"""
Baseline training/evaluation for PR timeline features.

Implements a multinomial Naive Bayes classifier over sparse count features.
No third-party dependencies are required.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


def _stable_hash_int(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16], 16)


def _is_feature_key(k: str) -> bool:
    return k.startswith("ev:") or k.startswith("tr:")


def _iter_jsonl(path: str | Path) -> Iterator[Dict]:
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _group_id(row: Dict) -> str:
    repo = row.get("repo")
    if isinstance(repo, str) and repo:
        return f"repo:{repo}"
    pr_key = row.get("pr_key")
    if isinstance(pr_key, str) and pr_key:
        return f"pr:{pr_key}"
    return "unknown"


def train_test_split_rows(
    rows: Iterable[Dict],
    test_fraction: float = 0.2,
    seed: int = 0,
) -> Tuple[List[Dict], List[Dict]]:
    train: List[Dict] = []
    test: List[Dict] = []

    for row in rows:
        gid = _group_id(row)
        h = _stable_hash_int(f"{seed}:{gid}")
        r = (h % 10_000_000) / 10_000_000.0
        (test if r < test_fraction else train).append(row)

    return train, test


@dataclass
class MultinomialNB:
    alpha: float = 1.0

    classes_: List[str] = None  # type: ignore[assignment]
    log_prior_: Dict[str, float] = None  # type: ignore[assignment]
    log_prob_: Dict[str, Dict[str, float]] = None  # type: ignore[assignment]
    vocab_: List[str] = None  # type: ignore[assignment]

    def fit(self, rows: List[Dict], label_key: str = "tool_family") -> "MultinomialNB":
        class_doc_counts = Counter()
        class_feature_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        vocab: set[str] = set()

        for row in rows:
            y = row.get(label_key)
            if not isinstance(y, str):
                continue
            class_doc_counts[y] += 1

            for k, v in row.items():
                if not isinstance(k, str) or not _is_feature_key(k):
                    continue
                if isinstance(v, (int, float)) and v:
                    c = int(v)
                    if c > 0:
                        class_feature_counts[y][k] += c
                        vocab.add(k)

        self.classes_ = sorted(class_doc_counts.keys())
        total_docs = sum(class_doc_counts.values())
        self.log_prior_ = {c: math.log(class_doc_counts[c] / total_docs) for c in self.classes_}

        self.vocab_ = sorted(vocab)

        self.log_prob_ = {}
        for c in self.classes_:
            counts = class_feature_counts[c]
            denom = sum(counts.values()) + self.alpha * len(self.vocab_)
            self.log_prob_[c] = {}
            for f in self.vocab_:
                num = counts.get(f, 0) + self.alpha
                self.log_prob_[c][f] = math.log(num / denom)

        return self

    def predict_one(self, row: Dict) -> Optional[str]:
        if not self.classes_:
            return None

        feats: Dict[str, int] = {}
        for k, v in row.items():
            if not isinstance(k, str) or not _is_feature_key(k):
                continue
            if isinstance(v, (int, float)) and v:
                c = int(v)
                if c > 0:
                    feats[k] = c

        best_c = None
        best_score = float("-inf")
        for c in self.classes_:
            score = self.log_prior_[c]
            lp = self.log_prob_[c]
            for f, cnt in feats.items():
                if f in lp:
                    score += cnt * lp[f]
            if score > best_score:
                best_score = score
                best_c = c
        return best_c


def confusion_matrix(y_true: List[str], y_pred: List[str], labels: List[str]) -> List[List[int]]:
    idx = {l: i for i, l in enumerate(labels)}
    m = [[0 for _ in labels] for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            m[idx[t]][idx[p]] += 1
    return m


def classification_report(y_true: List[str], y_pred: List[str], labels: List[str]) -> Dict:
    cm = confusion_matrix(y_true, y_pred, labels)
    totals = sum(sum(r) for r in cm)
    correct = sum(cm[i][i] for i in range(len(labels)))
    acc = correct / totals if totals else 0.0

    per_class = {}
    for i, l in enumerate(labels):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(len(labels))) - tp
        fn = sum(cm[i][c] for c in range(len(labels))) - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) else 0.0
        per_class[l] = {"precision": prec, "recall": rec, "f1": f1, "support": sum(cm[i])}

    return {"accuracy": acc, "labels": labels, "per_class": per_class, "confusion_matrix": cm}


def train_and_eval(
    features_jsonl: str | Path,
    test_fraction: float = 0.2,
    seed: int = 0,
    alpha: float = 1.0,
) -> Dict:
    rows = list(_iter_jsonl(features_jsonl))
    train_rows, test_rows = train_test_split_rows(rows, test_fraction=test_fraction, seed=seed)

    model = MultinomialNB(alpha=alpha).fit(train_rows)

    y_true: List[str] = []
    y_pred: List[str] = []
    for r in test_rows:
        yt = r.get("tool_family")
        if not isinstance(yt, str):
            continue
        yp = model.predict_one(r)
        if yp is None:
            continue
        y_true.append(yt)
        y_pred.append(yp)

    report = classification_report(y_true, y_pred, labels=model.classes_)
    return {
        "n_rows_total": len(rows),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "alpha": alpha,
        "seed": seed,
        "test_fraction": test_fraction,
        "model": {"classes": model.classes_, "vocab_size": len(model.vocab_ or [])},
        "metrics": report,
    }


def save_model(model: MultinomialNB, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "alpha": model.alpha,
        "classes": model.classes_,
        "log_prior": model.log_prior_,
        "log_prob": model.log_prob_,
        "vocab": model.vocab_,
    }
    p.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


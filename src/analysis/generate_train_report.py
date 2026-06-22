"""
Generate a detailed, grounded training report for the Naive Bayes baseline.

Default inputs are the ignored `.tmp/` artifacts produced by `src.analysis.pipeline`.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.analysis.train_nb import (
    _group_id,
    _iter_jsonl,
    classification_report,
    train_test_split_rows,
    MultinomialNB,
)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_float(x: float, nd: int = 6) -> str:
    return f"{x:.{nd}f}"


def _load_model_json(path: str | Path) -> MultinomialNB:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    m = MultinomialNB(alpha=float(obj["alpha"]))
    m.classes_ = list(obj["classes"])
    m.log_prior_ = {k: float(v) for k, v in obj["log_prior"].items()}
    m.log_prob_ = {c: {f: float(lp) for f, lp in d.items()} for c, d in obj["log_prob"].items()}
    m.vocab_ = list(obj["vocab"])
    return m


def _rows_basic_stats(rows: List[Dict]) -> Dict:
    by_label = Counter()
    repos = set()
    groups = Counter()
    n_missing_repo = 0

    for r in rows:
        y = r.get("tool_family")
        if isinstance(y, str):
            by_label[y] += 1

        repo = r.get("repo")
        if isinstance(repo, str) and repo:
            repos.add(repo)
        else:
            n_missing_repo += 1

        groups[_group_id(r)] += 1

    return {
        "n_rows": len(rows),
        "by_label": dict(by_label),
        "n_unique_repos": len(repos),
        "n_missing_repo": n_missing_repo,
        "n_groups": len(groups),
    }


def _split_group_leakage_check(train_rows: List[Dict], test_rows: List[Dict]) -> Dict:
    train_groups = set(_group_id(r) for r in train_rows)
    test_groups = set(_group_id(r) for r in test_rows)
    overlap = train_groups & test_groups
    return {"n_train_groups": len(train_groups), "n_test_groups": len(test_groups), "n_overlapping_groups": len(overlap)}


def _top_features_by_class(model: MultinomialNB, top_k: int = 25) -> Dict[str, List[Tuple[str, float]]]:
    out: Dict[str, List[Tuple[str, float]]] = {}
    classes = model.classes_ or []
    if not classes:
        return out
    for c in classes:
        scores: List[Tuple[str, float]] = []
        for f in model.vocab_ or []:
            lp_c = model.log_prob_[c].get(f)
            if lp_c is None:
                continue
            others = [model.log_prob_[c2].get(f) for c2 in classes if c2 != c]
            others = [x for x in others if x is not None]
            if not others:
                continue
            score = lp_c - (sum(others) / len(others))
            scores.append((f, score))
        scores.sort(key=lambda t: t[1], reverse=True)
        out[c] = scores[:top_k]
    return out


def write_markdown_report(
    features_jsonl: str | Path,
    model_json: str | Path,
    output_md: str | Path,
    test_fraction: float = 0.2,
    seed: int = 0,
    top_k_features: int = 25,
) -> None:
    rows = list(_iter_jsonl(features_jsonl))
    model = _load_model_json(model_json)

    train_rows, test_rows = train_test_split_rows(rows, test_fraction=test_fraction, seed=seed)
    split_check = _split_group_leakage_check(train_rows, test_rows)

    # Evaluate using saved model
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
    rep = classification_report(y_true, y_pred, labels=model.classes_)

    stats_all = _rows_basic_stats(rows)
    stats_train = _rows_basic_stats(train_rows)
    stats_test = _rows_basic_stats(test_rows)
    top_feats = _top_features_by_class(model, top_k=top_k_features)

    per = rep["per_class"]
    labels = rep["labels"]
    macro_f1 = sum(per[l]["f1"] for l in labels) / len(labels) if labels else 0.0
    macro_precision = sum(per[l]["precision"] for l in labels) / len(labels) if labels else 0.0
    macro_recall = sum(per[l]["recall"] for l in labels) / len(labels) if labels else 0.0
    support_total = sum(per[l]["support"] for l in labels) if labels else 0
    weighted_f1 = (
        sum(per[l]["f1"] * per[l]["support"] for l in labels) / support_total if support_total else 0.0
    )

    outp = Path(output_md)
    outp.parent.mkdir(parents=True, exist_ok=True)
    md: List[str] = []

    def w(s: str = "") -> None:
        md.append(s)

    w("## Model training report (Naive Bayes baseline)")
    w("")
    w(f"- **Generated (UTC)**: `{_now_utc_iso()}`")
    w(f"- **Features file**: `{Path(features_jsonl)}`")
    w(f"- **Model file**: `{Path(model_json)}`")
    w("")
    w("### Data volume")
    w(f"- **Rows (total)**: {stats_all['n_rows']}")
    w(f"- **Rows (train/test)**: {stats_train['n_rows']} / {stats_test['n_rows']}")
    w(f"- **Unique repos (all)**: {stats_all['n_unique_repos']}")
    w(f"- **Rows missing `repo` (all)**: {stats_all['n_missing_repo']}")
    w(f"- **Groups (all)**: {stats_all['n_groups']}")
    w("")
    w("**Label distribution (all rows)**:")
    for k, v in sorted(stats_all["by_label"].items(), key=lambda kv: (-kv[1], kv[0])):
        w(f"- {k}: {v}")
    w("")
    w("### Split integrity (group overlap check)")
    w(f"- **Train groups**: {split_check['n_train_groups']}")
    w(f"- **Test groups**: {split_check['n_test_groups']}")
    w(f"- **Overlapping groups**: {split_check['n_overlapping_groups']}")
    w("")
    w("### Evaluation on the test split (using the saved model)")
    w(f"- **Accuracy**: {_format_float(rep['accuracy'], 6)}")
    w(f"- **Macro precision/recall/F1**: {_format_float(macro_precision, 6)} / {_format_float(macro_recall, 6)} / {_format_float(macro_f1, 6)}")
    w(f"- **Weighted F1**: {_format_float(weighted_f1, 6)}")
    w("")
    w("**Per-class metrics**:")
    w("")
    w("| class | precision | recall | f1 | support |")
    w("|---|---:|---:|---:|---:|")
    for l in labels:
        w(f"| {l} | {_format_float(per[l]['precision'], 6)} | {_format_float(per[l]['recall'], 6)} | {_format_float(per[l]['f1'], 6)} | {per[l]['support']} |")
    w("")
    w("**Confusion matrix** (rows=true, cols=pred; label order matches table above):")
    w("")
    w("```")
    for row in rep["confusion_matrix"]:
        w(" ".join(str(x) for x in row))
    w("```")
    w("")
    w("### Most class-indicative features")
    w("Scores are `log P(feature|class) - mean_{other classes} log P(feature|other)`.")
    w("")
    for c in model.classes_ or []:
        w(f"#### {c}")
        feats = top_feats.get(c, [])
        if not feats:
            w("_No features available._")
            w("")
            continue
        w("| feature | score |")
        w("|---|---:|")
        for f, s in feats:
            w(f"| `{f}` | {_format_float(s, 6)} |")
        w("")

    outp.write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="src.analysis.generate_train_report")
    ap.add_argument("--features", default=".tmp/features.jsonl")
    ap.add_argument("--model", default=".tmp/model_nb.json")
    ap.add_argument("--output", default=".tmp/train_report.md")
    ap.add_argument("--test-fraction", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--top-k", type=int, default=25)
    args = ap.parse_args()

    write_markdown_report(
        features_jsonl=args.features,
        model_json=args.model,
        output_md=args.output,
        test_fraction=args.test_fraction,
        seed=args.seed,
        top_k_features=args.top_k,
    )
    print(f"Wrote report to: {args.output}")


if __name__ == "__main__":
    main()


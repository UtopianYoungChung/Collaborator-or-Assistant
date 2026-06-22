"""
Qualitative analysis for PR timeline datasets under `data/raw/`.

This module extracts raw text fields (comment `body` and commit `message`) from the
timeline JSONs, applies transparent template filters + deduplication, and then
performs lightweight thematic clustering (TF-IDF + KMeans) to surface recurring
topics with representative excerpts.

Outputs:
- A cleaned JSONL corpus with metadata (for reproducibility)
- A markdown report with counts, clusters, and grounded excerpts
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from src.analysis.stream_pr_timelines import iter_timeline_items


_WS_RE = re.compile(r"\s+")


def _tool_family_from_dataset_filename(name: str) -> str:
    # Expected: pr_timelines_<tool_family>.json
    p = Path(name).name
    if p.startswith("pr_timelines_") and p.endswith(".json"):
        return p[len("pr_timelines_") : -len(".json")]
    return p


def _safe_get_login(d: Any) -> Optional[str]:
    if isinstance(d, dict):
        v = d.get("login")
        return v if isinstance(v, str) else None
    return None


def _safe_get_type(d: Any) -> Optional[str]:
    if isinstance(d, dict):
        v = d.get("type")
        return v if isinstance(v, str) else None
    return None


def _normalize_for_hash(text: str) -> str:
    # Keep simple: collapse whitespace and strip.
    return _WS_RE.sub(" ", text).strip()


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class TextRecord:
    tool_family: str
    dataset_file: str
    pr_key: str
    event: Optional[str]
    text_field: str  # "body" or "message"
    author_login: Optional[str]
    author_type: Optional[str]  # "User", "Bot", ...
    text: str


def _template_labels_for_body(body: str) -> List[str]:
    """
    Transparent, substring-based template detection.

    Labels here are intentionally conservative and based only on patterns
    observed directly in this workspace's datasets during exploration.
    """
    labels: List[str] = []
    b = body
    bl = body.lower()

    if "devin ai engineer" in bl:
        labels.append("tpl:devin_intro")
    if b.startswith("## Pull Request Overview"):
        labels.append("tpl:pr_overview")
    if "codecov" in bl and "report" in bl:
        labels.append("tpl:codecov_report")
    if "cla-assistant.io" in bl or "cla assistant check" in bl:
        labels.append("tpl:cla_assistant")
    if "[approvalnotifier]" in bl:
        labels.append("tpl:approvalnotifier")
    if "<!-- this is an auto-generated comment" in bl:
        labels.append("tpl:coderabbit_autogen")
    if "actionable comments posted:" in bl and "<details" in bl:
        labels.append("tpl:bulk_review_bot")
    if b.startswith("Visit the preview URL for this PR"):
        labels.append("tpl:preview_link")
    if "<details" in bl:
        labels.append("has:details_tag")

    return labels


def _template_labels_for_message(msg: str) -> List[str]:
    labels: List[str] = []
    m = msg.strip()
    ml = m.lower()

    if m == "Initial plan":
        labels.append("tpl:initial_plan_exact")
    if ml.startswith("initial plan"):
        labels.append("tpl:initial_plan_prefix")
    if "generated with claude code" in ml:
        labels.append("has:generated_with_claude_code")
    if "co-authored-by:" in ml or "co-authored-by" in ml:
        labels.append("has:co_authored_by")
    if ml.startswith(("feat:", "fix:", "refactor:")):
        labels.append("has:conventional_commit_prefix")

    return labels


def iter_text_records(dataset_path: Path) -> Iterator[TextRecord]:
    tool_family = _tool_family_from_dataset_filename(dataset_path.name)
    for ti in iter_timeline_items(dataset_path):
        if ti.item is None:
            continue
        item = ti.item

        event = item.get("event")
        event_s = event if isinstance(event, str) else None

        author_login = _safe_get_login(item.get("actor")) or _safe_get_login(item.get("user"))
        author_type = _safe_get_type(item.get("actor")) or _safe_get_type(item.get("user"))

        body = item.get("body")
        if isinstance(body, str):
            yield TextRecord(
                tool_family=tool_family,
                dataset_file=str(dataset_path),
                pr_key=ti.pr_key,
                event=event_s,
                text_field="body",
                author_login=author_login,
                author_type=author_type,
                text=body,
            )

        msg = item.get("message")
        if isinstance(msg, str):
            yield TextRecord(
                tool_family=tool_family,
                dataset_file=str(dataset_path),
                pr_key=ti.pr_key,
                event=event_s,
                text_field="message",
                author_login=author_login,
                author_type=author_type,
                text=msg,
            )


@dataclass
class CorpusBuildResult:
    records_written: int
    duplicates_dropped: int
    templates_dropped: int
    counts_by_tool_family: Dict[str, int]
    counts_by_author_type: Dict[str, int]
    dropped_by_template: Dict[str, int]


def build_corpus_jsonl(
    dataset_dir: Path,
    out_jsonl: Path,
    *,
    drop_templates: bool,
    dedup: bool,
    min_chars: int,
    max_records: Optional[int],
) -> CorpusBuildResult:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    counts_by_tool_family: Counter[str] = Counter()
    counts_by_author_type: Counter[str] = Counter()
    dropped_by_template: Counter[str] = Counter()

    seen_hashes: set[str] = set()
    records_written = 0
    duplicates_dropped = 0
    templates_dropped = 0

    dataset_files = sorted(dataset_dir.glob("pr_timelines_*.json"))
    with out_jsonl.open("w", encoding="utf-8") as f:
        for fp in dataset_files:
            for rec in iter_text_records(fp):
                text = rec.text
                if len(text) < min_chars:
                    continue

                # Label templates
                if rec.text_field == "body":
                    labels = _template_labels_for_body(text)
                else:
                    labels = _template_labels_for_message(text)

                is_template = any(l.startswith("tpl:") for l in labels)
                if drop_templates and is_template:
                    templates_dropped += 1
                    for l in labels:
                        if l.startswith("tpl:"):
                            dropped_by_template[l] += 1
                    continue

                norm = _normalize_for_hash(text)
                h = _sha1(norm)
                if dedup:
                    if h in seen_hashes:
                        duplicates_dropped += 1
                        continue
                    seen_hashes.add(h)

                row = {
                    "tool_family": rec.tool_family,
                    "dataset_file": rec.dataset_file,
                    "pr_key": rec.pr_key,
                    "event": rec.event,
                    "text_field": rec.text_field,
                    "author_login": rec.author_login,
                    "author_type": rec.author_type,
                    "labels": labels,
                    "text": text,
                    "text_len": len(text),
                    "text_hash": h,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                records_written += 1

                counts_by_tool_family[rec.tool_family] += 1
                if rec.author_type is not None:
                    counts_by_author_type[rec.author_type] += 1
                else:
                    counts_by_author_type["(unknown)"] += 1

                if max_records is not None and records_written >= max_records:
                    break
            if max_records is not None and records_written >= max_records:
                break

    return CorpusBuildResult(
        records_written=records_written,
        duplicates_dropped=duplicates_dropped,
        templates_dropped=templates_dropped,
        counts_by_tool_family=dict(counts_by_tool_family),
        counts_by_author_type=dict(counts_by_author_type),
        dropped_by_template=dict(dropped_by_template),
    )


def _load_corpus(out_jsonl: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with out_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _tokenize_for_keywords(text: str) -> List[str]:
    # Simple, transparent tokenization: alphabetic words >=3 chars, lowercased.
    return re.findall(r"[a-zA-Z]{3,}", text.lower())


def _top_keywords(texts: Iterable[str], top_k: int) -> List[Tuple[str, int]]:
    c: Counter[str] = Counter()
    for t in texts:
        c.update(_tokenize_for_keywords(t))
    return c.most_common(top_k)


def cluster_texts_tfidf_kmeans(
    rows: List[Dict[str, Any]],
    *,
    n_clusters: int,
    min_df: int,
    max_features: int,
    random_state: int,
) -> Dict[str, Any]:
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [r["text"] for r in rows]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        min_df=min_df,
        max_features=max_features,
        token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
    )
    X = vectorizer.fit_transform(texts)

    k = min(n_clusters, X.shape[0]) if X.shape[0] > 0 else 0
    if k <= 1:
        return {"k": k, "labels": [0] * len(rows), "top_terms": {0: []}, "repr_idx": {0: []}}

    km = KMeans(n_clusters=k, random_state=random_state, n_init="auto")
    labels = km.fit_predict(X)

    # Top terms per cluster from centroid weights
    terms = vectorizer.get_feature_names_out()
    top_terms: Dict[int, List[Tuple[str, float]]] = {}
    for ci in range(k):
        center = km.cluster_centers_[ci]
        idxs = center.argsort()[::-1][:12]
        top_terms[ci] = [(terms[i], float(center[i])) for i in idxs if center[i] > 0]

    # Representative documents per cluster (closest to centroid)
    repr_idx: Dict[int, List[int]] = defaultdict(list)
    # distances: (n_samples, n_clusters)
    dists = km.transform(X)
    for ci in range(k):
        members = [i for i, lab in enumerate(labels) if lab == ci]
        members_sorted = sorted(members, key=lambda i: float(dists[i, ci]))
        repr_idx[ci] = members_sorted[:5]

    return {"k": k, "labels": labels.tolist(), "top_terms": top_terms, "repr_idx": dict(repr_idx)}


def write_markdown_report(
    *,
    corpus_jsonl: Path,
    out_md: Path,
    build_result: CorpusBuildResult,
    cluster_result: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)

    def _md_escape(s: str) -> str:
        return s.replace("\r", "").replace("\n", "\\n")

    # Basic breakdowns
    counts_by_tool = Counter(r["tool_family"] for r in rows)
    counts_by_field = Counter(r["text_field"] for r in rows)
    counts_by_author_type = Counter(r.get("author_type") or "(unknown)" for r in rows)

    # Human-only view (author_type == "User")
    human_rows = [r for r in rows if (r.get("author_type") == "User")]

    with out_md.open("w", encoding="utf-8") as f:
        f.write("## Qualitative insights report\n\n")
        f.write(f"- **Corpus**: `{corpus_jsonl}`\n")
        f.write(f"- **Records written**: {build_result.records_written}\n")
        f.write(f"- **Dropped (templates)**: {build_result.templates_dropped}\n")
        f.write(f"- **Dropped (duplicates)**: {build_result.duplicates_dropped}\n")
        f.write("\n")

        f.write("### Corpus composition\n\n")
        f.write("**Counts by tool_family**:\n\n")
        for k, v in sorted(counts_by_tool.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write(f"- {k}: {v}\n")
        f.write("\n")

        f.write("**Counts by text_field**:\n\n")
        for k, v in sorted(counts_by_field.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write(f"- {k}: {v}\n")
        f.write("\n")

        f.write("**Counts by author_type**:\n\n")
        for k, v in sorted(counts_by_author_type.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write(f"- {k}: {v}\n")
        f.write("\n")

        f.write(f"**Human-authored records (author_type == User)**: {len(human_rows)}\n\n")

        if build_result.dropped_by_template:
            f.write("### Template filters applied (dropped)\n\n")
            for k, v in sorted(build_result.dropped_by_template.items(), key=lambda kv: (-kv[1], kv[0])):
                f.write(f"- {k}: {v}\n")
            f.write("\n")

        # Clustered themes (keywords + excerpts)
        k = int(cluster_result.get("k", 0) or 0)
        labels = cluster_result.get("labels", [])
        top_terms = cluster_result.get("top_terms", {})
        repr_idx = cluster_result.get("repr_idx", {})

        f.write("### Thematic clusters (TF-IDF + KMeans)\n\n")
        f.write(
            "Each cluster is labeled by its top TF-IDF terms (not a human-assigned topic), "
            "with representative excerpts shown verbatim (truncated).\n\n"
        )
        f.write(f"- **k (clusters used)**: {k}\n\n")

        if k <= 1 or not rows:
            f.write("_Not enough records to cluster._\n")
            return

        # Per-cluster listing
        cluster_sizes = Counter(labels)
        for ci, size in sorted(cluster_sizes.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write(f"#### Cluster {ci} (n={size})\n\n")
            terms_ci = top_terms.get(ci, [])
            if terms_ci:
                f.write("**Top terms**: " + ", ".join([t for (t, _w) in terms_ci[:10]]) + "\n\n")
            else:
                f.write("**Top terms**: (none)\n\n")

            # Additional transparent keyword frequency (counts) within cluster
            idxs = [i for i, lab in enumerate(labels) if lab == ci]
            kw = _top_keywords((rows[i]["text"] for i in idxs), top_k=10)
            if kw:
                f.write(
                    "**Top word counts (cluster-local)**: "
                    + ", ".join([f"{w}({c})" for w, c in kw])
                    + "\n\n"
                )

            f.write("**Representative excerpts**:\n\n")
            for i in repr_idx.get(ci, [])[:5]:
                r = rows[i]
                prefix = r["text"][:360]
                meta = f"{r['tool_family']} | {r.get('author_type') or '(unknown)'} | {r['text_field']} | {r.get('event') or '(no-event)'} | {r['pr_key']}"
                f.write(f"- `{meta}`\n\n")
                f.write("  > " + _md_escape(prefix) + "\n\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="src.analysis.qualitative_insights")
    p.add_argument("--dataset-dir", default="data/raw", help="Directory containing pr_timelines_*.json")
    p.add_argument("--out-corpus", default=".tmp/qualitative_corpus.jsonl", help="Output JSONL corpus path")
    p.add_argument("--out-report", default=".tmp/qualitative_report.md", help="Output markdown report path")

    p.add_argument("--min-chars", type=int, default=40, help="Drop texts shorter than this")
    p.add_argument("--max-records", type=int, default=None, help="Optional cap for faster iteration")
    p.add_argument("--no-dedup", action="store_true", help="Disable deduplication (default: dedup on)")
    p.add_argument(
        "--keep-templates",
        action="store_true",
        help="Keep detected templates (default: drop templates)",
    )

    p.add_argument("--clusters", type=int, default=12, help="Requested number of clusters")
    p.add_argument("--min-df", type=int, default=5, help="TF-IDF min_df")
    p.add_argument("--max-features", type=int, default=25000, help="TF-IDF max_features")
    p.add_argument("--seed", type=int, default=0, help="Random seed")
    return p


def main() -> None:
    args = build_parser().parse_args()

    dataset_dir = Path(args.dataset_dir)
    out_corpus = Path(args.out_corpus)
    out_report = Path(args.out_report)

    build_result = build_corpus_jsonl(
        dataset_dir=dataset_dir,
        out_jsonl=out_corpus,
        drop_templates=(not args.keep_templates),
        dedup=(not args.no_dedup),
        min_chars=args.min_chars,
        max_records=args.max_records,
    )

    rows = _load_corpus(out_corpus)
    cluster_result = cluster_texts_tfidf_kmeans(
        rows,
        n_clusters=args.clusters,
        min_df=args.min_df,
        max_features=args.max_features,
        random_state=args.seed,
    )

    write_markdown_report(
        corpus_jsonl=out_corpus,
        out_md=out_report,
        build_result=build_result,
        cluster_result=cluster_result,
        rows=rows,
    )

    print(json.dumps({"corpus": str(out_corpus), "report": str(out_report), "records": build_result.records_written}, indent=2))


if __name__ == "__main__":
    main()


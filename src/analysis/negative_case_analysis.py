"""
Negative-case analysis: closed-without-merge PRs.

This is intended to address survivorship bias concerns noted in `reviews/critical_review_2026-01-18.md`.

Definition (dataset-grounded):
- Negative case: PR workflow contains a `closed` event and does NOT contain a `merged` event.

Sampling:
- Deterministic stratified sampling by tool, with a fixed seed.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.analysis.evidence_stats import compute_evidence_stats
from src.analysis.stream_pr_timelines import iter_timeline_items
from src.analysis.workflows import CollaborationType, DATASET_DIR, FILES, analyze_workflow


def _iter_pr_event_lists(dataset_path: Path) -> Iterable[Tuple[str, List[dict]]]:
    current_key: Optional[str] = None
    current_events: List[dict] = []
    for ti in iter_timeline_items(dataset_path):
        if ti.item is None:
            if current_key is not None:
                yield current_key, current_events
            current_key = None
            current_events = []
            continue
        if current_key is None:
            current_key = ti.pr_key
        current_events.append(ti.item)


def _is_closed_without_merge(pr_events: List[dict]) -> bool:
    has_closed = False
    has_merged = False
    for ev in pr_events:
        if not isinstance(ev, dict):
            continue
        et = ev.get("event")
        if et == "closed":
            has_closed = True
        elif et == "merged":
            has_merged = True
    return has_closed and (not has_merged)


def _has_pr_url(pr_id: str, pr_events: List[dict], tool: str) -> bool:
    """
    Return True iff the canonical analyzer can extract a GitHub PR URL.

    This is used to improve auditability of negative-case samples by ensuring the
    sampled PRs can be verified against GitHub UI when needed.
    """
    wf = analyze_workflow(pr_id, pr_events, tool, ml_analyzer=None)
    return bool(wf.url)


@dataclass(frozen=True)
class SampledPR:
    tool: str
    pr_id: str
    url: Optional[str]
    repo: Optional[str]
    collaboration_type: str
    agent_events: int
    human_events: int
    revision_cycles: int


def _sample_ids_by_tool(
    rng: random.Random, target_per_tool: int
) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """
    Returns (sample_ids_by_tool, candidate_counts_by_tool).
    """
    candidates_by_tool: Dict[str, List[str]] = {}
    candidate_counts: Dict[str, int] = {}
    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        ids: List[str] = []
        for pr_id, pr_events in _iter_pr_event_lists(fp):
            if _is_closed_without_merge(pr_events):
                # Restrict to PRs with resolvable URLs to improve auditability.
                if _has_pr_url(pr_id, pr_events, tool):
                    ids.append(pr_id)
        ids.sort()
        candidate_counts[tool] = len(ids)
        candidates_by_tool[tool] = ids

    sample_ids_by_tool: Dict[str, List[str]] = {}
    for tool, ids in candidates_by_tool.items():
        k = min(target_per_tool, len(ids))
        sample_ids_by_tool[tool] = rng.sample(ids, k=k) if k > 0 else []
        sample_ids_by_tool[tool].sort()

    return sample_ids_by_tool, candidate_counts


def _fetch_and_analyze_samples(sample_ids_by_tool: Dict[str, List[str]]) -> List[SampledPR]:
    wanted = {tool: set(ids) for tool, ids in sample_ids_by_tool.items()}
    samples: List[SampledPR] = []

    for tool, filename in FILES.items():
        if not wanted.get(tool):
            continue
        fp = DATASET_DIR / filename
        for pr_id, pr_events in _iter_pr_event_lists(fp):
            if pr_id not in wanted[tool]:
                continue
            wf = analyze_workflow(pr_id, pr_events, tool, ml_analyzer=None)
            samples.append(
                SampledPR(
                    tool=tool,
                    pr_id=pr_id,
                    url=wf.url,
                    repo=wf.repo,
                    collaboration_type=wf.collaboration_type.value,
                    agent_events=wf.agent_total,
                    human_events=wf.human_total,
                    revision_cycles=wf.revision_cycles,
                )
            )
    samples.sort(key=lambda s: (s.tool, s.pr_id))
    return samples


def _render_distribution_table(counts: Dict[str, int], total: int) -> str:
    types = [ct.value for ct in CollaborationType]
    lines: List[str] = []
    lines.append("| Type | Count | Percent |")
    lines.append("|---|---:|---:|")
    for t in types:
        k = int(counts.get(t, 0))
        pct = (100.0 * k / total) if total else 0.0
        lines.append(f"| {t} | {k:,} | {pct:.1f}% |")
    lines.append(f"| **TOTAL** | **{total:,}** | **100.0%** |")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(prog="src.analysis.negative_case_analysis")
    p.add_argument("--seed", type=int, default=0, help="Deterministic sampling seed")
    p.add_argument("--target-per-tool", type=int, default=10, help="Target sample size per tool")
    p.add_argument("--output", default="reports/negative_case_analysis.md")
    args = p.parse_args()

    rng = random.Random(args.seed)
    sample_ids_by_tool, candidate_counts = _sample_ids_by_tool(rng, target_per_tool=args.target_per_tool)
    samples = _fetch_and_analyze_samples(sample_ids_by_tool)

    total_sampled = len(samples)
    counts_overall = Counter(s.collaboration_type for s in samples)
    counts_by_tool: Dict[str, Counter[str]] = defaultdict(Counter)
    for s in samples:
        counts_by_tool[s.tool][s.collaboration_type] += 1

    # URL coverage (auditability)
    url_missing_overall = sum(1 for s in samples if not s.url)
    url_missing_by_tool: Dict[str, int] = defaultdict(int)
    for s in samples:
        if not s.url:
            url_missing_by_tool[s.tool] += 1

    baseline = compute_evidence_stats()
    baseline_total = sum(baseline.overall_counts_by_type.values())

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# Negative Case Analysis (Closed Without Merge)")
    lines.append("")
    lines.append("## Definition")
    lines.append("")
    lines.append(
        "- **Negative case**: PR contains a `closed` event and does **not** contain a `merged` event."
    )
    lines.append("")
    lines.append("## Sampling")
    lines.append("")
    lines.append(f"- **Seed**: {args.seed}")
    lines.append(f"- **Target per tool**: {args.target_per_tool}")
    lines.append(f"- **Total sampled**: {total_sampled}")
    lines.append("")
    lines.append("### Candidate pool sizes (closed-without-merge; URL-resolvable)")
    lines.append("")
    lines.append("| Tool | Candidate PRs | Sampled |")
    lines.append("|---|---:|---:|")
    for tool in FILES.keys():
        lines.append(
            f"| {tool} | {candidate_counts.get(tool, 0):,} | {len(sample_ids_by_tool.get(tool, [])):,} |"
        )
    lines.append("")
    lines.append("## Results")
    lines.append("")

    lines.append("### URL coverage (sample auditability)")
    lines.append("")
    lines.append(
        f"- **Sample rows with missing URL**: {url_missing_overall} / {total_sampled}"
        + (f" ({100.0*url_missing_overall/total_sampled:.1f}%)" if total_sampled else "")
    )
    lines.append("")
    lines.append("| Tool | Sampled | Missing URL | Missing % |")
    lines.append("|---|---:|---:|---:|")
    for tool in FILES.keys():
        n = len(sample_ids_by_tool.get(tool, []))
        miss = int(url_missing_by_tool.get(tool, 0))
        pct = (100.0 * miss / n) if n else 0.0
        lines.append(f"| {tool} | {n} | {miss} | {pct:.1f}% |")
    lines.append("")

    lines.append("### Collaboration type distribution (negative cases)")
    lines.append("")
    lines.append(_render_distribution_table(dict(counts_overall), total_sampled))
    lines.append("")
    lines.append("### Collaboration type distribution (baseline; all PRs)")
    lines.append("")
    lines.append(_render_distribution_table(baseline.overall_counts_by_type, baseline_total))
    lines.append("")
    lines.append("### Per-tool negative-case distributions (sample)")
    lines.append("")
    for tool in FILES.keys():
        ct = counts_by_tool.get(tool, Counter())
        n = sum(ct.values())
        lines.append(f"#### {tool} (n={n})")
        lines.append("")
        lines.append(_render_distribution_table(dict(ct), n))
        lines.append("")
    lines.append("## Sample listing")
    lines.append("")
    lines.append("| Tool | PR key | Repo | URL | Type | Agent events | Human events | Revision cycles |")
    lines.append("|---|---|---|---|---|---:|---:|---:|")
    for s in samples:
        url_cell = s.url if s.url else "(missing)"
        lines.append(
            f"| {s.tool} | `{s.pr_id}` | {s.repo or ''} | {url_cell} | {s.collaboration_type} | "
            f"{s.agent_events} | {s.human_events} | {s.revision_cycles} |"
        )
    lines.append("")

    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()


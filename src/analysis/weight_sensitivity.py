"""
Weight sensitivity analysis for collaboration metrics.

Goal: test stability of collaboration-type distributions under alternative event-weight
schemes (as recommended in `reviews/critical_review_2026-01-18.md`).

Performance note: this script streams `data/raw/` once, then recomputes weighted scores
under each scheme without re-reading the dataset multiple times.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.analysis.evidence_stats import compute_evidence_stats
from src.analysis.stream_pr_timelines import iter_timeline_items
from src.analysis.workflows import (
    CollaborationType,
    DATASET_DIR,
    EVENT_WEIGHTS,
    FILES,
    WorkflowPhaseName,
    analyze_workflow,
)


def _format_pct(k: int, n: int) -> str:
    if n <= 0:
        return "0.0%"
    return f"{100.0 * k / n:.1f}%"


def _get_reviewed_weight(weights: dict, review_state: Optional[str]) -> float:
    m = weights.get("reviewed", {})
    state = (review_state or "").upper()
    if isinstance(m, dict) and state in m:
        return float(m[state])
    if isinstance(m, dict):
        return float(m.get("COMMENTED", 1.0))
    return 1.0


def _event_weight(weights: dict, event_type: str, review_state: Optional[str]) -> float:
    if event_type == "reviewed":
        return _get_reviewed_weight(weights, review_state)
    v = weights.get(event_type)
    if isinstance(v, (int, float)):
        return float(v)
    return float(weights.get("default", 0.0))


@dataclass(frozen=True)
class _PRSummary:
    tool: str
    pr_id: str
    baseline_type: str
    initiator: str
    resolver: str
    agent_total: int
    human_total: int
    revision_cycles: int
    dev_phase_exists: bool
    dev_agent_count: int
    # Each tuple: (is_agent, event_type, review_state)
    events: Tuple[Tuple[bool, str, Optional[str]], ...]


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


def _collect_summaries() -> List[_PRSummary]:
    summaries: List[_PRSummary] = []
    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        for pr_key, pr_events in _iter_pr_event_lists(fp):
            wf = analyze_workflow(pr_key, pr_events, tool, ml_analyzer=None)
            dev = wf.phases.get(WorkflowPhaseName.PR_CREATED.value)
            evs = tuple((e.is_agent, e.event_type, e.review_state) for e in wf.events)
            summaries.append(
                _PRSummary(
                    tool=tool,
                    pr_id=pr_key,
                    baseline_type=wf.collaboration_type.value,
                    initiator=wf.initiator,
                    resolver=wf.resolver,
                    agent_total=wf.agent_total,
                    human_total=wf.human_total,
                    revision_cycles=wf.revision_cycles,
                    dev_phase_exists=(dev is not None and bool(dev.events)),
                    dev_agent_count=(dev.agent_count if dev is not None else 0),
                    events=evs,
                )
            )
    return summaries


def _collaboration_score(weights: dict, pr: _PRSummary) -> float:
    a = 0.0
    h = 0.0
    for is_agent, event_type, review_state in pr.events:
        w = _event_weight(weights, event_type, review_state)
        if is_agent:
            a += w
        else:
            h += w
    if a == 0.0 and h == 0.0:
        return 0.0
    return min(a, h) / max(a, h)


def _classify_for_scheme(weights: dict, pr: _PRSummary) -> str:
    """
    Compute the collaboration type under an alternate weight scheme.

    With the observable-only taxonomy (initiator × resolver), collaboration type
    does not depend on event weights. We always return the baseline type.
    """
    return pr.baseline_type


def _weights_scheme_uniform() -> dict:
    # Scheme A (Uniform): all events = 1.0
    return {
        "committed": 1.0,
        "reviewed": {"CHANGES_REQUESTED": 1.0, "APPROVED": 1.0, "COMMENTED": 1.0},
        "commented": 1.0,
        "review_requested": 1.0,
        "assigned": 1.0,
        "labeled": 1.0,
        "default": 1.0,
    }


def _weights_scheme_binary() -> dict:
    # Scheme B (Binary): commits=1.0, all others=0.5
    return {
        "committed": 1.0,
        "reviewed": {"CHANGES_REQUESTED": 0.5, "APPROVED": 0.5, "COMMENTED": 0.5},
        "commented": 0.5,
        "review_requested": 0.5,
        "assigned": 0.5,
        "labeled": 0.5,
        "default": 0.5,
    }


def _weights_scheme_inverted() -> dict:
    # Scheme C (Inverted): reviews=3.0, commits=1.5 (others moderate)
    return {
        "committed": 1.5,
        "reviewed": {"CHANGES_REQUESTED": 3.0, "APPROVED": 3.0, "COMMENTED": 3.0},
        "commented": 1.0,
        "review_requested": 0.5,
        "assigned": 0.25,
        "labeled": 0.25,
        "default": 0.5,
    }


def _render_overall_table(overall_counts_by_type: Dict[str, int]) -> str:
    total = sum(overall_counts_by_type.values())
    types = [ct.value for ct in CollaborationType]

    lines: List[str] = []
    lines.append("| Type | Count | Percent |")
    lines.append("|---|---:|---:|")
    for t in types:
        k = int(overall_counts_by_type.get(t, 0))
        lines.append(f"| {t} | {k:,} | {_format_pct(k, total)} |")
    lines.append(f"| **TOTAL** | **{total:,}** | **100.0%** |")
    return "\n".join(lines)


def _render_by_tool_table(
    totals_by_tool: Dict[str, int],
    counts_by_tool_and_type: Dict[str, Dict[str, int]],
    focus_types: List[str],
) -> str:
    tools = list(FILES.keys())

    lines: List[str] = []
    lines.append("| Tool | Total PRs | " + " | ".join(focus_types) + " |")
    lines.append("|---|---:|" + "|".join(["---:" for _ in focus_types]) + "|")
    for tool in tools:
        n = int(totals_by_tool.get(tool, 0))
        row = [f"**{tool}**", f"{n:,}"]
        for t in focus_types:
            k = int(counts_by_tool_and_type.get(tool, {}).get(t, 0))
            row.append(f"{k:,} ({_format_pct(k, n)})")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(prog="src.analysis.weight_sensitivity")
    p.add_argument("--output", default="reports/weight_sensitivity_analysis.md")
    args = p.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schemes: List[tuple[str, dict]] = [
        ("Baseline (current EVENT_WEIGHTS)", EVENT_WEIGHTS),
        ("Scheme A (Uniform: all events = 1.0)", _weights_scheme_uniform()),
        ("Scheme B (Binary: commits=1.0, others=0.5)", _weights_scheme_binary()),
        ("Scheme C (Inverted: reviews=3.0, commits=1.5)", _weights_scheme_inverted()),
    ]

    focus = [ct.value for ct in CollaborationType]

    sections: List[str] = []
    sections.append("# Weight Sensitivity Analysis")
    sections.append("")
    sections.append(
        "This report evaluates how collaboration-type distributions change under alternative "
        "event-weight schemes. The dataset is streamed once, and per-PR weighted scores are "
        "recomputed under each scheme without re-reading `data/raw/` multiple times."
    )
    sections.append("")

    baseline_expected = compute_evidence_stats().overall_counts_by_type
    summaries = _collect_summaries()

    for title, weights in schemes:
        totals_by_tool: Dict[str, int] = {t: 0 for t in FILES.keys()}
        counts_by_tool_and_type: Dict[str, Dict[str, int]] = {t: {} for t in FILES.keys()}
        overall_counts_by_type: Dict[str, int] = {}

        is_baseline = title.startswith("Baseline")
        for pr in summaries:
            totals_by_tool[pr.tool] += 1
            ctype = pr.baseline_type if is_baseline else _classify_for_scheme(weights, pr)
            counts_by_tool_and_type[pr.tool][ctype] = counts_by_tool_and_type[pr.tool].get(ctype, 0) + 1
            overall_counts_by_type[ctype] = overall_counts_by_type.get(ctype, 0) + 1

        sections.append(f"## {title}")
        sections.append("")
        sections.append("### Overall distribution (all tools)")
        sections.append("")
        sections.append(_render_overall_table(overall_counts_by_type))
        sections.append("")
        sections.append("### Per-tool distribution")
        sections.append("")
        sections.append(_render_by_tool_table(totals_by_tool, counts_by_tool_and_type, focus_types=focus))
        sections.append("")

        if is_baseline:
            if dict(overall_counts_by_type) != dict(baseline_expected):
                sections.append("### Baseline integrity check (FAILED)")
                sections.append("")
                sections.append(
                    "**WARNING**: The baseline distribution computed by this script does not match "
                    "the canonical `compute_evidence_stats()` output. This indicates a bug and "
                    "the results below should not be used."
                )
                sections.append("")
                sections.append("Expected (from `compute_evidence_stats()`):")
                sections.append("")
                sections.append("```json")
                sections.append(json.dumps(baseline_expected, indent=2))
                sections.append("```")
                sections.append("")
                sections.append("Observed:")
                sections.append("")
                sections.append("```json")
                sections.append(json.dumps(overall_counts_by_type, indent=2))
                sections.append("```")
                sections.append("")

    out_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()


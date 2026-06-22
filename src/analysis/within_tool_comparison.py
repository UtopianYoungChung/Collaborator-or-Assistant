"""
Within-tool comparison: among human-initiated PRs only, compare first-exit-from-PR-created
(Review vs Merged vs Unmerged vs Revision) by tool.

Addresses circularity concern: paradigm is defined by initiation rate, then we analyze
review/direct-resolution; holding initiation constant (human-init only) shows whether
Collaborator vs Assistant tools differ in review behavior when the initiator is human.

Run from repo root:
  python -m src.analysis.within_tool_comparison
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from src.analysis.evidence_stats import DATASET_DIR, _iter_pr_event_lists, wilson_interval
from src.analysis.workflows import (
    FILES,
    CollaborationType,
    analyze_workflow,
    get_phase_transition_sequence,
)

# Human-initiated scenarios (S4, S5, S6)
HUMAN_INIT_TYPES = {
    CollaborationType.HUMAN_INITIATED_HUMAN_MERGED.value,
    CollaborationType.HUMAN_INITIATED_AGENT_MERGED.value,
    CollaborationType.HUMAN_INITIATED_NOT_MERGED.value,
}

# Display names for first-exit targets (from get_phase_transition_sequence: pr_created -> X)
EXIT_LABELS = {
    "review": "→ Review",
    "revision": "→ Revision",
    "merged_and_closed": "→ Merged and closed",
    "unmerged_and_closed": "→ Unmerged and closed",
}


def first_exit_from_pr_created(events) -> str | None:
    """
    Return the first transition target from pr_created (review, revision,
    merged_and_closed, or unmerged_and_closed), or None if no such transition.
    """
    seq = get_phase_transition_sequence(events)
    for from_phase, to_phase in seq:
        if from_phase == "pr_created":
            return to_phase
    return None


def run() -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """
    Stream all tools; for each PR, if human-initiated (S4/S5/S6), record
    tool and first exit from PR created. Return (counts_by_tool_and_exit, n_human_init_by_tool).
    """
    counts_by_tool_and_exit: Dict[str, Counter[str]] = defaultdict(Counter)
    n_human_init_by_tool: Dict[str, int] = {}

    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        if not fp.exists():
            continue
        n_human = 0
        for pr_key, pr_events in _iter_pr_event_lists(fp):
            wf = analyze_workflow(pr_key, pr_events, tool, ml_analyzer=None)
            ctype = wf.collaboration_type.value
            if ctype not in HUMAN_INIT_TYPES:
                continue
            n_human += 1
            exit_target = first_exit_from_pr_created(wf.events)
            if exit_target is not None:
                counts_by_tool_and_exit[tool][exit_target] += 1
        n_human_init_by_tool[tool] = n_human

    # Convert Counter to dict of dicts for JSON
    result = {
        tool: dict(ct) for tool, ct in counts_by_tool_and_exit.items()
    }
    return result, n_human_init_by_tool


def main() -> None:
    counts_by_tool_and_exit, n_human_init_by_tool = run()

    out_dir = Path(".tmp")
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = out_dir / "within_tool_human_initiated_report.json"
    with open(json_path, "w") as f:
        import json
        json.dump({
            "n_human_initiated_by_tool": n_human_init_by_tool,
            "first_exit_from_pr_created_by_tool": counts_by_tool_and_exit,
        }, f, indent=2)
    print(f"Wrote {json_path}")

    # Markdown summary
    md_path = out_dir / "within_tool_human_initiated_report.md"
    lines: List[str] = [
        "# Within-tool comparison: human-initiated PRs only",
        "",
        "First exit from PR created (Review, Revision, Merged, Unmerged) by tool.",
        "Addresses circularity: holding initiation constant, do Collaborator vs Assistant tools differ in review/direct-resolution?",
        "",
        "## Human-initiated PR count by tool",
        "",
        "| Tool | n (human-init) |",
        "|------|----------------|",
    ]
    for tool in sorted(n_human_init_by_tool.keys()):
        n = n_human_init_by_tool[tool]
        lines.append(f"| {tool} | {n} |")
    lines.append("")
    lines.append("## First exit from PR created (human-initiated PRs only)")
    lines.append("")
    for tool in sorted(counts_by_tool_and_exit.keys()):
        ct = counts_by_tool_and_exit[tool]
        total = sum(ct.values())
        if total == 0:
            continue
        lines.append(f"### {tool} (n = {total})")
        lines.append("")
        for exit_key in ["review", "revision", "merged_and_closed", "unmerged_and_closed"]:
            c = ct.get(exit_key, 0)
            pct = 100.0 * c / total if total else 0
            lo, hi = wilson_interval(c, total)
            label = EXIT_LABELS.get(exit_key, exit_key)
            lines.append(f"- {label}: {c} ({pct:.1f}%, 95% CI [{100*lo:.1f}%, {100*hi:.1f}%])")
        lines.append("")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {md_path}")

    # Brief stdout summary
    print("")
    print("Human-initiated PRs by tool:")
    for tool in sorted(n_human_init_by_tool.keys()):
        n = n_human_init_by_tool[tool]
        ct = counts_by_tool_and_exit.get(tool, Counter())
        total_exits = sum(ct.values())
        to_review = ct.get("review", 0) + ct.get("revision", 0)
        to_merged = ct.get("merged_and_closed", 0)
        to_unmerged = ct.get("unmerged_and_closed", 0)
        if total_exits:
            pct_review = 100.0 * to_review / total_exits
            pct_direct_merged = 100.0 * to_merged / total_exits
            print(f"  {tool}: n={n}, →Review/Revision={pct_review:.1f}%, →Merged={pct_direct_merged:.1f}%")


if __name__ == "__main__":
    main()

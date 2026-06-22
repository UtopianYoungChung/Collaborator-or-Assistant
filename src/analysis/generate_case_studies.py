"""
Generate additional deterministic deep case studies for the evidence report.

This script selects:
1) An Assistant-paradigm Human-Led exemplar (from Claude, to keep runtime small)
2) A Collaborator-paradigm Agent-Autonomous exemplar (from Cursor, to keep runtime small)

Selections are deterministic and based on the canonical analyzer in `src.analysis.workflows`.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from src.analysis.workflows import (
    CollaborationType,
    PRWorkflow,
    WorkflowPhaseName,
    load_and_analyze_tool,
)


def _pr_number_from_url(url: str) -> Optional[str]:
    if "/pull/" not in url:
        return None
    try:
        return url.split("/pull/")[1].split("/")[0]
    except Exception:
        return None


def _title_from_workflow(w: PRWorkflow) -> str:
    if w.repo and w.url:
        n = _pr_number_from_url(w.url)
        if n:
            return f"{w.repo}#{n}"
    return w.repo or w.pr_id


def _phase_rows(w: PRWorkflow) -> List[str]:
    rows: List[str] = []
    for phase_name in [p.value for p in WorkflowPhaseName]:
        ph = w.phases.get(phase_name)
        if not ph or not ph.events:
            continue
        rows.append(
            f"| {phase_name.title()} | {len(ph.events)} | {ph.agent_count} | {ph.human_count} | "
            f"{ph.agent_weighted:.2f} | {ph.human_weighted:.2f} | {ph.primary_actor} |"
        )
    return rows


def _event_type_summary(w: PRWorkflow) -> str:
    a = Counter(e.event_type for e in w.events if e.is_agent)
    h = Counter(e.event_type for e in w.events if not e.is_agent)
    a_top = ", ".join(f"{k}={v}" for k, v in a.most_common(6))
    h_top = ", ".join(f"{k}={v}" for k, v in h.most_common(6))
    return f"- Agent event types (top): {a_top}\n- Human event types (top): {h_top}"


def render_case_study(w: PRWorkflow, label: str) -> str:
    a_w, h_w = w.get_weighted_scores()
    lines: List[str] = []
    lines.append(f"## Verified Case Study: {_title_from_workflow(w)} ({label})")
    lines.append("")
    if w.url:
        lines.append(f"**URL**: `{w.url}`")
        lines.append("")
    lines.append(
        f"This case study is computed from the {w.tool} dataset PR key `{w.pr_id}` "
        "using the canonical analyzer in `src.analysis.workflows`."
    )
    lines.append("")
    lines.append("### Phase breakdown (temporal assignment on observed event order)")
    lines.append("")
    lines.append("| Phase | Events | Agent events | Human events | Agent (weighted) | Human (weighted) | Primary actor |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    lines.extend(_phase_rows(w))
    lines.append("")
    lines.append("### Computed metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Classification** | {w.collaboration_type.value} |")
    lines.append(f"| **Total events** | {w.total_events} |")
    lines.append(f"| **Agent events / Human events** | {w.agent_total} / {w.human_total} |")
    lines.append(f"| **Weighted Collaboration Score** | {w.collaboration_score:.2f} (agent={a_w:.2f}, human={h_w:.2f}) |")
    lines.append(f"| **Revision cycles** | {w.revision_cycles} |")
    lines.append("")
    lines.append("### Event-type summary (counts)")
    lines.append("")
    lines.append(_event_type_summary(w))
    lines.append("")
    lines.append("### Visual evidence")
    lines.append("")
    lines.append(
        "A GitHub UI screenshot was not captured into this repository for this exemplar. "
        "The case study above is grounded in the dataset timeline items and the canonical analyzer output."
    )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def select_human_led_assistant(tool: str = "Claude") -> PRWorkflow:
    workflows = load_and_analyze_tool(tool, max_prs=None, ml_analyzer=None)
    candidates = [
        w
        for w in workflows
        if w.url
        and w.collaboration_type == CollaborationType.HUMAN_INITIATED_HUMAN_MERGED
        and w.agent_total > 0
        and w.human_total > 0
    ]
    # Deterministic: prefer more agent participation (still human-led), then higher balance, then stable id.
    candidates.sort(key=lambda w: (-w.agent_total, -w.collaboration_score, w.pr_id))
    if not candidates:
        raise RuntimeError(f"No suitable Human-Init + Human-Merged exemplar found for tool={tool}")
    return candidates[0]


def select_agent_autonomous_collaborator(tool: str = "Cursor") -> PRWorkflow:
    workflows = load_and_analyze_tool(tool, max_prs=None, ml_analyzer=None)
    candidates = [
        w
        for w in workflows
        if w.url
        and w.collaboration_type == CollaborationType.AGENT_INITIATED_AGENT_MERGED
        and w.agent_total > 0
    ]
    # Deterministic: prefer stronger autonomy (agent-human gap), then more events, then stable id.
    candidates.sort(key=lambda w: (-(w.agent_total - w.human_total), -w.total_events, w.pr_id))
    if not candidates:
        raise RuntimeError(f"No suitable Agent-Init + Agent-Merged exemplar found for tool={tool}")
    return candidates[0]


def main() -> None:
    p = argparse.ArgumentParser(prog="src.analysis.generate_case_studies")
    p.add_argument("--output", default=".tmp/additional_case_studies.md")
    args = p.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    human_led = select_human_led_assistant("Claude")
    autonomous = select_agent_autonomous_collaborator("Cursor")

    content = []
    content.append(render_case_study(human_led, label="Assistant paradigm, Human-Led"))
    content.append("---\n")
    content.append(render_case_study(autonomous, label="Collaborator paradigm, Agent-Autonomous"))
    out.write_text("".join(content).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()


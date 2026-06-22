"""
Within-repository control analysis (camera-ready Threats / Discussion).

Two repository qualifiers (see ``--repo-rule``):

- ``all_five_tools``: each of Cursor, Devin, Copilot, OpenAI, Claude has at least
  ``min-prs`` included PRs in the repository (verbatim reading of Threats:
  "each Collaborator and Assistant tool had at least five PRs").
- ``both_paradigms``: aggregate Collaborator-tool PR count ≥ ``min-prs`` and
  aggregate Assistant-tool PR count ≥ ``min-prs``.

Outputs PR-pooled initiation rates and, among **merged** PRs, the share whose
merge actor is Human (``resolver == "Human"`` in ``workflows.analyze_workflow``).

Run from repo root:
  python -m src.analysis.within_repository_analysis --min-prs 5 --repo-rule all_five_tools
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Literal, Tuple

from src.analysis.evidence_stats import DATASET_DIR, _iter_pr_event_lists
from src.analysis.workflows import FILES, analyze_workflow

COLLAB_TOOLS = frozenset({"Cursor", "Devin", "Copilot"})
ASSIST_TOOLS = frozenset({"OpenAI", "Claude"})

RepoRule = Literal["all_five_tools", "both_paradigms"]


def _iter_included_rows() -> List[Tuple[str, str, object]]:
    """Build list of (tool, repo, workflow) for included PRs (single pass over raw data)."""
    out: List[Tuple[str, str, object]] = []
    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        if not fp.exists():
            continue
        for pr_key, pr_events in _iter_pr_event_lists(fp):
            wf = analyze_workflow(pr_key, pr_events, tool, ml_analyzer=None)
            if wf.resolver_origin == "incomplete_timeline":
                continue
            repo = wf.repo
            if not repo:
                continue
            out.append((tool, repo, wf))
    return out


def _qualifying_repos(
    counts: Dict[str, Dict[str, int]],
    min_prs: int,
    repo_rule: RepoRule,
) -> List[str]:
    tools_all = list(FILES.keys())
    out: List[str] = []
    for r in counts:
        if repo_rule == "all_five_tools":
            ok = all(counts[r].get(t, 0) >= min_prs for t in tools_all)
        else:
            collab_n = sum(counts[r].get(t, 0) for t in COLLAB_TOOLS)
            assist_n = sum(counts[r].get(t, 0) for t in ASSIST_TOOLS)
            ok = collab_n >= min_prs and assist_n >= min_prs
        if ok:
            out.append(r)
    return sorted(out)


def run_analysis(min_prs: int, repo_rule: RepoRule) -> dict:
    rows = _iter_included_rows()
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for tool, repo, _wf in rows:
        counts[repo][tool] += 1

    qualifying_repos = _qualifying_repos(counts, min_prs, repo_rule)

    collab_rows = [(t, r, w) for t, r, w in rows if r in qualifying_repos and t in COLLAB_TOOLS]
    assist_rows = [(t, r, w) for t, r, w in rows if r in qualifying_repos and t in ASSIST_TOOLS]

    def agent_init_stats(wfs: List[Tuple[str, str, object]]) -> Tuple[int, int, float]:
        n = len(wfs)
        agent = sum(1 for _t, _r, w in wfs if w.initiator == "Agent")
        return agent, n, (agent / n * 100.0) if n else 0.0

    def human_merge_among_merged(wfs: List[Tuple[str, str, object]]) -> Tuple[int, int, float]:
        merged = [(t, r, w) for t, r, w in wfs if w.resolver_origin == "merged"]
        n = len(merged)
        human = sum(1 for _t, _r, w in merged if w.resolver == "Human")
        return human, n, (human / n * 100.0) if n else 0.0

    _ca, na, pa = agent_init_stats(collab_rows)
    _aa, nb, pb = agent_init_stats(assist_rows)
    _hg_a, nm_a, ph_a = human_merge_among_merged(collab_rows)
    _hg_b, nm_b, ph_b = human_merge_among_merged(assist_rows)

    gap_pp = round(pa - pb, 1) if na and nb else None

    return {
        "repo_rule": repo_rule,
        "min_prs": min_prs,
        "n_qualifying_repositories": len(qualifying_repos),
        "n_prs_collaborator_tools_in_qualifying_repos": na,
        "n_prs_assistant_tools_in_qualifying_repos": nb,
        "total_prs_in_analysis": na + nb,
        "collaborator_tools_agent_initiated_pct": round(pa, 1),
        "assistant_tools_agent_initiated_pct": round(pb, 1),
        "agent_initiated_gap_percentage_points": gap_pp,
        "collaborator_merged_human_resolver_pct": round(ph_a, 1),
        "collaborator_merged_n": nm_a,
        "assistant_merged_human_resolver_pct": round(ph_b, 1),
        "assistant_merged_n": nm_b,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Within-repository paradigm comparison.")
    parser.add_argument(
        "--min-prs",
        type=int,
        default=5,
        help="Minimum included PRs per repository under the selected rule.",
    )
    parser.add_argument(
        "--repo-rule",
        choices=("all_five_tools", "both_paradigms"),
        default="all_five_tools",
        help=(
            "all_five_tools: every tool has ≥min-prs (camera-ready Threats wording). "
            "both_paradigms: ≥min-prs Collaborator-tool PRs total and ≥min-prs Assistant-tool PRs total per repo."
        ),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(".tmp/within_repository_analysis.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(".tmp/within_repository_analysis.md"),
        help="Output Markdown path",
    )
    args = parser.parse_args()

    result = run_analysis(args.min_prs, args.repo_rule)  # type: ignore[arg-type]
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    if args.repo_rule == "all_five_tools":
        crit = (
            f"Each of the five tools has ≥{args.min_prs} included PRs in the repository "
            "(matches Threats wording: “each Collaborator and Assistant tool … at least five PRs”)."
        )
    else:
        crit = (
            f"Aggregate Collaborator-tool PRs ≥{args.min_prs} **and** aggregate Assistant-tool PRs ≥{args.min_prs} "
            "per repository."
        )

    lines = [
        "# Within-repository analysis (qualifying repos)",
        "",
        f"**Rule:** `{args.repo_rule}` — {crit}",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Qualifying repositories | {result['n_qualifying_repositories']} |",
        f"| PRs (Collaborator tools, in those repos) | {result['n_prs_collaborator_tools_in_qualifying_repos']} |",
        f"| PRs (Assistant tools, in those repos) | {result['n_prs_assistant_tools_in_qualifying_repos']} |",
        f"| **Total PRs** | **{result['total_prs_in_analysis']}** |",
        "",
        "## Initiation (agent-initiated share, PR-pooled)",
        "",
        f"- Collaborator tools: **{result['collaborator_tools_agent_initiated_pct']}%**",
        f"- Assistant tools: **{result['assistant_tools_agent_initiated_pct']}%**",
        f"- Gap (percentage points): **{result['agent_initiated_gap_percentage_points']}**",
        "",
        "## Merged PRs: human merge actor (resolver) share",
        "",
        f"- Collaborator tools: **{result['collaborator_merged_human_resolver_pct']}%** "
        f"(n = {result['collaborator_merged_n']})",
        f"- Assistant tools: **{result['assistant_merged_human_resolver_pct']}%** "
        f"(n = {result['assistant_merged_n']})",
        "",
        "*If `all_five_tools` yields zero qualifying repositories on your extract, try `both_paradigms` for "
        "diagnostics, or verify raw data matches the Figshare bundle.",
        "",
        f"Artifacts: `{args.out_json}`",
        "",
    ]
    args.out_md.write_text("\n".join(lines), encoding="utf-8")

    print("Within-repository analysis")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"  Wrote {args.out_json}")
    print(f"  Wrote {args.out_md}")


if __name__ == "__main__":
    main()

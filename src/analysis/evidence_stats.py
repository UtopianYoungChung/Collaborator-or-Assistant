"""
Evidence statistics generator (deterministic, grounded in `data/raw/`).

This module exists to close the loop between:
- reported headline numbers in `reports/evidence_report.md`
- the actual dataset under `data/raw/pr_timelines_*.json`
- the current canonical workflow analyzer (`src.analysis.workflows`)

Outputs:
- JSON summary (machine-checkable)
- Markdown snippet (human-readable) suitable for inclusion in the evidence report
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from src.analysis.stream_pr_timelines import iter_timeline_items
from src.analysis.workflows import (
    DATASET_DIR as WORKFLOW_DATASET_DIR,
    FILES,
    CollaborationType,
    SCENARIO_TYPES,
    analyze_workflow,
    get_actor_type,
    is_bot,
    is_agent_event,
)

EXCLUDED_LABEL = CollaborationType.EXCLUDED_NO_COMMIT_IN_TIMELINE.value


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = WORKFLOW_DATASET_DIR


def _iter_pr_event_lists(dataset_path: Path) -> Iterator[Tuple[str, List[dict]]]:
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


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """
    Wilson score interval for a binomial proportion.
    Returns (lo, hi) in [0, 1].
    """
    if n <= 0:
        return 0.0, 0.0
    z = _z_from_alpha(alpha)
    phat = k / n
    denom = 1.0 + (z * z) / n
    center = (phat + (z * z) / (2 * n)) / denom
    half = (z / denom) * math.sqrt((phat * (1 - phat) + (z * z) / (4 * n)) / n)
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return lo, hi


def _z_from_alpha(alpha: float) -> float:
    """
    Return the (1 - alpha/2) quantile of the standard normal.

    For the project’s current needs, we support alpha=0.05 (95% CI) exactly and
    fall back to an approximation otherwise.
    """
    if abs(alpha - 0.05) < 1e-12:
        return 1.959963984540054  # fixed 97.5th percentile
    # Approximation (Acklam inverse normal CDF)
    p = 1.0 - alpha / 2.0
    return _inv_norm_cdf(p)


def _inv_norm_cdf(p: float) -> float:
    # Peter J. Acklam's approximation.
    # Source not cited in-repo; included as a standard numerical method.
    # p must be in (0, 1).
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0, 1)")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def chi2_test(table: List[List[int]]) -> Tuple[float, int, float]:
    """
    Pearson chi-square test of independence.
    Returns (chi2, dof, p_value).
    """
    if not table or not table[0]:
        return 0.0, 0, 1.0
    r = len(table)
    c = len(table[0])
    row_sums = [sum(row) for row in table]
    col_sums = [sum(table[i][j] for i in range(r)) for j in range(c)]
    n = sum(row_sums)
    if n == 0:
        return 0.0, 0, 1.0
    chi2 = 0.0
    for i in range(r):
        for j in range(c):
            expected = (row_sums[i] * col_sums[j]) / n
            if expected > 0:
                diff = table[i][j] - expected
                chi2 += (diff * diff) / expected
    dof = (r - 1) * (c - 1)
    p = _chi2_sf(chi2, dof)
    return chi2, dof, p


def _chi2_sf(x: float, k: int) -> float:
    """Survival function for chi-square(k) at x."""
    if k <= 0:
        return 1.0
    return _gammaincc(0.5 * k, 0.5 * x)


def _gammaincc(a: float, x: float) -> float:
    """
    Regularized upper incomplete gamma Q(a, x).
    Numerical Recipes-style implementation (series / continued fraction).
    """
    if x < 0 or a <= 0:
        return 1.0
    if x == 0:
        return 1.0

    # Use series for P(a, x) when x < a+1, then Q = 1-P
    if x < a + 1.0:
        ap = a
        summ = 1.0 / a
        delt = summ
        for _ in range(1, 2000):
            ap += 1.0
            delt *= x / ap
            summ += delt
            if abs(delt) < abs(summ) * 1e-14:
                break
        p = summ * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))

    # Continued fraction for Q(a, x)
    b = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    q = h * math.exp(-x + a * math.log(x) - math.lgamma(a))
    return max(0.0, min(1.0, q))


@dataclass
class ActorTypeValidation:
    n_events_with_type: int
    n_events_missing_type: int
    # Confusion matrix comparing heuristic (pattern-based) vs actor.type
    # rows: true type (Bot/User), cols: predicted (Agent/Human)
    true_bot_pred_agent: int
    true_bot_pred_human: int
    true_user_pred_agent: int
    true_user_pred_human: int

    @property
    def heuristic_error_rate(self) -> float:
        n = self.n_events_with_type
        if n <= 0:
            return 0.0
        errors = self.true_bot_pred_human + self.true_user_pred_agent
        return errors / n


@dataclass
class EvidenceStats:
    totals_by_tool: Dict[str, int]
    counts_by_tool_and_type: Dict[str, Dict[str, int]]
    overall_counts_by_type: Dict[str, int]
    actor_type_validation: ActorTypeValidation
    chi2: float
    chi2_dof: int
    chi2_p_value: float
    cramers_v: float
    # Excluded cluster (no committed event in timeline); not part of the 6 scenarios
    excluded_by_tool: Dict[str, int]
    total_excluded: int
    # Unresolved PRs (no merged/closed): counts by tool and last_event_type for nuance
    unresolved_by_tool: Dict[str, int]
    unresolved_last_event_type: Dict[str, Dict[str, int]]  # tool -> event_type -> count


def compute_evidence_stats(exclude_incomplete: bool = False) -> EvidenceStats:
    totals_by_tool: Dict[str, int] = {}
    counts_by_tool_and_type: Dict[str, Dict[str, int]] = {}
    overall_counts: Counter[str] = Counter()

    # Actor-type validation (heuristic vs actor.type). Note: this intentionally
    # ignores the actor.type shortcut used in `is_agent_event`.
    n_with_type = 0
    n_missing_type = 0
    tb_pa = tb_ph = tu_pa = tu_ph = 0

    unresolved_by_tool: Dict[str, int] = {}
    unresolved_last_event_type: Dict[str, Counter[str]] = defaultdict(Counter)

    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        total = 0
        type_counts: Counter[str] = Counter()
        unresolved_by_tool[tool] = 0

        for pr_key, pr_events in _iter_pr_event_lists(fp):
            total += 1
            wf = analyze_workflow(pr_key, pr_events, tool, ml_analyzer=None)
            if exclude_incomplete and wf.resolver_origin == "incomplete_timeline":
                unresolved_by_tool[tool] += 1
                last_ev = wf.last_event_type or "none"
                unresolved_last_event_type[tool][last_ev] += 1
                continue  # Skip: do not count toward scenario taxonomy
            ctype = wf.collaboration_type.value
            type_counts[ctype] += 1
            overall_counts[ctype] += 1
            if wf.resolver_origin == "incomplete_timeline":
                unresolved_by_tool[tool] += 1
                last_ev = wf.last_event_type or "none"
                unresolved_last_event_type[tool][last_ev] += 1

            # Per-event actor-type validation pass
            for ev in pr_events:
                if not isinstance(ev, dict):
                    continue
                at = get_actor_type(ev)
                if at not in ("Bot", "User"):
                    n_missing_type += 1
                    continue
                n_with_type += 1
                # Heuristic prediction: patterns only
                actor_dict = ev.get("actor") or ev.get("author") or ev.get("user") or ev.get("committer")
                pred_agent = is_bot(actor_dict)
                if at == "Bot":
                    if pred_agent:
                        tb_pa += 1
                    else:
                        tb_ph += 1
                elif at == "User":
                    if pred_agent:
                        tu_pa += 1
                    else:
                        tu_ph += 1

        totals_by_tool[tool] = total
        counts_by_tool_and_type[tool] = dict(type_counts)

    # Chi-square test on tool × scenario (6 types only; excluded cluster not included)
    tools = list(FILES.keys())
    scenario_type_values = [ct.value for ct in SCENARIO_TYPES]
    excluded_by_tool_dict: Dict[str, int] = {
        tool: counts_by_tool_and_type.get(tool, {}).get(EXCLUDED_LABEL, 0) for tool in tools
    }
    total_excluded = sum(excluded_by_tool_dict.values())

    table: List[List[int]] = []
    for tool in tools:
        row = [counts_by_tool_and_type.get(tool, {}).get(t, 0) for t in scenario_type_values]
        table.append(row)
    chi2, dof, p = chi2_test(table)
    n_included = sum(sum(row) for row in table)
    # Cramér's V effect size for an r×c contingency table (included PRs only).
    denom = n_included * max(1, min(len(tools) - 1, len(scenario_type_values) - 1))
    cramers_v = math.sqrt(chi2 / denom) if denom > 0 else 0.0

    # Convert Counter to dict for JSON
    unresolved_let: Dict[str, Dict[str, int]] = {
        tool: dict(ct) for tool, ct in unresolved_last_event_type.items()
    }

    return EvidenceStats(
        totals_by_tool=totals_by_tool,
        counts_by_tool_and_type=counts_by_tool_and_type,
        overall_counts_by_type=dict(overall_counts),
        actor_type_validation=ActorTypeValidation(
            n_events_with_type=n_with_type,
            n_events_missing_type=n_missing_type,
            true_bot_pred_agent=tb_pa,
            true_bot_pred_human=tb_ph,
            true_user_pred_agent=tu_pa,
            true_user_pred_human=tu_ph,
        ),
        chi2=chi2,
        chi2_dof=dof,
        chi2_p_value=p,
        cramers_v=cramers_v,
        excluded_by_tool=excluded_by_tool_dict,
        total_excluded=total_excluded,
        unresolved_by_tool=dict(unresolved_by_tool),
        unresolved_last_event_type=unresolved_let,
    )


def render_markdown(stats: EvidenceStats, alpha: float = 0.05) -> str:
    tools = list(FILES.keys())
    scenario_types = [ct.value for ct in SCENARIO_TYPES]

    lines: List[str] = []
    w = lines.append

    w("## Deterministic evidence statistics (generated from `data/raw/`)")
    w("")
    w("This section is generated by `python -m src.analysis.evidence_stats` using the current canonical workflow analyzer (`src.analysis.workflows`).")
    w("")

    # Totals
    w("### Dataset totals")
    w("")
    w("| Tool | Total PRs |")
    w("|---|---:|")
    total_all = 0
    for tool in tools:
        n = stats.totals_by_tool.get(tool, 0)
        total_all += n
        w(f"| {tool} | {n:,} |")
    w(f"| **TOTAL** | **{total_all:,}** |")
    w("")

    # Excluded cluster (not a scenario; outliers/noise)
    w("### Excluded cluster (not part of scenario taxonomy)")
    w("")
    w("PRs with no `committed` event in the timeline are excluded from the 6-scenario taxonomy (outliers/noise) and reported separately.")
    w("")
    w("| Tool | Excluded (No-Commit in Timeline) | % of tool |")
    w("|---|---:|---:|")
    for tool in tools:
        n = stats.totals_by_tool.get(tool, 0)
        exc = getattr(stats, "excluded_by_tool", {}).get(tool, 0)
        pct = (100.0 * exc / n) if n else 0.0
        w(f"| {tool} | {exc:,} | {pct:.1f}% |")
    total_exc = getattr(stats, "total_excluded", 0)
    pct_all = (100.0 * total_exc / total_all) if total_all else 0.0
    w(f"| **Total** | **{total_exc:,}** | **{pct_all:.1f}%** |")
    w("")
    n_included = sum(
        sum(stats.counts_by_tool_and_type.get(t, {}).get(ct, 0) for ct in scenario_types)
        for t in tools
    )
    w(f"**Included PRs (used for scenario analysis)**: {n_included:,}")
    w("")

    # Distribution with CIs (6 scenarios only)
    w("### Collaboration type distribution (6 scenarios; with 95% Wilson CIs)")
    w("")
    w("| Tool | Type | Count | Percent | 95% CI |")
    w("|---|---|---:|---:|---|")
    for tool in tools:
        counts = stats.counts_by_tool_and_type.get(tool, {})
        n_incl = sum(counts.get(t, 0) for t in scenario_types)  # denominator = PRs in 6 scenarios
        for t in scenario_types:
            k = stats.counts_by_tool_and_type.get(tool, {}).get(t, 0)
            pct = (100.0 * k / n_incl) if n_incl else 0.0
            lo, hi = wilson_interval(k, n_incl, alpha=alpha)
            w(f"| {tool} | {t} | {k:,} | {pct:.1f}% | [{100*lo:.1f}%, {100*hi:.1f}%] |")
    w("")

    # Chi-square test (on included PRs, 6 scenarios only)
    w("### Tool × collaboration-type association (chi-square test; 6 scenarios, included PRs only)")
    w("")
    w(f"- **Chi-square**: {stats.chi2:.3f}")
    w(f"- **Degrees of freedom**: {stats.chi2_dof}")
    w(f"- **p-value**: {stats.chi2_p_value:.6g}")
    w(f"- **Cramér's V**: {stats.cramers_v:.4f}")
    w("")

    # Actor-type heuristic validation
    v = stats.actor_type_validation
    w("### Bot/Agent detection validation (heuristic vs dataset actor.type)")
    w("")
    w("This checks the **pattern-based heuristic** (`BOT_PATTERNS`) against `actor.type` fields in the dataset (where present).")
    w("")
    w(f"- **Events with actor.type in {{Bot, User}}**: {v.n_events_with_type:,}")
    w(f"- **Events missing/other actor.type**: {v.n_events_missing_type:,}")
    w(f"- **Heuristic error rate (on typed events)**: {100*v.heuristic_error_rate:.3f}%")
    w("")
    w("| True actor.type | Pred=Agent | Pred=Human |")
    w("|---|---:|---:|")
    w(f"| Bot | {v.true_bot_pred_agent:,} | {v.true_bot_pred_human:,} |")
    w(f"| User | {v.true_user_pred_agent:,} | {v.true_user_pred_human:,} |")
    w("")

    # Incomplete timeline PRs (no merged/closed): nuance via last_event_type
    w("### Incomplete Timeline PRs (no terminal event)")
    w("")
    w("PRs with no `merged` or `closed` event have resolver = No resolver and **resolver_origin** = \"incomplete_timeline\". Below: counts by tool and top **last_event_type** (how the observed activity ended) for insight.")
    w("")
    w("| Tool | Incomplete Timeline | % of tool |")
    w("|---|---:|---:|")
    total_unresolved = 0
    for tool in tools:
        n = stats.totals_by_tool.get(tool, 0)
        u = getattr(stats, "unresolved_by_tool", {}).get(tool, 0)
        total_unresolved += u
        pct = (100.0 * u / n) if n else 0.0
        w(f"| {tool} | {u:,} | {pct:.1f}% |")
    n_all = sum(stats.totals_by_tool.get(t, 0) for t in tools)
    pct_all = (100.0 * total_unresolved / n_all) if n_all else 0.0
    w(f"| **Total** | **{total_unresolved:,}** | **{pct_all:.1f}%** |")
    w("")
    let_by_tool = getattr(stats, "unresolved_last_event_type", {})
    if let_by_tool:
        agg: Counter[str] = Counter()
        for tool, ev_counts in let_by_tool.items():
            for ev, c in ev_counts.items():
                agg[ev] += c
        w("**Top last_event_type when incomplete_timeline (all tools)**:")
        w("")
        for ev, c in agg.most_common(10):
            w(f"- `{ev}`: {c:,}")
        w("")

    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(prog="src.analysis.evidence_stats")
    p.add_argument("--out-json", default=".tmp/evidence_stats.json", help="Where to write JSON summary")
    p.add_argument("--out-md", default=".tmp/evidence_stats.md", help="Where to write markdown snippet")
    p.add_argument("--include-incomplete", action="store_true", help="Include PRs with no merged/closed event (default: exclude; incomplete timelines add no value)")
    args = p.parse_args()

    stats = compute_evidence_stats(exclude_incomplete=not args.include_incomplete)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(asdict(stats), indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(stats), encoding="utf-8")

    # Also generate outcome statistics
    try:
        from src.analysis.outcome_analysis import load_all_workflows, generate_outcome_report
        print("Generating outcome statistics...", file=__import__('sys').stderr)
        workflows = load_all_workflows()
        out_outcome = Path(".tmp/outcome_stats.md")
        generate_outcome_report(workflows, out_outcome)
        print(json.dumps({"json": str(out_json), "md": str(out_md), "outcome": str(out_outcome)}, indent=2))
    except ImportError:
        print(json.dumps({"json": str(out_json), "md": str(out_md)}, indent=2))


if __name__ == "__main__":
    main()


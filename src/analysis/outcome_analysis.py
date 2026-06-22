"""
Outcome Analysis Module for AIDev Research

Computes outcome measures (merge rate, duration, review iterations)
grouped by collaboration type, enabling claims linking patterns to quality.
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import math

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from src.analysis.workflows import (
    verify_scenario_mutual_exclusivity,
    PRWorkflow, CollaborationType, load_and_analyze_tool, FILES
)


@dataclass
class OutcomeStats:
    """Outcome statistics for a group of PRs."""
    count: int
    merged_count: int
    merge_rate: float
    merge_rate_ci_low: float
    merge_rate_ci_high: float
    
    mean_commits: float
    median_commits: float
    
    mean_changes_requested: float
    median_changes_requested: float
    
    mean_revision_cycles: float
    median_revision_cycles: float
    
    mean_reviews: float
    median_reviews: float
    
    # Duration (may have missing data)
    duration_count: int  # PRs with valid duration
    mean_duration_hours: Optional[float]
    median_duration_hours: Optional[float]

    # Median phase durations (days)
    median_pr_created_days: float = 0.0
    median_review_days: float = 0.0
    median_revision_days: float = 0.0


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Compute Wilson score confidence interval for a proportion.
    """
    if trials == 0:
        return (0.0, 0.0)
    
    z = 1.96 if confidence == 0.95 else 1.645  # 95% or 90%
    p = successes / trials
    
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials) / denominator
    
    return (max(0.0, center - spread), min(1.0, center + spread))


def median(values: List[float]) -> float:
    """Compute median of a list."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n % 2 == 0:
        return (sorted_v[n//2 - 1] + sorted_v[n//2]) / 2
    return sorted_v[n//2]


def mean(values: List[float]) -> float:
    """Compute mean of a list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_outcome_stats(workflows: List[PRWorkflow]) -> OutcomeStats:
    """Compute outcome statistics for a list of workflows."""
    n = len(workflows)
    if n == 0:
        return OutcomeStats(
            count=0, merged_count=0, merge_rate=0.0,
            merge_rate_ci_low=0.0, merge_rate_ci_high=0.0,
            mean_commits=0.0, median_commits=0.0,
            mean_changes_requested=0.0, median_changes_requested=0.0,
            mean_revision_cycles=0.0, median_revision_cycles=0.0,
            mean_reviews=0.0, median_reviews=0.0,
            duration_count=0, mean_duration_hours=None, median_duration_hours=None
        )
    
    merged_count = sum(1 for w in workflows if w.is_merged)
    merge_rate = merged_count / n
    ci_low, ci_high = wilson_ci(merged_count, n)
    
    commits = [w.commit_count for w in workflows]
    changes_req = [w.changes_requested_count for w in workflows]
    rev_cycles = [w.revision_cycles for w in workflows]
    reviews = [w.review_count for w in workflows]
    
    durations = [w.duration_hours for w in workflows if w.duration_hours is not None]
    
    # Phase durations (days)
    # Note: phase_durations is in hours
    pr_created_days = [w.phase_durations.get('pr_created', 0.0) / 24.0 for w in workflows]
    rev_days = [w.phase_durations.get('review', 0.0) / 24.0 for w in workflows]
    revn_days = [w.phase_durations.get('revision', 0.0) / 24.0 for w in workflows]

    return OutcomeStats(
        count=n,
        merged_count=merged_count,
        merge_rate=merge_rate,
        merge_rate_ci_low=ci_low,
        merge_rate_ci_high=ci_high,
        mean_commits=mean(commits),
        median_commits=median(commits),
        mean_changes_requested=mean(changes_req),
        median_changes_requested=median(changes_req),
        mean_revision_cycles=mean(rev_cycles),
        median_revision_cycles=median(rev_cycles),
        mean_reviews=mean(reviews),
        median_reviews=median(reviews),
        duration_count=len(durations),
        mean_duration_hours=mean(durations) if durations else None,
        median_duration_hours=median(durations) if durations else None,
        median_pr_created_days=median(pr_created_days),
        median_review_days=median(rev_days),
        median_revision_days=median(revn_days)
    )


def compute_outcome_stats_by_type(
    workflows: List[PRWorkflow]
) -> Dict[str, OutcomeStats]:
    """
    Compute outcome statistics grouped by collaboration type.
    
    Returns:
        Dict mapping collaboration type name to OutcomeStats
    """
    grouped: Dict[str, List[PRWorkflow]] = defaultdict(list)
    for w in workflows:
        grouped[w.collaboration_type.value].append(w)
    
    return {type_name: compute_outcome_stats(wfs) for type_name, wfs in grouped.items()}


def chi_square_merge_by_type(
    stats_by_type: Dict[str, OutcomeStats]
) -> Tuple[float, float, int]:
    """
    Chi-square test for merge outcome × collaboration type.
    
    Returns:
        (chi2_statistic, p_value, degrees_of_freedom)
    """
    if not SCIPY_AVAILABLE:
        return (0.0, 1.0, 0)
    
    # Build contingency table: rows = types, cols = [merged, not_merged]
    observed = []
    for type_name in sorted(stats_by_type.keys()):
        s = stats_by_type[type_name]
        merged = s.merged_count
        not_merged = s.count - s.merged_count
        if s.count > 0:  # Only include non-empty types
            observed.append([merged, not_merged])
    
    if len(observed) < 2:
        return (0.0, 1.0, 0)
    
    chi2, p, dof, expected = stats.chi2_contingency(observed)
    return (chi2, p, dof)


def kruskal_wallis_duration_by_type(
    workflows: List[PRWorkflow]
) -> Tuple[float, float]:
    """
    Kruskal-Wallis H-test for duration across collaboration types.
    
    Returns:
        (H_statistic, p_value)
    """
    if not SCIPY_AVAILABLE:
        return (0.0, 1.0)
    
    grouped: Dict[str, List[float]] = defaultdict(list)
    for w in workflows:
        if w.duration_hours is not None:
            grouped[w.collaboration_type.value].append(w.duration_hours)
    
    # Need at least 2 groups with data
    groups = [v for v in grouped.values() if len(v) >= 5]
    if len(groups) < 2:
        return (0.0, 1.0)
    
    H, p = stats.kruskal(*groups)
    return (H, p)


def generate_outcome_report(
    workflows: List[PRWorkflow],
    output_path: Optional[Path] = None
) -> str:
    """Generate a markdown report of outcome statistics."""
    stats_by_type = compute_outcome_stats_by_type(workflows)
    chi2, p_chi2, dof = chi_square_merge_by_type(stats_by_type)
    H, p_kw = kruskal_wallis_duration_by_type(workflows)
    
    lines = []
    lines.append("## Outcome Measures by Collaboration Type\n")
    lines.append("| Type | n | Merged | Merge Rate | 95% CI | Mean Commits | Mean Reviews | Mean Duration (h) |")
    lines.append("|------|---|--------|------------|--------|--------------|--------------|-------------------|")
    
    # Sort by collaboration type priority
    type_order = [ct.value for ct in CollaborationType]
    for type_name in type_order:
        if type_name not in stats_by_type:
            continue
        s = stats_by_type[type_name]
        dur_str = f"{s.mean_duration_hours:.1f}" if s.mean_duration_hours else "N/A"
        lines.append(
            f"| {type_name} | {s.count:,} | {s.merged_count:,} | "
            f"{s.merge_rate*100:.1f}% | [{s.merge_rate_ci_low*100:.1f}%, {s.merge_rate_ci_high*100:.1f}%] | "
            f"{s.mean_commits:.1f} | {s.mean_reviews:.1f} | {dur_str} |"
        )
    
    lines.append("")
    lines.append("### Median Phase Durations (days)\n")
    lines.append("| Type | PR created | Review | Revision |")
    lines.append("|------|------------|--------|----------|")
    
    for type_name in type_order:
        if type_name not in stats_by_type:
            continue
        s = stats_by_type[type_name]
        lines.append(
            f"| {type_name} | {s.median_pr_created_days:.2f} | "
            f"{s.median_review_days:.2f} | {s.median_revision_days:.2f} |"
        )

    lines.append("")
    lines.append("### Statistical Tests\n")
    lines.append(f"- **Merge outcome × type chi-square**: χ²={chi2:.2f}, df={dof}, p={p_chi2:.4g}")
    lines.append(f"- **Duration × type Kruskal-Wallis**: H={H:.2f}, p={p_kw:.4g}")
    
    if SCIPY_AVAILABLE:
        lines.append("")
        lines.append("*Tests computed with scipy.stats*")
    else:
        lines.append("")
        lines.append("> [!WARNING]")
        lines.append("> scipy not available; statistical tests returned placeholder values.")
    
    report = "\n".join(lines)
    
    if output_path:
        output_path.write_text(report, encoding='utf-8')
    
    return report


def load_all_workflows() -> List[PRWorkflow]:
    """Load all workflows from all tools."""
    all_workflows = []
    for tool in FILES.keys():
        print(f"Loading {tool}...", file=sys.stderr)
        all_workflows.extend(load_and_analyze_tool(tool))
    return all_workflows


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Outcome analysis for AIDev workflows')
    parser.add_argument('--output', type=str, default='.tmp/outcome_stats.md',
                        help='Output path for markdown report')
    parser.add_argument('--validate', action='store_true',
                        help='Run validation checks')
    args = parser.parse_args()
    
    print("Loading all workflows...", file=sys.stderr)
    workflows = load_all_workflows()
    print(f"Loaded {len(workflows)} workflows", file=sys.stderr)
    
    if args.validate:
        # Sanity checks
        merged = sum(1 for w in workflows if w.is_merged)
        closed = sum(1 for w in workflows if w.is_closed)
        print(f"Merged: {merged}")
        print(f"Closed (any): {closed}")
        print(f"Closed without merge: {closed - merged}")
        
        # Check per-type sums (redundant with exclusivity check but kept for clarity)
        stats_by_type = compute_outcome_stats_by_type(workflows)
        total = sum(s.count for s in stats_by_type.values())
        print(f"Sum of per-type counts: {total} (expected: {len(workflows)})")
        assert total == len(workflows), "Count mismatch!"
        
        # 100% scenario mutual exclusivity: no overcounts; each PR counted exactly once
        exclusivity = verify_scenario_mutual_exclusivity(workflows, raise_on_fail=True)
        print(f"Scenario mutual exclusivity: sum_by_type={exclusivity['sum_by_type']} total={exclusivity['total']}")
        print("✓ Validation passed (including scenario mutual exclusivity)")
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = generate_outcome_report(workflows, output_path)
        print(report)
        print(f"\nReport saved to {output_path}", file=sys.stderr)

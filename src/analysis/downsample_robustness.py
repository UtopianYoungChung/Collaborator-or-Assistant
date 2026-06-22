"""
Downsampling robustness check: randomly sample OpenAI PRs to match Copilot sample size,
recompute tool × scenario contingency table, χ² and Cramér's V.

Addresses reviewer concern that the paradigm bifurcation may be driven by OpenAI's
large sample size. If the bifurcation holds after downsampling, the result strengthens
the paper; if not, the authors need to know before submission.

Run from repo root:
  python -m src.analysis.downsample_robustness [--n-match 4885] [--seeds 10]  # default seeds=10
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

from src.analysis.evidence_stats import (
    DATASET_DIR,
    _iter_pr_event_lists,
    chi2_test,
    compute_evidence_stats,
)
from src.analysis.workflows import (
    FILES,
    CollaborationType,
    SCENARIO_TYPES,
    analyze_workflow,
)

EXCLUDED_LABEL = CollaborationType.EXCLUDED_NO_COMMIT_IN_TIMELINE.value
SCENARIO_VALUES = [ct.value for ct in SCENARIO_TYPES]


def collect_openai_included_types_list() -> List[str]:
    """
    Stream OpenAI PRs once; return list of collaboration_type for included PRs only.
    Caller can then sample from this list for each seed without re-streaming.
    """
    openai_file = FILES.get("OpenAI")
    if not openai_file:
        raise FileNotFoundError("OpenAI not in FILES")
    fp = DATASET_DIR / openai_file
    if not fp.exists():
        raise FileNotFoundError(fp)

    included_types: List[str] = []
    for pr_key, pr_events in _iter_pr_event_lists(fp):
        wf = analyze_workflow(pr_key, pr_events, "OpenAI", ml_analyzer=None)
        if wf.resolver_origin == "incomplete_timeline":
            continue
        ctype = wf.collaboration_type.value
        if ctype == EXCLUDED_LABEL:
            continue
        included_types.append(ctype)
    return included_types


def sample_openai_types(included_types: List[str], n_match: int, seed: int) -> List[str]:
    """Sample n_match types from included_types without replacement."""
    rng = random.Random(seed)
    k = min(n_match, len(included_types))
    if k == 0:
        return []
    indices = rng.sample(range(len(included_types)), k)
    return [included_types[i] for i in indices]


def count_by_scenario(type_list: List[str]) -> Dict[str, int]:
    """Count occurrences of each scenario type; return dict with all 6 keys."""
    from collections import Counter
    counts = Counter(type_list)
    return {t: counts.get(t, 0) for t in SCENARIO_VALUES}


def run_one_seed(
    full_stats,
    openai_included_types: List[str],
    n_match: int,
    seed: int,
) -> Tuple[float, int, float, float, Dict[str, int], bool]:
    """
    Run one downsampling trial. Returns (chi2, dof, p_value, cramers_v, openai_row, bifurcation_holds).
    Bifurcation: OpenAI remains Assistant (≥90% human-init); Collaborator tools unchanged.
    """
    openai_sample_types = sample_openai_types(openai_included_types, n_match, seed)
    openai_row = count_by_scenario(openai_sample_types)

    tools = list(FILES.keys())
    scenario_type_values = SCENARIO_VALUES
    table: List[List[int]] = []
    for tool in tools:
        if tool == "OpenAI":
            row = [openai_row.get(t, 0) for t in scenario_type_values]
        else:
            row = [
                full_stats.counts_by_tool_and_type.get(tool, {}).get(t, 0)
                for t in scenario_type_values
            ]
        table.append(row)

    chi2, dof, p = chi2_test(table)
    n_included = sum(sum(r) for r in table)
    denom = n_included * max(1, min(len(tools) - 1, len(scenario_type_values) - 1))
    cramers_v = math.sqrt(chi2 / denom) if denom > 0 else 0.0

    # Bifurcation: OpenAI row should be ≥90% human-init (S4+S5+S6)
    openai_total = sum(openai_row.values())
    human_init = (
        openai_row.get(CollaborationType.HUMAN_INITIATED_HUMAN_MERGED.value, 0)
        + openai_row.get(CollaborationType.HUMAN_INITIATED_AGENT_MERGED.value, 0)
        + openai_row.get(CollaborationType.HUMAN_INITIATED_NOT_MERGED.value, 0)
    )
    bifurcation_holds = openai_total == 0 or (human_init / openai_total) >= 0.90

    return chi2, dof, p, cramers_v, openai_row, bifurcation_holds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Downsample OpenAI to match Copilot; recompute Cramér's V and check bifurcation."
    )
    parser.add_argument(
        "--n-match",
        type=int,
        default=4885,
        help="Target sample size for OpenAI (default: Copilot included count 4885)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=10,
        help="Number of random seeds to run (default: 10; matches camera-ready Threats)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp/downsample_robustness.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    # Full stats once (for other tools' rows); OpenAI included types once (stream once)
    full_stats = compute_evidence_stats(exclude_incomplete=True)
    full_cramers_v = full_stats.cramers_v
    openai_included_types = collect_openai_included_types_list()

    results: List[dict] = []
    cramers_v_list: List[float] = []
    bifurcation_holds_list: List[bool] = []

    for seed in range(args.seeds):
        chi2, dof, p, cramers_v, openai_row, bifurcation_holds = run_one_seed(
            full_stats, openai_included_types, args.n_match, seed
        )
        cramers_v_list.append(cramers_v)
        bifurcation_holds_list.append(bifurcation_holds)
        results.append({
            "seed": seed,
            "chi2": round(chi2, 4),
            "dof": dof,
            "p_value": p,
            "cramers_v": round(cramers_v, 4),
            "openai_row_sum": sum(openai_row.values()),
            "bifurcation_holds": bifurcation_holds,
        })

    out = {
        "full_dataset_cramers_v": round(full_cramers_v, 4),
        "n_match": args.n_match,
        "seeds": args.seeds,
        "runs": results,
        "cramers_v_min": round(min(cramers_v_list), 4) if cramers_v_list else None,
        "cramers_v_max": round(max(cramers_v_list), 4) if cramers_v_list else None,
        "cramers_v_mean": round(sum(cramers_v_list) / len(cramers_v_list), 4) if cramers_v_list else None,
        "bifurcation_holds_all_seeds": all(bifurcation_holds_list),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)

    print("Downsampling robustness check")
    print(f"  Full dataset Cramér's V: {full_cramers_v:.4f}")
    print(f"  OpenAI downsampled to n = {args.n_match} (Copilot size)")
    print(f"  Seeds: {args.seeds}")
    print(f"  Cramér's V (downsampled): min = {min(cramers_v_list):.4f}, max = {max(cramers_v_list):.4f}, mean = {sum(cramers_v_list)/len(cramers_v_list):.4f}")
    print(f"  Bifurcation holds (OpenAI ≥90%% human-init) all seeds: {out['bifurcation_holds_all_seeds']}")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()

"""
Generate a stacked bar chart of collaboration type distribution by tool.

Reads from .tmp/evidence_stats.json. The default pipeline excludes incomplete timelines
(29,585 included PRs). Run: python -m src.analysis.evidence_stats (exclude-incomplete is default).
Uses the 6 scenario types (S1–S6); excluded cluster is not shown (percentages are of included PRs per tool).
Output: assets/collaboration_type_distribution_by_tool.png, AIWare2026_CameraReady_Package/figures/fig_collab_distribution.pdf
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = REPO_ROOT / ".tmp" / "evidence_stats.json"
OUTPUT_PATH = REPO_ROOT / "assets" / "collaboration_type_distribution_by_tool.png"
SUBMISSIONS_PDF = REPO_ROOT / "AIWare2026_CameraReady_Package" / "figures" / "fig_collab_distribution.pdf"

# 6 scenarios (S1–S6); must match SCENARIO_TYPES after running evidence_stats (merge-focused)
SCENARIO_ORDER = [
    "Agent-Init + Human-Merged",
    "Agent-Init + Agent-Merged",
    "Agent-Init + Not-Merged",
    "Human-Init + Human-Merged",
    "Human-Init + Agent-Merged",
    "Human-Init + Not-Merged",
]
# Legacy: if JSON still has old taxonomy keys, use this order for the stacked bars
OLD_SCENARIO_ORDER = [
    "Agent-Initiated + Human-Resolved",
    "Human-Initiated + Agent-Assisted",
    "Agent-Autonomous",
    "Human-Led",
    "Balanced Collaboration",
    "Unclassified",
]
EXCLUDED_LABEL = "Excluded: No-Commit in Timeline"
# Match manuscript Table 3 row order (Collaborator then Assistant)
TOOL_ORDER = ["Cursor", "Devin", "Copilot", "Claude", "OpenAI"]

# Colors (stacked order, bottom to top; 6 scenarios)
COLORS = [
    "#e74c3c",  # red
    "#e67e22",  # orange
    "#f1c40f",  # yellow
    "#27ae60",  # green
    "#3498db",  # blue
    "#9b59b6",  # purple
]


def main() -> None:
    parser = argparse.ArgumentParser(prog="src.analysis.plot_collaboration_distribution")
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Use evidence_stats.json with incomplete PRs included (default: excluded; n=29,585)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        help="Override n in title (default: computed from data = 29,585)",
    )
    args = parser.parse_args()
    evidence_json = DEFAULT_EVIDENCE if not args.include_incomplete else REPO_ROOT / ".tmp" / "evidence_stats_include_incomplete.json"
    if not evidence_json.exists():
        raise FileNotFoundError(
            f"Run first: python -m src.analysis.evidence_stats"
            + (" --include-incomplete --out-json .tmp/evidence_stats_include_incomplete.json" if args.include_incomplete else "")
            + f"\nMissing: {evidence_json}"
        )
    data = json.loads(evidence_json.read_text(encoding="utf-8"))
    totals_by_tool = data["totals_by_tool"]
    counts_by_tool_and_type = data["counts_by_tool_and_type"]
    excluded_by_tool = data.get("excluded_by_tool", {})
    # Included = PRs with terminal outcomes used in the 6-scenario distribution
    overall = data.get("overall_counts_by_type", {})
    n_included = sum(
        overall.get(k, 0) for k in SCENARIO_ORDER
        if k in overall and k != EXCLUDED_LABEL
    )
    if n_included == 0:
        n_included = sum(totals_by_tool.get(t, 0) for t in TOOL_ORDER) - sum(excluded_by_tool.values())
    if args.n is not None:
        n_included = args.n

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise ImportError("matplotlib is required. Install with: pip install matplotlib") from None

    # Use new 6 scenarios if present in data; else fall back to old taxonomy keys
    first_tool = next(iter(counts_by_tool_and_type), None)
    type_keys = list(counts_by_tool_and_type.get(first_tool, {}).keys()) if first_tool else []
    if any(t in type_keys for t in SCENARIO_ORDER):
        order = [t for t in SCENARIO_ORDER if t in (type_keys or [])]
        if len(order) < 6:
            order = [t for t in SCENARIO_ORDER]
    else:
        order = [t for t in OLD_SCENARIO_ORDER if t in (type_keys or [])]
        if not order:
            order = OLD_SCENARIO_ORDER

    # Build matrix: tools x scenario types (percentages; use included PRs if excluded present)
    tool_labels = [t for t in TOOL_ORDER if t in totals_by_tool]
    if not tool_labels:
        tool_labels = list(totals_by_tool.keys())

    num_tools = len(tool_labels)
    num_types = len(order)
    pct_matrix = np.zeros((num_types, num_tools))

    unresolved_by_tool = data.get("unresolved_by_tool", {})
    for j, tool in enumerate(tool_labels):
        total = totals_by_tool.get(tool, 0)
        excluded = excluded_by_tool.get(tool, 0)
        unresolved = unresolved_by_tool.get(tool, 0) if unresolved_by_tool else 0
        included = max(1, total - excluded - unresolved)
        denom = included if (excluded_by_tool or unresolved_by_tool) else total
        if denom <= 0:
            denom = total or 1
        for i, ctype in enumerate(order):
            count = counts_by_tool_and_type.get(tool, {}).get(ctype, 0)
            pct_matrix[i, j] = 100.0 * count / denom

    # Stacked bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#fffef5")
    ax.set_facecolor("#fffef5")

    x = np.arange(num_tools)
    width = 0.65
    bottom = np.zeros(num_tools)

    # Stack bottoms per tool (num_types+1 x num_tools): row i is bottom of segment i
    stack_bottom = np.zeros((num_types + 1, num_tools))
    for i in range(num_types):
        stack_bottom[i + 1] = stack_bottom[i] + pct_matrix[i]

    # For each tool, indices of the top two segments by percentage (for labels only)
    top_two_per_tool = {}
    for j in range(num_tools):
        order_by_pct = np.argsort(pct_matrix[:, j])[::-1]
        top_two = [idx for idx in order_by_pct if pct_matrix[idx, j] > 0][:2]
        top_two_per_tool[j] = set(top_two)

    for i, (ctype, color) in enumerate(zip(order, COLORS)):
        ax.bar(x, pct_matrix[i], width, label=ctype, bottom=stack_bottom[i], color=color, edgecolor="white", linewidth=0.5)
        # Percentage labels: only for the top two segments per tool
        for j in range(num_tools):
            if i not in top_two_per_tool[j]:
                continue
            pct = pct_matrix[i, j]
            if pct <= 0:
                continue
            mid_y = stack_bottom[i, j] + pct / 2
            if pct >= 6:
                # Label inside segment; use white or black for contrast
                r, g, b = int(color[1:3], 16) / 255, int(color[3:5], 16) / 255, int(color[5:7], 16) / 255
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                textcolor = "black" if lum > 0.6 else "white"
                ax.text(x[j], mid_y, f"{pct:.1f}%", ha="center", va="center", fontsize=7, color=textcolor, fontweight="medium")
            else:
                # Thin segment: label just above so proportion is visible
                ax.text(x[j], stack_bottom[i, j] + pct, f"{pct:.1f}%", ha="center", va="bottom", fontsize=6, color="black")

    ax.set_ylabel("Percentage of PRs", fontsize=11)
    ax.set_xlabel("Tool", fontsize=11)
    ax.set_title(f"Interaction Scenario Type Distribution by Tool (n={n_included:,})", fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(tool_labels)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    # Legend below the chart to avoid overflowing into the second column (two-column layout)
    ax.legend(
        title="Collaboration Type",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=3,
        fontsize=8,
        frameon=True,
    )
    ax.yaxis.grid(True, linestyle="-", color="white", linewidth=1)
    ax.set_axisbelow(True)
    plt.tight_layout(rect=[0, 0, 1, 1])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    # PDF for manuscript Figure 3 (camera-ready package)
    SUBMISSIONS_PDF.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(SUBMISSIONS_PDF, format="pdf", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {SUBMISSIONS_PDF}")


if __name__ == "__main__":
    main()

"""
Generate five PR workflow state machine diagrams with transition probabilities
and median hours per state/transition.

State machine (canonical): PR created → Review ⇄ Revision → Merged and closed
| Unmerged and closed. No Initiation or Development phase.

Data source: .tmp/networks/phase_transition_probabilities_by_tool.md (pipeline
output). Median hours per phase on each state; each edge shows P(To|From) and
median (h) for that transition. Excludes transitions from Closed.
Output: AIWare2026_CameraReady_Package/figures/fig_state_machine_{copilot,cursor,devin,openai,claude}.pdf
"""

from pathlib import Path
import re
import warnings

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT_DIR = REPO_ROOT / "AIWare2026_CameraReady_Package" / "figures"
ASSETS_DIR = REPO_ROOT / "assets"
PIPELINE_MD = REPO_ROOT / ".tmp" / "networks" / "phase_transition_probabilities_by_tool.md"

# Tool paradigm classification (static)
TOOL_PARADIGMS: dict[str, str] = {
    "Claude": "Assistant",
    "OpenAI": "Assistant",
    "Copilot": "Collaborator",
    "Cursor": "Collaborator",
    "Devin": "Collaborator",
}


def _load_from_pipeline(
    path: Path,
) -> tuple[dict[str, dict[str, float]], dict[str, list[tuple[str, str, float, float, int]]]] | None:
    """Parse pipeline output MD; return (MEDIAN_HOURS_PER_PHASE, TRANSITIONS) or None."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    tools_order = ["Claude", "Copilot", "Cursor", "Devin", "OpenAI"]
    # Parse "Median time (hours) per phase" table: rows Phase, then PR created, Review, Revision, Merged and closed, Unmerged and closed
    med_match = re.search(
        r"\| Phase \| ([^\n]+) \|\s*\n\|[-:\s|]+\|\s*\n((?:\|[^|]+\|[^\n]+\n)+)",
        text,
    )
    if not med_match:
        return None
    header = med_match.group(1)
    tool_names = [t.strip() for t in re.split(r"\|", header) if t.strip()]
    if not all(t in tools_order for t in tool_names):
        return None
    rows_text = med_match.group(2)
    median_per_phase: dict[str, dict[str, float]] = {t: {} for t in tool_names}
    for line in rows_text.strip().split("\n"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < len(tool_names) + 2:
            continue
        phase_name = parts[1]
        for i, tool in enumerate(tool_names):
            if i + 2 < len(parts):
                try:
                    median_per_phase[tool][phase_name] = float(parts[i + 2])
                except ValueError:
                    pass
    # Parse per-tool transition tables: ## ToolName then table with From, To, Median (h), Count, P(To | From)
    transitions: dict[str, list[tuple[str, str, float, float, int]]] = {t: [] for t in tools_order}
    for tool in tools_order:
        section = re.search(rf"## {re.escape(tool)}\s*\n\n(\|[^\n]+\n\|[-:\s|]+\|\s*\n(?:\|[^\n]+\n)+)", text)
        if not section:
            continue
        table = section.group(1)
        for line in table.split("\n"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue
            from_phase, to_phase = parts[1], parts[2]
            if from_phase == "Closed":
                continue
            try:
                median_h = float(parts[3])
                count = int(parts[4])
                p_val = float(parts[5])
            except (ValueError, IndexError):
                continue
            transitions[tool].append((from_phase, to_phase, median_h, p_val, count))
    if not all(transitions[t] for t in tools_order):
        return None
    return (median_per_phase, transitions)


# Load from pipeline output; fallback to hardcoded data if missing
_loaded = _load_from_pipeline(PIPELINE_MD)
if _loaded is not None:
    MEDIAN_HOURS_PER_PHASE, TRANSITIONS = _loaded
else:
    warnings.warn(
        "Pipeline output not found; using fallback data. Run: python -m src.analysis.network_extraction --output-dir .tmp/networks",
        UserWarning,
        stacklevel=0,
    )
    # Fallback: same structure as pipeline output (PR created model)
    MEDIAN_HOURS_PER_PHASE = {
        "Claude": {
            "PR created": 1.09,
            "Review": 2.00,
            "Revision": 4.01,
            "Merged and closed": 10.78,
            "Unmerged and closed": 8.08,
        },
        "Copilot": {
            "PR created": 0.23,
            "Review": 3.04,
            "Revision": 0.18,
            "Merged and closed": 17.87,
            "Unmerged and closed": 16.40,
        },
        "Cursor": {
            "PR created": 0.54,
            "Review": 1.64,
            "Revision": 1.40,
            "Merged and closed": 71.92,
            "Unmerged and closed": 7.21,
        },
        "Devin": {
            "PR created": 0.45,
            "Review": 2.00,
            "Revision": 0.65,
            "Merged and closed": 22.15,
            "Unmerged and closed": 24.42,
        },
        "OpenAI": {
            "PR created": 0.02,
            "Review": 0.66,
            "Revision": 1.96,
            "Merged and closed": 31.91,
            "Unmerged and closed": 0.03,
        },
    }
    TRANSITIONS = {
    "Claude": [
        ("PR created", "Merged and closed", 0.87, 0.376, 145),
        ("PR created", "Review", 0.64, 0.427, 165),
        ("PR created", "Revision", 5.06, 0.010, 4),
        ("PR created", "Unmerged and closed", 9.64, 0.187, 72),
        ("Review", "Merged and closed", 1.20, 0.752, 94),
        ("Review", "Revision", 4.33, 0.056, 7),
        ("Review", "Unmerged and closed", 17.81, 0.192, 24),
        ("Revision", "Merged and closed", 0.23, 0.250, 2),
        ("Revision", "Review", 3.97, 0.500, 4),
        ("Revision", "Unmerged and closed", 876.91, 0.250, 2),
    ],
    "Copilot": [
        ("PR created", "Merged and closed", 2.65, 0.006, 26),
        ("PR created", "Review", 0.23, 0.903, 4249),
        ("PR created", "Revision", 2.82, 0.005, 24),
        ("PR created", "Unmerged and closed", 0.17, 0.087, 409),
        ("Review", "Merged and closed", 3.34, 0.410, 1267),
        ("Review", "Revision", 0.77, 0.222, 687),
        ("Review", "Unmerged and closed", 10.71, 0.367, 1134),
        ("Revision", "Merged and closed", 0.97, 0.019, 12),
        ("Revision", "Review", 0.17, 0.955, 593),
        ("Revision", "Unmerged and closed", 23.63, 0.026, 16),
    ],
    "Cursor": [
        ("PR created", "Merged and closed", 0.51, 0.346, 492),
        ("PR created", "Review", 0.37, 0.513, 729),
        ("PR created", "Revision", 2.30, 0.003, 4),
        ("PR created", "Unmerged and closed", 10.60, 0.139, 197),
        ("Review", "Merged and closed", 1.03, 0.736, 465),
        ("Review", "Revision", 3.51, 0.041, 26),
        ("Review", "Unmerged and closed", 19.04, 0.223, 141),
        ("Revision", "Merged and closed", 34.69, 0.074, 2),
        ("Revision", "Review", 1.16, 0.815, 22),
        ("Revision", "Unmerged and closed", 7.00, 0.111, 3),
    ],
    "Devin": [
        ("PR created", "Merged and closed", 0.78, 0.190, 889),
        ("PR created", "Review", 0.06, 0.522, 2438),
        ("PR created", "Revision", 0.37, 0.018, 84),
        ("PR created", "Unmerged and closed", 67.79, 0.270, 1261),
        ("Review", "Merged and closed", 0.66, 0.605, 1305),
        ("Review", "Revision", 1.22, 0.057, 124),
        ("Review", "Unmerged and closed", 100.68, 0.338, 728),
        ("Revision", "Merged and closed", 0.13, 0.076, 14),
        ("Revision", "Review", 0.36, 0.723, 133),
        ("Revision", "Unmerged and closed", 193.69, 0.201, 37),
    ],
    "OpenAI": [
        ("PR created", "Merged and closed", 0.01, 0.765, 16163),
        ("PR created", "Review", 0.04, 0.111, 2356),
        ("PR created", "Revision", 0.09, 0.002, 32),
        ("PR created", "Unmerged and closed", 1.40, 0.122, 2583),
        ("Review", "Merged and closed", 0.40, 0.786, 1697),
        ("Review", "Revision", 0.66, 0.032, 69),
        ("Review", "Unmerged and closed", 12.17, 0.182, 393),
        ("Revision", "Merged and closed", 0.52, 0.122, 11),
        ("Revision", "Review", 0.78, 0.700, 63),
        ("Revision", "Unmerged and closed", 119.39, 0.178, 16),
    ],
    }


# Cap display for extreme median hours (e.g. show ">168h" to avoid distortion)
_HOUR_CAP = 168.0


def _fmt_h(h: float) -> str:
    """Format median hours with one decimal place."""
    if h > _HOUR_CAP:
        return f">{_HOUR_CAP:.0f}h"
    return f"{h:.1f}h"


def _fmt_p(p: float) -> str:
    """Format probability as percentage (e.g. 0.376 -> 37.60%)."""
    if p <= 0:
        return "0.00%"
    return f"{p * 100:.2f}%"


def _node_id(phase: str) -> str:
    # "PR created" -> PR_created; "Merged and closed" -> Merged_and_closed
    return phase.replace(" ", "_")


def _node_label(phase: str, median_h: float) -> str:
    prefix = ""
    if phase in ["Merged and closed", "Unmerged and closed"]:
        prefix = "TOTAL DURATION\n"
    return f"{prefix}{phase}\nmedian {_fmt_h(median_h)}"


def _edge_label(median_h: float, p: float, count: int) -> str:
    return f"{_fmt_p(p)}\n{_fmt_h(median_h)}\n(N={count})"


def _edge_label_compact(median_h: float, p: float) -> str:
    """Compact one-line label for diagram (e.g. 90.8%, 0.23h)."""
    pct = f"{p * 100:.1f}%" if p >= 0.001 else "<0.1%"
    return f"{pct}, {_fmt_h(median_h)}"


TERMINAL_PHASES = {"Merged_and_closed", "Unmerged_and_closed"}


def build_dot(tool: str) -> str:
    med = MEDIAN_HOURS_PER_PHASE[tool]
    trans = TRANSITIONS[tool]
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        "  nodesep=0.5; ranksep=0.6;",
        "  node [shape=box, fontname=\"Helvetica\", fontsize=11];",
        "  edge [fontname=\"Helvetica\", fontsize=10];",
        "  splines=ortho;",
    ]
    # Nodes: state with median hours; terminal states get double border
    for phase, h in med.items():
        nid = _node_id(phase)
        label = _node_label(phase, h)
        attrs = [f'label="{label}"']
        if nid in TERMINAL_PHASES:
            attrs.append("peripheries=2")
        lines.append(f"  {nid} [{', '.join(attrs)}];")
    # Edges: P (as %) and median h (skip P=0 to reduce clutter)
    for from_phase, to_phase, median_h, p, count in trans:
        if p <= 0:
            continue
        fid, tid = _node_id(from_phase), _node_id(to_phase)
        label = _edge_label(median_h, p, count)
        lines.append(f'  {fid} -> {tid} [label="{label}"];')
    # Legend at bottom (graph label)
    paradigm = TOOL_PARADIGMS.get(tool, "")
    lines.append(f'  label="{tool} ({paradigm} Paradigm)\nNode: median h in phase | Edge: P(To|From) %, median h to transition";')
    lines.append("  labelloc=b; fontsize=9;")
    lines.append("}")
    return "\n".join(lines)


def render_with_graphviz(tool: str, out_path: Path) -> bool:
    try:
        import graphviz
    except ImportError:
        return False
    dot_src = build_dot(tool)
    g = graphviz.Source(dot_src, format="pdf")
    g.render(out_path.with_suffix(""), cleanup=True)
    return True


# Node box half-dimensions (used for arrow start/end at boundary)
_BOX_HW = 0.32
_BOX_HH = 0.18


def _box_exit(center: tuple[float, float], direction: tuple[float, float], inset: float) -> tuple[float, float]:
    """Point inset from center along direction (for box: use inset as distance)."""
    dx, dy = direction[0], direction[1]
    s = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / s, dy / s
    return (center[0] + inset * ux, center[1] + inset * uy)


def _box_entry(center: tuple[float, float], direction_from_outside: tuple[float, float]) -> tuple[float, float]:
    """Boundary point when approaching center from outside. direction_from_outside points toward center."""
    dx, dy = direction_from_outside[0], direction_from_outside[1]
    s = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / s, dy / s
    # Distance along ray to hit box [±_BOX_HW] x [±_BOX_HH]
    if abs(ux) < 1e-9:
        t = _BOX_HH / abs(uy) if uy != 0 else _BOX_HW
    elif abs(uy) < 1e-9:
        t = _BOX_HW / abs(ux)
    else:
        t = min(_BOX_HW / abs(ux), _BOX_HH / abs(uy))
    return (center[0] - t * ux, center[1] - t * uy)


def render_with_matplotlib(tool: str, out_path: Path) -> None:
    import math
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Ellipse

    med = MEDIAN_HOURS_PER_PHASE[tool]
    trans = TRANSITIONS[tool]

    # Reference design: left-to-right flow; PR created (oval) left, Review/Revision center, terminals right
    pos = {
        "PR_created": (0.4, 1.5),
        "Review": (1.3, 1.5),
        "Revision": (1.3, 0.45),
        "Merged_and_closed": (2.5, 1.6),
        "Unmerged_and_closed": (2.5, 0.35),
    }
    # Start point: just outside node (use box half-dim so arrow meets boundary)
    start_inset = max(_BOX_HW, _BOX_HH) + 0.04  # 0.36 so clearly outside box
    # Orthogonal paths: (from, to) -> list of waypoints (path = [start] + waypoints + [end])
    # Label on segment: (segment_index 0.., t 0..1 along segment). Omit waypoints for straight edges.
    def waypoints(from_k: str, to_k: str) -> list[tuple[float, float]]:
        x1, y1 = pos[from_k][0], pos[from_k][1]
        x2, y2 = pos[to_k][0], pos[to_k][1]
        if (from_k, to_k) == ("PR_created", "Review"):
            return []  # horizontal
        if (from_k, to_k) == ("PR_created", "Merged_and_closed"):
            # Right, then down, then up into Merged (so arrow points up into node)
            return [(x2, y1), (x2, 1.28)]
        if (from_k, to_k) == ("PR_created", "Revision"):
            return [(x1 + 0.5 * (x2 - x1), y1), (x1 + 0.5 * (x2 - x1), y2)]  # right, down
        if (from_k, to_k) == ("PR_created", "Unmerged_and_closed"):
            return [(0.82, y1), (0.82, y2)]  # right, down, then right to terminal
        if (from_k, to_k) == ("Review", "Merged_and_closed"):
            return []
        if (from_k, to_k) == ("Review", "Revision"):
            return []
        if (from_k, to_k) == ("Review", "Unmerged_and_closed"):
            return [(x2, y1)]
        if (from_k, to_k) == ("Revision", "Merged_and_closed"):
            return [(x2, y1)]
        if (from_k, to_k) == ("Revision", "Review"):
            return []
        if (from_k, to_k) == ("Revision", "Unmerged_and_closed"):
            return []
        return []

    def label_on_segment(from_k: str, to_k: str) -> tuple[int, float]:
        """Which segment (0=first) and t (0.5=middle) to place label."""
        w = waypoints(from_k, to_k)
        if len(w) == 0:
            return (0, 0.5)
        # Prefer first (usually horizontal) segment so label is clearly on the main run
        if (from_k, to_k) == ("PR_created", "Merged_and_closed"):
            return (0, 0.5)  # horizontal segment
        if (from_k, to_k) in (("Review", "Unmerged_and_closed"), ("Revision", "Merged_and_closed")):
            return (1, 0.5)  # second segment
        return (0, 0.5)

    def k(p: str) -> str:
        return p.replace(" ", "_")

    # Dark theme (reference: dark grey background, white lines and text)
    DARK_BG = "#2d2d2d"
    NODE_FILL = "#404040"
    NODE_EDGE = "#e0e0e0"
    EDGE_COLOR = "#e0e0e0"
    TEXT_COLOR = "#ffffff"
    GRID_ALPHA = 0.15

    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.set_xlim(0, 2.85)
    ax.set_ylim(0.15, 1.9)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.grid(True, alpha=GRID_ALPHA, color=TEXT_COLOR, linestyle="-")

    # Nodes: oval for PR created, rounded rectangles for others
    for phase, (x, y) in pos.items():
        phase_display = phase.replace("_", " ")
        h = med.get(phase_display, 0)
        if phase == "PR_created":
            label = f"Pull Request Created\nmedian {_fmt_h(h)}"
        else:
            label = f"{phase_display}\nmedian {_fmt_h(h)}"
        is_terminal = phase in TERMINAL_PHASES
        if phase == "PR_created":
            ellipse = Ellipse((x, y), 0.64, 0.36, facecolor=NODE_FILL, edgecolor=NODE_EDGE, linewidth=1.5)
            ax.add_patch(ellipse)
        else:
            box = FancyBboxPatch(
                (x - 0.32, y - 0.18), 0.64, 0.36,
                boxstyle="round,pad=0.02", facecolor=NODE_FILL, edgecolor=NODE_EDGE,
                linewidth=2.0 if is_terminal else 1.2,
            )
            ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=9, color=TEXT_COLOR)

    # Orthogonal edges: path = start + waypoints + end; draw segments, arrow at end; label on segment
    for from_phase, to_phase, median_h, p, count in trans:
        if p <= 0:
            continue
        from_k, to_k = k(from_phase), k(to_phase)
        if from_k not in pos or to_k not in pos:
            continue
        x1, y1 = pos[from_k][0], pos[from_k][1]
        x2, y2 = pos[to_k][0], pos[to_k][1]
        w = waypoints(from_k, to_k)
        # Start: from node exit
        if w:
            dir_start = (w[0][0] - x1, w[0][1] - y1)
        else:
            dir_start = (x2 - x1, y2 - y1)
        s0 = math.hypot(dir_start[0], dir_start[1]) or 1.0
        start = _box_exit((x1, y1), dir_start, start_inset)
        # End: into node (boundary point when approaching from last waypoint)
        if w:
            dir_end = (x2 - w[-1][0], y2 - w[-1][1])
        else:
            dir_end = (x2 - x1, y2 - y1)
        end = _box_entry((x2, y2), dir_end)
        path = [start] + w + [end]
        # Draw segments
        for i in range(len(path) - 1):
            ax.plot([path[i][0], path[i + 1][0]], [path[i][1], path[i + 1][1]], color=EDGE_COLOR, lw=1.2)
        # Arrow at end (last segment)
        p0, p1 = path[-2], path[-1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        arrow_tail = (p1[0] - 0.12 * dx, p1[1] - 0.12 * dy)
        ax.annotate("", xy=p1, xytext=arrow_tail,
                    arrowprops=dict(arrowstyle="->", color=EDGE_COLOR, lw=1.2))
        # Label on chosen segment
        seg_idx, t = label_on_segment(from_k, to_k)
        a, b = path[seg_idx], path[seg_idx + 1]
        label_x = a[0] + t * (b[0] - a[0])
        label_y = a[1] + t * (b[1] - a[1])
        # Slight perpendicular offset so label doesn't sit on the line
        if b[0] == a[0]:
            label_x += 0.06
        else:
            label_y += 0.04
        ax.text(label_x, label_y, _edge_label_compact(median_h, p), fontsize=8, color=TEXT_COLOR,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.12", facecolor=DARK_BG, edgecolor=NODE_EDGE, linewidth=0.6))

    paradigm = TOOL_PARADIGMS.get(tool, "")
    ax.text(0.02, 0.02, f"Paradigm: {paradigm}\nNode: median h in phase | Edge: P(To|From) %, median h",
            transform=ax.transAxes, fontsize=8, color=TEXT_COLOR, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=NODE_FILL, edgecolor=NODE_EDGE, linewidth=0.6))
    ax.set_title(f"{tool} PR Workflow: {paradigm.upper()} PARADIGM", fontsize=12, fontweight="bold", color=TEXT_COLOR)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=DARK_BG, edgecolor="none")
    if "fig_state_machine_" in out_path.name:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        asset_path = ASSETS_DIR / f"{tool.lower()}_state_machine.png"
        plt.savefig(asset_path, dpi=300, bbox_inches="tight", facecolor=DARK_BG, edgecolor="none")
        print(f"Saved asset: {asset_path}")
    plt.close()


def main() -> None:
    MANUSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    tool_to_file = {
        "Copilot": "fig_state_machine_copilot",
        "Cursor": "fig_state_machine_cursor",
        "Devin": "fig_state_machine_devin",
        "OpenAI": "fig_state_machine_openai",
        "Claude": "fig_state_machine_claude",
    }
    for tool, base in tool_to_file.items():
        out_pdf = MANUSCRIPT_DIR / f"{base}.pdf"
        if render_with_graphviz(tool, out_pdf):
            print(f"Generated (graphviz): {out_pdf}")
        else:
            render_with_matplotlib(tool, out_pdf)
            print(f"Generated (matplotlib): {out_pdf}")


if __name__ == "__main__":
    main()

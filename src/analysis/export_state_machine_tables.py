"""
Generate LaTeX for multipanel tables that summarize what the state machine
diagrams show: P(To|From) as % and median hours per transition, by tool.

Uses the same data as plot_state_machines.py. Output: manuscript/tab_state_machine_multipanel.tex
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT_DIR = REPO_ROOT / "manuscript"

# Import diagram data and formatters
from src.analysis.plot_state_machines import (
    TRANSITIONS,
    MEDIAN_HOURS_PER_PHASE,
    TOOL_PARADIGMS,
    _fmt_h,
    _fmt_p,
)

FROM_STATES = ["PR created", "Review", "Revision"]
TO_STATES = ["Review", "Revision", "Merged and closed", "Unmerged and closed"]
TOOL_ORDER = ["Copilot", "Cursor", "Devin", "OpenAI", "Claude"]


def _cell(tool: str, from_s: str, to_s: str) -> str:
    r"""Return LaTeX cell content: P%, median\,h or ---."""
    for (f, t, median_h, p, _) in TRANSITIONS[tool]:
        if f == from_s and t == to_s and p > 0:
            pct = _fmt_p(p).replace("%", r"\%")
            h_str = _fmt_h(median_h).replace("h", r"\,h")
            return f"{pct}, {h_str}"
    return "---"


def _one_panel(tool: str) -> str:
    """LaTeX for one tool panel: small table From x To."""
    paradigm = TOOL_PARADIGMS.get(tool, "")
    lines = [
        r"\textbf{" + tool + r" (" + paradigm + r")}",
        r"\\[0.3em]",
        r"\begin{tabular}{@{}lcccc@{}}",
        r"\toprule",
        r"\textbf{From} & \textbf{Review} & \textbf{Revis.} & \textbf{Merged} & \textbf{Unmerged} \\",
        r"\midrule",
    ]
    short_from_label = {"PR created": "PR created", "Review": "Review", "Revision": "Revis."}
    for from_s in FROM_STATES:
        short_from = short_from_label.get(from_s, from_s)
        cells = [short_from]
        for to_s in TO_STATES:
            cells.append(_cell(tool, from_s, to_s))
        lines.append(" & ".join(cells) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def generate_tex() -> str:
    """Generate full table* LaTeX with five panels (two rows: 3 + 2)."""
    panels = [_one_panel(tool) for tool in TOOL_ORDER]
    def wrap(p: str) -> str:
        return (
            r"\begin{minipage}[t]{0.32\linewidth}"
            "\n\\centering\\small\n"
            + p
            + "\n"
            + r"\end{minipage}"
        )
    row1 = "\n\\hfill\n".join(wrap(p) for p in panels[:3])
    row2 = "\n\\hfill\n".join(wrap(p) for p in panels[3:])
    content = (
        r"\begin{table*}[t]"
        "\n"
        r"\caption{Phase transition probabilities and median hours per transition, by tool (same data as Figures~\ref{fig:sm-copilot}--\ref{fig:sm-claude}). From: source phase; columns: target phase. Cell: P(To$|$From)\%, median\,h.}"
        "\n"
        r"\label{tab:state-machine-multipanel}"
        "\n"
        r"\centering"
        "\n"
        r"\noindent"
        "\n"
        + row1
        + "\n\n"
        r"\vspace{1.2em}"
        "\n\n"
        r"\noindent"
        "\n"
        + row2
        + "\n"
        r"\end{table*}"
    )
    return content


def main() -> None:
    MANUSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = MANUSCRIPT_DIR / "tab_state_machine_multipanel.tex"
    tex = generate_tex()
    out.write_text(tex, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

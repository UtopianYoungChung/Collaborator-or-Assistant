# Methodology 2.0 — Workflow-Centric Collaboration Analysis

> **Scope**: This protocol supports **two main contributions** only. All other findings are archived for reference (see `archive/directives/methodology_20_reference_findings.md`).

## Overview

This methodology analyzes complete PR workflows to produce:

1. **Main contribution 1**: Tool-specific collaboration patterns — collaboration type distribution per tool, paradigm classification (Collaborator vs Assistant), and phase transition probabilities by tool with interpretation.
2. **Main contribution 2**: Five state machine diagrams with median hours per state and interpretation.

Only the materials required for these two contributions are defined below.

---

## Canonical References

| Role | Location |
|------|----------|
| **Narrative (methodology 2.0)** | `manuscript/methodology_20.md` |
| **Reference implementation** | `src/analysis/workflows.py`, `src/analysis/network_extraction.py` (or equivalent pipeline that produces phase transitions and median hours) |
| **Main output artifacts** | **`docs/phase_transition_master.md`** (canonical: P(To\|From) + median (h) per transition; all future work must refer to this), `.tmp/networks/phase_transition_probabilities_by_tool.md`, `.tmp/networks/median_hours_per_phase_by_tool.json`, `assets/*_state_machine.png`, `assets/collaboration_type_distribution_by_tool.png` |
| **Collaboration-type counts (for distribution table)** | `python -m src.analysis.evidence_stats` → `.tmp/evidence_stats.json`, `.tmp/evidence_stats.md` |
| **Stacked bar chart (collaboration type by tool)** | `python -m src.analysis.plot_collaboration_distribution` → `assets/collaboration_type_distribution_by_tool.png` |

---

## 1. Dataset (Required for Both Contributions)

- **Source**: AIDev PR timeline data (`data/raw/`).
- **Scope**: 33,600 PRs across 5 tools (OpenAI Codex, Copilot, Devin, Cursor, Claude Code).
- **Event types**: `committed`, `review_requested`, `reviewed`, `commented`, `merged`, `closed` (and others as in the dataset).

---

## 2. Workflow Lifecycle Model (Required for Both Contributions)

```
PR CREATED → REVIEW ⇄ REVISION → Merged and closed | Unmerged and closed
```

- **Implementation**: `src.analysis.workflows.assign_phases_temporal` (or equivalent).
- **Phases**: PR created, Review, Revision (non-terminal); **Merged and closed** and **Unmerged and closed** (terminal). No Initiation phase; first phase is **PR created** (from first event until first `review_requested` or `reviewed` after ≥1 commit).
- **Phase definitions**: As in `config/methodology.md` § Workflow Lifecycle Model (entry/exit conditions, events). Same state machine is used for (a) collaboration-type logic (revision_cycles, phase membership) and (b) transition sequences for P(To|From) and median hours per phase.

---

## 3. Actor Classification (Required for Contribution 1)

- **Agent**: `actor.type == "Bot"` or conservative substring heuristics (`BOT_PATTERNS`) — see `src.analysis.workflows.is_agent_event`.
- **Human**: All other actors.
- Used to assign initiator, resolver, and event counts for the collaboration taxonomy.

---

## 4. Collaboration Taxonomy (Required for Contribution 1)

**Observable-only scenarios**: The taxonomy is **initiator × terminal state**: merged PRs split by who merged (Human/Agent); non-merged (closed or incomplete timeline) collapsed to Not-Merged. No derived metrics (event ratios, weighted score, revision cycles) are used.

**Initiator** = actor of the first `committed` event → "Agent" | "Human". **Resolver** = actor who merged (Human | Agent); only when terminal event is `merged`.

**Six scenarios (S1–S6)** — PRs with at least one `committed` event in the timeline:

| Scenario | Type | Criteria (observable only) |
|----------|------|-----------------------------|
| S1 | Agent-Init + Human-Merged | initiator=Agent, merged, resolver=Human |
| S2 | Agent-Init + Agent-Merged | initiator=Agent, merged, resolver=Agent |
| S3 | Agent-Init + Not-Merged | initiator=Agent, closed or incomplete timeline |
| S4 | Human-Init + Human-Merged | initiator=Human, merged, resolver=Human |
| S5 | Human-Init + Agent-Merged | initiator=Human, merged, resolver=Agent |
| S6 | Human-Init + Not-Merged | initiator=Human, closed or incomplete timeline |

**Excluded cluster (not a scenario)** — PRs with **no `committed` event** in the timeline are excluded and reported separately as **"Excluded: No-Commit in Timeline"**. χ² and Cramér's V are computed on included PRs only (6 scenarios). Implementation: `src.analysis.workflows` (`SCENARIO_TYPES`, `EXCLUDED_NO_COMMIT_IN_TIMELINE`).

**Paradigm classification**: Collaborator tools = high share of Agent-Initiated (S1+S2+S3); Assistant tools = high share of Human-Initiated (S4+S5+S6). Excluded cluster is not part of the taxonomy.

**Outputs for contribution 1**: Collaboration type distribution per tool (counts and percentages for each scenario), tool × type χ² and Cramér's V, paradigm classification (Collaborator vs Assistant).

---

## 5. Phase Transition Probabilities (Required for Contributions 1 & 2)

- **Definition**: For each tool, \( P(B \mid A) = N(A \to B) / \sum_{B'} N(A \to B') \).
- **Computation**: From ordered (from-phase, to-phase) sequences produced by the same state machine over all PRs per tool.
- **Output**: `.tmp/networks/phase_transition_probabilities_by_tool.md` (tables and, optionally, interpretation).

---

## 6. Median Hours per Phase (Required for Contribution 2)

- **Definition**: Per tool, median time (hours) spent in each non-terminal phase before transitioning out; for terminal states, median time from PR open to that outcome.
- **Output**: `.tmp/networks/median_hours_per_phase_by_tool.json` (and/or equivalent table in the phase_transition doc).

---

## 7. State Machine Diagrams (Contribution 2)

- **Content**: For each of the five tools, one diagram showing the same lifecycle, with transition probabilities on arrows and median hours per state.
- **Location**: `assets/claude_state_machine.png`, `assets/copilot_state_machine.png`, `assets/cursor_state_machine.png`, `assets/devin_state_machine.png`, `assets/openai_state_machine.png`.

---

## 8. Evidence and Audit (Minimal)

- **Numbers in the paper**: Collaboration-type distribution and χ²/Cramér's V from `.tmp/evidence_stats.*`; phase transition probabilities and median hours from `.tmp/networks/*`.
- **Current evidence run (6 scenarios, included PRs only)**:
  - **Included PRs**: 29,585 (terminal outcomes only; used for scenario analysis). **Excluded**: 15 no-commit (0.0% of 33,600); 4,000 incomplete timeline (11.9%).
  - **Tool × collaboration-type (χ²)**: χ² = 29,817.204, dof = 20, p ≈ 0; **Cramér's V** = 0.5020.
  - Full distribution table (counts and 95% Wilson CIs per tool and scenario): `.tmp/evidence_stats.md`.
- **Layer 4 audit**: If an evidence report is still used for narrative consistency, run `python -m src.audit.evidence`; methodology 2.0 does not require exemplars or secondary findings to be in scope.

---

## Summary

Methodology 2.0 retains: **dataset**, **lifecycle model**, **actor classification**, **collaboration taxonomy**, **phase transition probability formula**, **median hours per phase**, and **state machine diagrams**. It produces exactly **two main contributions** and their interpretations. All other findings (weight sensitivity, negative case analysis, temporal analysis, exemplars, etc.) are archived for reference only.

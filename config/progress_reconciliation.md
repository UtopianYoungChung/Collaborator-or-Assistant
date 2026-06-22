# Progress Reconciliation for Paper Drafting

> **Purpose:** Organize and reconcile project state so the manuscript can be drafted and finalized against a single source of truth. Aligns with Layer 1 (methodology_20) and Layer 4 (review rubric).

**Date:** 2026-02-12

**Camera-ready folder:** `AIWare2026_CameraReady_Package/` — sole working folder.
**Camera-ready master:** `AIWare2026_CameraReady_Package/manuscript/aiware2026_submission_Camera-Ready.tex` — ACM sigconf. **All manuscript edits go here.** Prior drafts are in `reference/`.

---

## 1. Paper Scope (Methodology 2.0)

The paper is built around **two main contributions only** (see `config/methodology_20.md`):

| Contribution | Content | Source artifacts |
|--------------|---------|------------------|
| **1. Tool-specific collaboration patterns** | Collaboration type distribution per tool (6 scenarios S1–S6), paradigm classification (Collaborator vs Assistant), phase transition probabilities by tool | `.tmp/evidence_stats.json`, `.tmp/evidence_stats.md`, `.tmp/networks/phase_transition_probabilities_by_tool.md` |
| **2. Five state machine diagrams** | One diagram per tool with transition probabilities and median hours per state | `docs/phase_transition_master.md` (canonical), `.tmp/networks/median_hours_per_phase_by_tool.json`, `assets/*_state_machine.png` |

**Out of scope for the paper** (archived in `archive/directives/methodology_20_reference_findings.md`): weight sensitivity, negative case analysis, temporal analysis beyond a brief note, exemplar case studies, ML classifier, legacy 6-type taxonomy (Agent-Autonomous, Human-Led, Balanced Collaboration, etc.).

---

## 2. Source-of-Truth Mapping

All numbers in the manuscript **must** come from these artifacts (or be regenerated via the commands below).

| Manuscript section | Source artifact | Regenerate |
|--------------------|-----------------|------------|
| Dataset totals, Table 1 | `.tmp/evidence_stats.json` (`totals_by_tool`) | `python -m src.analysis.evidence_stats` |
| Collaboration type distribution (Table, Fig) | `.tmp/evidence_stats.md` (6 scenarios; 95% Wilson CIs), `.tmp/evidence_stats.json` | Same |
| χ², Cramér's V, tool × type | `.tmp/evidence_stats.json` (`chi2`, `cramers_v`, `chi2_dof`) | Same |
| Excluded cluster (No-Commit in Timeline) | `.tmp/evidence_stats.md` | Same |
| Phase transition probabilities P(To\|From) and median (h) per transition | **`docs/phase_transition_master.md`** (canonical; all future work must refer to this) | Run `python -m src.analysis.network_extraction --output-dir .tmp/networks`, then update master from `.tmp/networks/phase_transition_probabilities_by_tool.md` |
| Median hours per phase (state) | In `docs/phase_transition_master.md` and `.tmp/networks/median_hours_per_phase_by_tool.json` | Same pipeline |
| State machine figures | `assets/claude_state_machine.png`, etc. | Plotting script that uses the above |
| Collaboration stacked bar | `assets/collaboration_type_distribution_by_tool.png` | `python -m src.analysis.plot_collaboration_distribution` |
| Construct validity (87.8%, 61.0%, etc.) with 95% Wilson CIs: human-initiated PRs only, first exit from PR created | `.tmp/within_tool_human_initiated_report.json`, `.tmp/within_tool_human_initiated_report.md` | `python -m src.analysis.within_tool_comparison` |
| Temporal concentration (94% from 2025 Q2–Q3) | `.tmp/temporal_analysis.json` | `python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json` |
| OpenAI downsampling, Cramér's V range (Threats) | `.tmp/downsample_robustness.json` | `python -m src.analysis.downsample_robustness` |

**Important:** `reports/evidence_report.md` uses a **different taxonomy** (six legacy types: Agent-Initiated + Human-Resolved, Human-Initiated + Agent-Assisted, Agent-Autonomous, Human-Led, Balanced Collaboration, Unclassified) and **different counts**. Do **not** use it as the source for the paper’s collaboration table or percentages. Use **only** `.tmp/evidence_stats.*` for the 6-scenario (S1–S6) distribution.

---

## 3. Current Canonical Numbers (from latest run)

- **Total PRs (raw):** 33,600  
- **Excluded:** 15 no-commit; 4,000 incomplete timeline (11.9\%).
- **Included PRs (6 scenarios):** 29,585 (terminal outcomes only). Use \texttt{--exclude-incomplete} for evidence\_stats and network\_extraction.
- **Excluded (No-Commit in Timeline):** 15 (0.0%)
- **Tool × collaboration-type:** χ² = 29,817.204, dof = 20, p ≈ 0; **Cramér's V = 0.5020**
- **Bot heuristic error rate (on typed events):** 0.360%

Full distribution (counts and 95% Wilson CIs per tool and scenario): `.tmp/evidence_stats.md`.

---

## 4. Discrepancies Resolved for Drafting

### 4.1 Phase transition probabilities and median hours (Results § Phase Transitions)

The manuscript must use the exact values from **`docs/phase_transition_master.md`** (canonical). Pipeline output: `.tmp/networks/phase_transition_probabilities_by_tool.md`; after each full-dataset run, update the master from that file. **Lifecycle model (canonical as of 2026-02-04):** No Initiation; first phase is **PR created**; then Review ⇄ Revision; terminal = **Merged and closed** | **Unmerged and closed**. All P(To|From) and phase names in artifacts and manuscript use **PR created** (not Development/Initiation). See `docs/phase_transition_master.md` for current P(To|From) and median (h) per transition. After re-running the pipeline with the new phase model, refresh the master from `.tmp/networks/phase_transition_probabilities_by_tool.md`.

### 4.2 Paradigm percentages

Paradigm classification (Collaborator vs Assistant) and any cited percentages (e.g. “high share of Agent-Initiated”) must be computed from the 6-scenario distribution in `.tmp/evidence_stats.md` (e.g. Agent-Initiated share = S1+S2+S3 as % of included PRs per tool).

### 4.3 RQ3 and contribution 4 (methodological robustness)

The current manuscript mentions RQ3 (robustness to methodological choices) and contribution 4 (sensitivity analyses). Methodology 2.0 does **not** include these in the two main contributions. Options: (a) remove or shorten RQ3 and contribution 4 to "exploratory" only, or (b) keep as secondary and ensure any numbers there are grounded in `reports/weight_sensitivity_analysis.md` or equivalent, not invented.

---

## 5. Drafting Checklist

Before declaring the draft complete:

- [ ] **Numbers:** Every statistic in the manuscript is traceable to `.tmp/evidence_stats.*` or `.tmp/networks/*` (see §2).
- [ ] **Taxonomy:** Only the 6-scenario (S1–S6) taxonomy is used in the paper; no legacy types from `reports/evidence_report.md` in tables or main narrative.
- [ ] **Figures:** All figure PDFs used by the camera-ready .tex exist in `AIWare2026_CameraReady_Package/figures/` (fig_pipeline_overview.pdf, fig_pr_workflow.pdf, fig_collab_distribution.pdf, fig_state_machine_*.pdf).
- [ ] **Phase transition prose:** All P(To | From) and median (h) values in the Results section match **`docs/phase_transition_master.md`**. Phase names: **PR created**, Review, Revision; terminal: Merged and closed | Unmerged and closed (no Initiation/Development).
- [ ] **Median hours:** Table and text match `.tmp/networks/median_hours_per_phase_by_tool.json` → use **`docs/phase_transition_master.md`** (phases: PR created, Review, Revision, Merged and closed, Unmerged and closed). (see “Merged and closed”; manuscript uses “—”).
- [ ] **Paradigm percentages and χ²:** Filled from `.tmp/evidence_stats.md` (Collaborator: Cursor 96%, Devin 98%, Copilot 99%; Assistant: OpenAI 99.9%, Claude 96%). χ² and Cramér's V added in Results.
- [ ] **Temporal concentration (Threats / Introduction):** Quarter-level shares (e.g. Q2/Q3 2025, 94% in Q2–Q3) traceable to `.tmp/temporal_analysis.json` after `python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json`.
- [ ] **OpenAI downsampling sensitivity (Threats):** Cramér's V stability under OpenAI downsampled to Copilot-sized sample (default n = 4,885) traceable to `.tmp/downsample_robustness.json` after `python -m src.analysis.downsample_robustness` (defaults: `--n-match 4885`, `--seeds 10`).
- [ ] **Layer 4:** Run `python -m src.audit.evidence` if the evidence report is still maintained (may time out; re-run manually). For the manuscript, perform a manual pass against `config/review_rubric.md` (no hallucinated numbers, methodology consistent with `config/methodology.md` and methodology_20, citations in `data/external/` or bibliography).

---

## 6. File Quick Reference

| Role | Path |
|------|------|
| Paper scope (two contributions) | `config/methodology_20.md` |
| Narrative methodology (2.0) | `manuscript/methodology_20.md` |
| **Camera-ready folder** | **`AIWare2026_CameraReady_Package/`** — sole working folder |
| **Camera-ready master** | **`AIWare2026_CameraReady_Package/manuscript/aiware2026_submission_Camera-Ready.tex`** — primary manuscript. ALL edits go here. |
| Figure sources | `AIWare2026_CameraReady_Package/figures/*.pdf` (fig_pipeline_overview.pdf, fig_pr_workflow.pdf, fig_collab_distribution.pdf, fig_state_machine_*.pdf) |
| Deterministic stats (machine) | `.tmp/evidence_stats.json` |
| Deterministic stats (human) | `.tmp/evidence_stats.md` |
| Construct validity (human-init only) with 95% Wilson CIs | `.tmp/within_tool_human_initiated_report.json`, `.tmp/within_tool_human_initiated_report.md` |
| Temporal concentration (94% Q2–Q3) | `.tmp/temporal_analysis.json` — regenerate: `python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json` |
| OpenAI downsampling / Cramér's V range (Threats) | `.tmp/downsample_robustness.json` — regenerate: `python -m src.analysis.downsample_robustness` |
| **Phase transitions + median hours (canonical)** | **`reference/docs/phase_transition_master.md`** — all future work must refer to this |
| Pipeline output (refresh master from this) | `.tmp/networks/phase_transition_probabilities_by_tool.md` |
| Median hours (JSON) | `.tmp/networks/median_hours_per_phase_by_tool.json` |
| State machine diagrams | `assets/*_state_machine.png` |
| Collaboration plot | `assets/collaboration_type_distribution_by_tool.png` |
| Layer 4 rubric | `config/review_rubric.md` |
| Hand-off for drafting | `.agent/HANDOFF_DRAFTING_PHASE.md` |

---

## 7. Current Progress (Master Source for Agents)

**Camera-ready master:** `AIWare2026_CameraReady_Package/manuscript/aiware2026_submission_Camera-Ready.tex`. **Last updated:** 2026-04-05. All agents should refer to this state for camera-ready content.

### Paper structure (sections)

1. **Introduction** — RQs, two main contributions, paper organization.
2. **Background and Related Work** (sec:background) — AI Coding Agents, Human-AI Collaboration, Process Mining, Gap Analysis.
3. **Methodology** (sec:methodology) — Overview (with pipeline figure), Dataset (Source, Composition, Event Types), Workflow Lifecycle Model (PR created → Review ⇄ Revision → Merged & Closed | Unmerged & Closed), Actor Classification, Collaboration Taxonomy.
4. **Results** (sec:results) — Collaboration Type Distribution, Paradigm Classification, Phase Transitions and State Machine Diagrams, Interpretation (Transition Probabilities, Median Hours), Incomplete Timeline (with two tables), Outcome Measures and Success Patterns, Temporal Analysis.
5. **Discussion** (sec:discussion) — Two Paradigms, Implications for Practice.
6. **Threats to Validity** (sec:threats).
7. **Conclusion** (sec:conclusion).

### Lifecycle model (canonical)

- **Phases:** PR created → Review ⇄ Revision → **Merged and closed** | **Unmerged and closed**.
- **No Initiation.** First phase is **PR created** (from first event until first `review_requested` or `reviewed` after ≥1 commit).
- **Code:** `src/analysis/workflows.py` — `WorkflowPhaseName`: `PR_CREATED`, `REVIEW`, `REVISION`, `RESOLUTION`. Transition targets: `merged_and_closed`, `unmerged_and_closed`.
- **Protocol:** `config/methodology.md` and manuscript §3 (Workflow Lifecycle Model) use this model.

### Figures (master paper)

| Label | Location | File | Notes |
|-------|----------|------|--------|
| fig:pipeline-overview | §3 Methodology, Overview | `AIWare2026_CameraReady_Package/figures/fig_pipeline_overview.pdf` | High-level data pipeline diagram. |
| fig:collab-dist | §4 Results, Interaction Scenario Type Distribution | `AIWare2026_CameraReady_Package/figures/fig_collab_distribution.pdf` | Full-width (`figure*`), legend below bars, top-two % labels per tool. |
| fig:sm-copilot, fig:sm-cursor, fig:sm-devin, fig:sm-openai, fig:sm-claude | §4 Phase Transitions | `AIWare2026_CameraReady_Package/figures/fig_state_machine_*.pdf` | Terminal outcomes: Merged & Closed \| Unmerged & Closed. |

### Tables (master paper)

- **Active:** tab:dataset (Dataset composition: Tool, Total PRs only); tab:taxonomy (Six scenarios S1–S6); tab:results (Collaboration type by tool — percentages, 6 scenarios); tab:incomplete-timeline-breakdown (Open, Abandoned, Incomplete Data); tab:incomplete-timeline (Incomplete timeline PRs by tool).
- **Commented out:** tab:trans-copilot, tab:trans-cursor, tab:trans-devin, tab:trans-openai, tab:trans-claude (per-tool transition tables); tab:median-hours (median hours per phase by tool). Redundant with state machine figures and prose.

### Key numbers (from manuscript text)

- **Dataset:** 33,600 PRs; five tools (OpenAI Codex, Copilot, Devin, Cursor, Claude Code).
- **Results § Collaboration Type:** χ² = 29,817, dof = 20, p ≈ 0, Cramér's V = 0.50. Figure 1 caption: Copilot 0.8% Human-Init (S4 + S6; 23 PRs); see Table~\ref{tab:results} for exact values.

### Pipeline / artifacts

- **Evidence and phase transitions:** `python -m src.analysis.evidence_stats` and `python -m src.analysis.network_extraction --output-dir .tmp/networks`. Refresh `reference/docs/phase_transition_master.md` from `.tmp/networks/phase_transition_probabilities_by_tool.md` after runs (phase names: PR created, Review, Revision; no Initiation/Development).
- **Collaboration plot (PDF):** `python -m src.analysis.plot_collaboration_distribution` → writes figure PDF (configure output dir) and `assets/collaboration_type_distribution_by_tool.png`.
- **Construct validity (human-initiated PRs only):** `python -m src.analysis.within_tool_comparison` → `.tmp/within_tool_human_initiated_report.json`, `.tmp/within_tool_human_initiated_report.md` (point estimates + 95% Wilson CIs; e.g., Copilot 87.8%→review [75.8%, 94.3%], OpenAI 11.1%→review [10.7%, 11.6%]).
- **Temporal concentration (94% from 2025 Q2–Q3):** `python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json` → `.tmp/temporal_analysis.json`.

### Single source of truth

- **Camera-ready master:** **`AIWare2026_CameraReady_Package/manuscript/aiware2026_submission_Camera-Ready.tex`** — ALL EDITS GO HERE.
- **Methodology (phases, taxonomy):** `config/methodology.md`.
- **Paper scope and artifact mapping:** This file (`config/progress_reconciliation.md`).
- **Phase transition numbers (after pipeline run):** `reference/docs/phase_transition_master.md` (refresh from `.tmp/networks/phase_transition_probabilities_by_tool.md`).

---

## Summary

**Reconciled state:** The paper is scoped to two contributions (tool-specific collaboration patterns + five state machine diagrams). All empirical content must be grounded in `.tmp/evidence_stats.*` and `.tmp/networks/*`. The legacy evidence report is not the source for the paper’s collaboration table. **Lifecycle model is PR created → Review ⇄ Revision → Merged and closed | Unmerged and closed (no Initiation).** Phase transition numbers in the manuscript must match the pipeline output (after re-run with new phase model) and `docs/phase_transition_master.md`; use this document and the checklist (§5) for the final drafting pass and before Layer 4 verification.

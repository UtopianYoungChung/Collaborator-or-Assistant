# Strategic Plan: Statistical Testing to Fill Tables 3 and 6

**Purpose:** Compute and fill the blanks in **Table 3** (Collaboration type distribution by tool) and **Table 6** (Outcome measures by collaboration type) in `manuscript/aiware2026_submission.tex`, using deterministic pipeline outputs and correct statistical tests.

**Scope:** Layer 2 (Orchestration) plan; execution uses Layer 3 tools (`src/analysis/evidence_stats.py`, `src/analysis/outcome_analysis.py`). Results must be verifiable by Layer 4 (audit).

---

## 1. Current Paper Context

- **Table 3** (`\ref{tab:results}`): “Collaboration type distribution by tool (6 scenarios; 95% Wilson CIs).” Rows = 5 tools (Cursor, Devin, Copilot, Claude, OpenAI); columns = S1–S6. All cells are currently `---`. The narrative states: “Tool × collaboration-type association is highly significant (χ², dof=20, p ≈ 0, Cramér's V from replication package). Full counts and 95% Wilson CIs are produced by our pipeline.”
- **Table 6** (`\ref{tab:outcome-measures}`): “Outcome measures by collaboration type (6 scenarios).” Columns: Type, n, Merge Rate, Mean Commits, Mean Duration (h). Rows = S1–S6. All cells are currently `---`. Caption: “Merge rate = proportion with \texttt{merged} event; Duration = time from first to last timestamp.”

Taxonomy (from manuscript): S1 = Agent-Init + Human-Merged, S2 = Agent-Init + Agent-Merged, S3 = Agent-Init + Not-Merged, S4 = Human-Init + Human-Merged, S5 = Human-Init + Agent-Merged, S6 = Human-Init + Not-Merged. Only **included** PRs (with at least one `committed` event) are in the 6 scenarios; excluded (“No-Commit in Timeline”) are reported separately and not in χ².

---

## 2. Table 3: Collaboration Type Distribution by Tool

### 2.1 Statistics to Produce

| Output | Description | Source |
|--------|-------------|--------|
| **Per-cell counts** | For each (tool, scenario) pair: count of PRs in that tool and scenario (S1–S6 only; excluded not in table). | `evidence_stats` |
| **Per-cell percentages** | For each (tool, scenario): percentage of **included** PRs for that tool (denominator = tool total − excluded for that tool). | Derived from counts |
| **95% Wilson CIs** | For each (tool, scenario): Wilson score interval for proportion within that tool’s included PRs. | `evidence_stats.wilson_interval(k, n_incl, alpha=0.05)` |
| **χ² test** | Test of independence: Tool × Scenario (5×6 contingency table, included PRs only). | `evidence_stats.chi2_test(table)` |
| **Degrees of freedom** | (5−1)×(6−1) = **20**. | Must match manuscript (dof=20). |
| **Cramér's V** | Effect size for 5×6 table: √(χ² / (n × min(4,5))). | `evidence_stats` (existing formula) |

### 2.2 Implementation Status

- **`src/analysis/evidence_stats.py`** already:
  - Uses `SCENARIO_TYPES` (6 scenarios) and builds a contingency table with one row per tool and one column per scenario type value.
  - Computes χ², dof, p-value, and Cramér's V on that table.
  - Writes `counts_by_tool_and_type` and totals to `.tmp/evidence_stats.json` and a long-format markdown table with 95% Wilson CIs to `.tmp/evidence_stats.md`.

- **Gap:** The manuscript table is **wide** (one row per tool, six columns S1–S6). The current markdown is long (one row per tool × type). No direct “table 3” export exists.

### 2.3 Steps to Fill Table 3

1. **Re-run evidence pipeline** (ensure 6-scenario taxonomy and dof=20):
   ```bash
   python -m src.analysis.evidence_stats
   ```
   - Confirm `.tmp/evidence_stats.json` has exactly 6 scenario keys per tool (S1–S6 labels: `Agent-Init + Human-Merged`, …, `Human-Init + Not-Merged`) and that `chi2_dof` is **20**. If the JSON still has finer-grained types (e.g. Human-Closed, Agent-Closed, Incomplete Timeline), the run may be using an older workflow; ensure `workflows.CollaborationType` and `SCENARIO_TYPES` are the single source of truth (6 scenarios + excluded).

2. **Build wide-format table for manuscript:**
   - **Option A (recommended):** Add a small script or function (e.g. in `evidence_stats.py` or a new `scripts/export_table3.py`) that:
     - Reads `.tmp/evidence_stats.json`.
     - For each tool, computes for S1–S6: count, percentage of included PRs for that tool, and Wilson CI (using same `wilson_interval` as in evidence_stats).
     - Outputs a table in a form easy to paste into the LaTeX table (e.g. one row per tool: `Tool & S1 & S2 & … & S6` with cells like `12.3\% [10.1\%, 14.8\%]` or just `12.3\%` with a note “Full counts and 95% Wilson CIs: replication package”).
   - **Option B:** Manually aggregate from `.tmp/evidence_stats.md`: for each tool, take the 6 rows corresponding to S1–S6 and transpose into one row with 6 columns.

3. **Update manuscript:**
   - Replace the `---` cells in Table 3 with the computed percentages (and optionally CI bounds). Use consistent formatting (e.g. one decimal for percentages).
   - In the narrative, report χ², dof=20, p ≈ 0, and Cramér's V from `.tmp/evidence_stats.json` (e.g. “Cramér's V = 0.54” or the exact value from the run).

4. **Layer 4 check:** Run `python -m src.audit.evidence` (if available) and/or manually verify that the numbers in the manuscript match `.tmp/evidence_stats.json` and that dof=20 for the Tool × Scenario test.

---

## 3. Table 6: Outcome Measures by Collaboration Type

### 3.1 Statistics to Produce

| Column | Description | Source |
|--------|-------------|--------|
| **Type** | Scenario label (S1–S6). | Same taxonomy as Table 3. |
| **n** | Count of PRs in that scenario (included only). | `outcome_analysis.compute_outcome_stats_by_type` |
| **Merge Rate** | Proportion of PRs in that scenario with a `merged` event. By definition: S1, S2, S4, S5 = 100%; S3, S6 = 0%. | From workflow `is_merged`; report 100.0% or 0.0% as appropriate. |
| **Mean Commits** | Mean commit count over PRs in that scenario. | `OutcomeStats.mean_commits` |
| **Mean Duration (h)** | Mean of (last_ts − first_ts) in hours; PRs with no valid duration can be omitted from the mean (document in caption). | `OutcomeStats.mean_duration_hours` |

Optional for replication package: 95% Wilson CI for merge rate, mean reviews, median duration.

### 3.2 Implementation Status

- **`src/analysis/outcome_analysis.py`** already:
  - Loads all workflows via `load_all_workflows()` (uses same `workflows.analyze_workflow` and thus same 6-scenario `collaboration_type`).
  - `compute_outcome_stats_by_type(workflows)` groups by `wf.collaboration_type.value` and computes `OutcomeStats` (n, merge rate, mean commits, mean reviews, mean duration, etc.).
  - `generate_outcome_report()` writes a markdown table to `.tmp/outcome_stats.md`.

- **Gap:** The manuscript table has 6 rows (S1–S6). If the pipeline was run with a finer-grained taxonomy, `.tmp/outcome_stats.md` may have more rows (e.g. Human-Closed, Agent-Closed, Incomplete Timeline). Then we must aggregate to S1–S6: e.g. S3 = all “Agent-Init + Not-Merged” (one type in current taxonomy); S6 = all “Human-Init + Not-Merged”. With the current 6-scenario `CollaborationType`, no aggregation is needed—just ensure the report lists only the 6 scenarios (and optionally excludes “Excluded: No-Commit in Timeline” from the main table or reports it separately).

### 3.3 Steps to Fill Table 6

1. **Re-run outcome analysis** (so it uses 6-scenario taxonomy):
   - From project root:
     ```bash
     python -m src.analysis.outcome_analysis --output .tmp/outcome_stats.md
     ```
   - Or run `python -m src.analysis.evidence_stats` (it calls `generate_outcome_report` and writes `.tmp/outcome_stats.md`).
   - Confirm `.tmp/outcome_stats.md` has exactly six scenario rows (S1–S6) plus optionally one row for “Excluded: No-Commit in Timeline.”

2. **Map report columns to manuscript columns:**
   - Type → scenario label (S1–S6).
   - n → `OutcomeStats.count`.
   - Merge Rate → `OutcomeStats.merge_rate` (×100 for percentage); S3 and S6 must be 0.0%, S1, S2, S4, S5 = 100.0%.
   - Mean Commits → `OutcomeStats.mean_commits` (one decimal).
   - Mean Duration (h) → `OutcomeStats.mean_duration_hours` (one decimal; use “N/A” or “—” if null).

3. **Optional script:** Add a small exporter that reads the outcome report or recomputes `compute_outcome_stats_by_type` and outputs LaTeX table rows for Table 6 (or a CSV) so the manuscript can be updated without manual transcription.

4. **Update manuscript:** Replace the `---` cells in Table 6 with the values from `.tmp/outcome_stats.md` (or from the exporter). Keep caption wording: “Merge rate = proportion with \texttt{merged} event; Duration = time from first to last timestamp.”

5. **Layer 4 check:** Verify that n summed over S1–S6 equals total included PRs (e.g. 29,585) and that merge rates for S3 and S6 are 0% and for S1, S2, S4, S5 are 100%.

---

## 4. Summary: Execution Order

| Step | Action | Output / Check |
|------|--------|----------------|
| 1 | Run `python -m src.analysis.evidence_stats` | `.tmp/evidence_stats.json`, `.tmp/evidence_stats.md`; χ² dof=20, 6 scenarios only. |
| 2 | Optionally add wide-format export for Table 3 | Rows for Table 3 (percentages ± Wilson CIs). |
| 3 | Fill Table 3 in `aiware2026_submission.tex` | No `---`; narrative χ², dof, p, Cramér's V. |
| 4 | Run outcome report (via evidence_stats or outcome_analysis) | `.tmp/outcome_stats.md` with 6 scenario rows. |
| 5 | Fill Table 6 in `aiware2026_submission.tex` | n, Merge Rate, Mean Commits, Mean Duration (h) for S1–S6. |
| 6 | Run audit (e.g. `python -m src.audit.evidence`) | No mismatch between manuscript and pipeline outputs. |

---

## 5. Consistency and Grounding

- **No invention:** All numbers in Tables 3 and 6 must come from pipeline outputs (`.tmp/evidence_stats.*`, `.tmp/outcome_stats.md`) or from deterministic aggregation of those outputs.
- **Single source of truth:** Scenario definitions are in `src/analysis/workflows.py` (`CollaborationType`, `SCENARIO_TYPES`). Evidence and outcome modules must use the same workflow analyzer so that “included PRs” and “6 scenarios” are identical for both tables.
- **Statistical tests:** χ² and Cramér's V are computed on the 5×6 Tool × Scenario table (included PRs only); dof = 20. Wilson CIs are 95% for binomial proportions (per-tool scenario shares).
- **Facts vs interpretation:** Report exact statistics (χ², p, Cramér's V, percentages, means); reserve causal or interpretive language for the narrative and discussion.

This plan aligns with the 4-layer research architecture (AGENTS.md) and the “Grounded Analyst” rules: strict grounding in pipeline outputs and clear separation of fact from inference.

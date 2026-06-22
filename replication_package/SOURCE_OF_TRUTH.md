# Source-of-Truth Mapping

Manuscript claims and their traceable artifacts. Numbers in the camera-ready PDF should be regenerable from these outputs when `data/raw/` matches the Figshare bundle.

## Core Artifacts

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| Dataset totals, Table 1 | `.tmp/evidence_stats.json` (`totals_by_tool`) | `python -m src.analysis.evidence_stats` |
| Collaboration type distribution (S1–S6), χ², Cramér's V | `.tmp/evidence_stats.json`, `.tmp/evidence_stats.md` | Same |
| Phase transition P(To\|From), median hours | `.tmp/networks/phase_transition_probabilities_by_tool.md` | `python -m src.analysis.network_extraction --output-dir .tmp/networks --exclude-incomplete` |
| State machine figures | `AIWare2026_CameraReady_Package/figures/fig_state_machine_*.pdf` | `python -m src.analysis.plot_state_machines` |
| Collaboration stacked bar | `AIWare2026_CameraReady_Package/figures/fig_collab_distribution.pdf` | `python -m src.analysis.plot_collaboration_distribution` |

## RQ3 (Automation-authorized merges, path analysis)

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| 54 PRs with Agent-classified merge (S2+S5), 0.24% of merged | RQ3 prose + Table; derive from `.tmp/evidence_stats.json` (`counts_by_tool_and_type`; sum Agent-init Agent-merged + Human-init Agent-merged) **or** cross-check paths in `s2_path_analysis.md` | Step 2: `network_extraction` |
| 61% of automation-authorized merges touched human review | RQ3 Results in paper; detailed paths | `.tmp/networks/s2_path_analysis.md` (produced by `export_s2_path_analysis_report` in Step 2) |
| 21 / 29,585 upper bound (autonomous authority framing) | Discussion / Threats | Derive from RQ3 path rules in paper + same artifacts |

**Note:** The authoritative scenario counts remain in `evidence_stats`; `s2_path_analysis.md` classifies workflow paths for Agent-merge cases for narrative checks.

## Threats § External validity — Downsampling

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| OpenAI downsampled to \(n = 4{,}885\), 10 seeds; Cramér's V \(\approx 0.510 \pm 0.001\) | `.tmp/downsample_robustness.json` | `python -m src.analysis.downsample_robustness --n-match 4885 --seeds 10` |

Uses `compute_evidence_stats(exclude_incomplete=True)` for non-OpenAI tool rows so counts align with the 29,585 included PRs.

## Threats § External validity — Within-repository control

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| Repos where each tool has ≥5 included PRs; pooled initiation shares; human merge-actor contrast | `.tmp/within_repository_analysis.json`, `.tmp/within_repository_analysis.md` | `python -m src.analysis.within_repository_analysis --min-prs 5 --repo-rule all_five_tools` |

**Definition:** Default rule `all_five_tools` matches Threats wording (“each Collaborator and Assistant tool … at least five PRs”: all five tool files must contribute ≥5 included PRs in that repository). Alternative `both_paradigms` aggregates Collaborator tools (Cursor+Devin+Copilot) and Assistant tools (OpenAI+Claude) for a less sparse diagnostic. *Included* PRs exclude incomplete timelines.

**Note:** Published percentages for the “human approver” reversal (e.g., 59.6% vs.\ 49.7%) should be **reconciled** to `.tmp/within_repository_analysis.json` after running on the **Figshare** raw bundle; if they diverge, the camera-ready slice may use a secondary weighting (e.g., repo-level means) or an RQ2-aligned routing definition---extend `within_repository_analysis.py` to match that snapshot.

## Construct Validity (Threats § Construct validity)

The paragraph comparing **human-initiated PRs only** across tools (Copilot 87.8%→review, Devin 61.0%→review, Cursor 57.1%→review, OpenAI 76.6%→merge) addresses circularity: paradigm is defined by initiation, then we analyze review vs direct resolution; holding initiation constant (human-init only) shows that Collaborator vs Assistant tools still differ.

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| Copilot 87.8% → review, 95% CI [75.8%, 94.3%] (human-init only) | `.tmp/within_tool_human_initiated_report.md` / `.json` | `python -m src.analysis.within_tool_comparison` |
| Devin 61.0% → review, 95% CI [49.9%, 71.2%] (human-init only) | Same | Same |
| Cursor 57.1% → review, 95% CI [44.1%, 69.2%] (human-init only) | Same | Same |
| OpenAI 11.1% → review, 95% CI [10.7%, 11.6%] (human-init only) | Same | Same |
| OpenAI 76.6% → merged (human-init only) | Same | Same |
| Non-overlapping Wilson CIs; Collaborator lower bounds exceed OpenAI upper bound by 3.8–6.5× | Same | Same |

**Note:** These rates require a human-initiated-only filter and are **not** derivable from `evidence_stats.json` alone. The `within_tool_comparison` module restricts to S4/S5/S6 PRs and records first exit from PR created (review, revision, merged_and_closed, unmerged_and_closed) per tool, with 95% Wilson score confidence intervals.

## Temporal Concentration (Threats § External validity)

| Manuscript claim | Source artifact | Regenerate |
|-----------------|-----------------|------------|
| 94% of PRs from 2025 Q2–Q3 | `.tmp/temporal_analysis.json` (`counts_by_tool_by_month`; sum Q2+Q3, divide by `total_prs`) | `python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json` |

The dataset spans 2018–2025 but is temporally concentrated; the manuscript rounds the computed share to “94%” (actual ~94.7% depending on exact date boundaries).

---

*See `config/progress_reconciliation.md` in the main project for extended drafting checklists.*

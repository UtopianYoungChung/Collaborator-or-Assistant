# Methodology Summary

Abbreviated reference for the replication package. For full protocol, see `config/methodology.md` and `config/methodology_20.md`.

## Lifecycle Model

**Phases:** PR created → Review ⇄ Revision → terminal

**Terminal outcomes:** Merged & Closed | Unmerged & Closed

No separate Initiation or Development phase; the first phase is **PR created** (interval from PR open until first review event after ≥1 commit).

## Six Interaction Scenarios (S1–S6)

| ID | Type | Criteria |
|----|------|----------|
| S1 | Agent-Init + Human-Merged | initiator=Agent, merged (human approver / merge actor) |
| S2 | Agent-Init + Agent-Merged | initiator=Agent, merged (agent approver / merge actor) |
| S3 | Agent-Init + Not-Merged | initiator=Agent, closed without merge |
| S4 | Human-Init + Human-Merged | initiator=Human, merged (human merged) |
| S5 | Human-Init + Agent-Merged | initiator=Human, merged (agent merged) |
| S6 | Human-Init + Not-Merged | initiator=Human, closed without merge |

**Initiator** = actor of first `committed` event. **Excluded:** PRs with no `committed` event; PRs with no `merged` or `closed` event (incomplete timelines).

## Paradigm Classification

Empirically, **Collaborator** tools are **Cursor, Devin, Copilot** ($\geq$96% agent-initiated among included PRs in the camera-ready results) and **Assistant** tools are **OpenAI, Claude** ($\geq$95.6% human-initiated). The replication code does not hard-code these percentages; it reports scenario counts from `evidence_stats` and the within-repository script uses the same tool→paradigm mapping as the paper.

## Key Outputs

- **Evidence stats:** χ², Cramér's V, 95% Wilson CIs per tool/scenario; bot heuristic error rate
- **Phase transitions:** P(To|From) and median hours per phase per tool
- **Construct validity (human-init only):** First exit from PR created by tool with 95% Wilson CIs (Copilot 87.8%→review [75.8%, 94.3%], Devin 61.0%→review [49.9%, 71.2%], OpenAI 11.1%→review [10.7%, 11.6%], OpenAI 76.6%→merge); non-overlapping CIs between paradigms. Source: `.tmp/within_tool_human_initiated_report.md`
- **Temporal concentration:** ~94% of PRs from 2025 Q2–Q3; source: `.tmp/temporal_analysis.json`
- **Downsampling robustness:** `.tmp/downsample_robustness.json` (optional; Threats)
- **Within-repository control:** `.tmp/within_repository_analysis.json` (Discussion / Threats)
- **RQ3 paths:** `.tmp/networks/s2_path_analysis.md` (after `network_extraction`)
- **Figures:** Collaboration stacked bar chart; five per-tool state machine diagrams

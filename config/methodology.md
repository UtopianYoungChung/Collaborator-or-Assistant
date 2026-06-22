# Workflow-Centric Collaboration Analysis Methodology

> **Methodology 2.0**: For the paper built around **two main contributions** only (tool-specific collaboration patterns + five state machine diagrams with median hours), use `config/methodology_20.md` and `manuscript/methodology_20.md`. Other findings are archived for reference in `archive/directives/methodology_20_reference_findings.md`.

> **Note (canonical narrative)**: This file defines the **Layer 1 protocol** in abbreviated form. The
> most complete, publication-oriented description currently lives in `manuscript/methodology.md`.
> If the two diverge, treat `manuscript/methodology.md` as the narrative reference and update this
> protocol intentionally (to avoid silent drift).

## Overview

This methodology analyzes complete PR workflows to characterize human-agent collaboration in software development.

### Canonical references (single source of truth)

- **Narrative reference**: `manuscript/methodology.md`
- **Reference implementation**: `src/analysis/workflows.py`
- **Deterministic headline statistics**:
  - Generate: `python -m src.analysis.evidence_stats`
  - Outputs: `.tmp/evidence_stats.json`, `.tmp/evidence_stats.md`
- **Layer 4 audit** (validates the evidence report against deterministic stats):
  - Run: `python -m src.audit.evidence`

## Workflow Lifecycle Model

```
PR CREATED → REVIEW ⇄ REVISION → Merged and closed | Unmerged and closed
```

**Current canonical model (as of 2026-02-04):** No Initiation phase. First phase is **PR created**; then Review ⇄ Revision; terminal outcomes are **Merged and closed** or **Unmerged and closed**.

### Phase Definitions

Phases are assigned using a temporal state machine implemented in `src.analysis.workflows.assign_phases_temporal`. Terminal outcomes are distinguished as **Merged and closed** vs **Unmerged and closed** (event type `merged` vs `closed`).

| Phase / Terminal | Entry condition | Exit condition | Events captured |
|---|---|---|---|
| **PR created** | First event (PR creation) | First `review_requested` or `reviewed` *after at least one* `committed` | All events from PR creation until first review; must see ≥1 `committed` before exiting |
| **Review** | First `review_requested` or `reviewed` after ≥1 commit | `reviewed:CHANGES_REQUESTED` (→ REVISION) or `merged`/`closed` | `reviewed`, `commented`, `review_requested` |
| **Revision** | `reviewed:CHANGES_REQUESTED` | Next `review_requested` or `reviewed` (→ REVIEW) or `merged`/`closed` | `committed`, `commented` |
| **Merged and closed** | `merged` | — (terminal) | — |
| **Unmerged and closed** | `closed` | — (terminal) | — |

*PR created:* runs from the first event in the timeline until the first `review_requested` or `reviewed` after at least one `committed` event. *Review:* transition from PR created occurs on either `review_requested` or `reviewed` (manual review fallback). `APPROVED` does not end the PR; workflow remains in Review until a terminal event. *Revision:* a revision cycle is counted only when `CHANGES_REQUESTED` is followed by ≥1 `committed` before the next `review_requested` or `reviewed`. Terminal states are absorbing (Merged and closed = PR was merged; Unmerged and closed = PR was closed without merge).

> **Implementation note**: The canonical reference implementation for the workflow lifecycle model used
> by the deterministic evidence pipeline is `src/analysis/workflows.py` (including explicit REVISION handling,
> revision-cycle counting, two terminal outcomes merged_and_closed / unmerged_and_closed in transition sequences, and weighted metrics). See `manuscript/methodology.md` §3.3 for the full narrative and state machine formalization.

## Actor Classification

| Code | Meaning | Examples |
|------|---------|----------|
| **Agent** | AI agent / bot actor | devin-ai-integration[bot], copilot-swe-agent[bot] |
| **Human** | Human Developer | Any non-bot actor |

### Actor labeling rule (grounded)

Actor labeling is implemented in `src.analysis.workflows.is_agent_event`:
- If the dataset provides `actor.type == "Bot"`, classify as **Agent**.
- Otherwise, fall back to conservative substring heuristics (`BOT_PATTERNS`).

## Collaboration Types

Collaboration type classification uses **observable-only scenarios** (initiator × terminal state). **Terminal state**: merged PRs are split by who merged (Human/Agent); non-merged (closed or incomplete timeline) are collapsed to Not-Merged. **Initiator** = actor of first `committed` (Agent | Human). **Resolver** = actor who merged (Human | Agent); only defined when terminal event is `merged`. No derived metrics (event ratios, weighted score) are used. Closed vs incomplete can be disaggregated via \`resolver_origin\` and \`last_event_type\` when needed.

| Scenario | Type | Criteria |
|----------|------|----------|
| S1 | **Agent-Init + Human-Merged** | initiator=Agent, merged, resolver=Human |
| S2 | **Agent-Init + Agent-Merged** | initiator=Agent, merged, resolver=Agent |
| S3 | **Agent-Init + Not-Merged** | initiator=Agent, closed or incomplete timeline |
| S4 | **Human-Init + Human-Merged** | initiator=Human, merged, resolver=Human |
| S5 | **Human-Init + Agent-Merged** | initiator=Human, merged, resolver=Agent |
| S6 | **Human-Init + Not-Merged** | initiator=Human, closed or incomplete timeline |
| — | **Excluded: No-Commit in Timeline** | timeline has no \`committed\` event; excluded from taxonomy (outliers/noise); reported separately |

## Metrics

### Weighted collaboration score

Weighted collaboration score is computed as:

```
Weighted_Events(actor) = Σ (event_count × event_weight)
Score = min(Weighted_Agent, Weighted_Human) / max(Weighted_Agent, Weighted_Human)
```

Event weights are defined in `src.analysis.workflows.EVENT_WEIGHTS` and documented in `manuscript/methodology.md` (§3.5.1).

### Revision cycle count

Revision cycle count is the number of REVIEW → REVISION → REVIEW loops under the temporal state machine (`assign_phases_temporal`).

## Exemplars and evidence standards

### Deterministic exemplars (avoid hard-coded counts)

Exemplar case studies (including phase breakdowns and computed metrics) are recorded in deterministic artifacts rather than described with hard-coded event counts in this protocol:

- `reports/evidence_report.md` (verified exemplars + definitions)
- `.tmp/evidence_stats.*` (dataset totals + uncertainty quantification + validation summaries)

### Evidence inclusion criteria (protocol-level)

For a PR to serve as evidence in narrative claims:
1. ✅ Actor identities are clear (Agent vs Human) under the project’s actor labeling rule
2. ✅ Collaboration type is unambiguous under the P1–P6 hierarchy
3. ✅ Supporting numbers (counts/percentages/statistics) are sourced from deterministic artifacts (`.tmp/evidence_stats.*`)
4. ✅ If GitHub UI verification is claimed, the PR URL is present and accessible

# Strategic Plan: Refining Paper Narration

**Goal:** Improve logical flow and reader motivation. Text carries the argument; tables and figures carry the evidence. Readers should feel led through a story, not through a data dump.

**Principle:** *Make readers motivated and interested*—every section should answer “why am I reading this?” and “what will I learn?” before delivering detail.

---

## 1. Introduction

### Current state
- Clear structure (context → gap → RQs → contributions → organization).
- Slightly generic opening (“landscape is undergoing transformation”).
- Contributions and abstract overlap; some readers may skim.

### Refinements

| Action | Detail |
|--------|--------|
| **Sharpen the hook** | Open with stakes, not scenery. Example: “AI coding agents now initiate, review, and merge pull requests—but we do not yet know whether they act as teammates or as tools in the hands of humans. The answer matters for tool design, team workflows, and trust.” |
| **Make the gap consequential** | After “event-centric perspective,” add one sentence: “Without a lifecycle-level view, we cannot tell how responsibility is partitioned between humans and agents across a full workflow.” |
| **Keep contributions tight** | List four contributions as now, but avoid repeating the abstract verbatim; use slightly different phrasing so the intro feels like a roadmap, not a duplicate. |
| **Delegate** | No tables/figures here; keep narrative only. |

### Logical flow
Context (why this matters) → Gap (what we don’t know) → RQs (what we ask) → Contributions (what we deliver) → Organization (how to read). Preserve this order.

---

## 2. Background and Related Work

### Current state
- Compact. AI agents, human–AI collaboration, process mining, gap are each covered briefly.
- Gap paragraph ends with “lifecycle-level collaboration” and “workflow-centric approach.”

### Refinements

| Action | Detail |
|--------|--------|
| **Keep it short** | Do not expand; background supports, does not dominate. |
| **End with a bridge** | Last sentence of Gap should feel like a direct lead-in: “This gap motivates our workflow-centric approach and the following methodology.” (Already present; ensure it’s the closing line.) |
| **Delegate** | No new tables; citations carry the weight. |

### Logical flow
What exists (agents, collaboration, process mining) → What’s missing (lifecycle-level collaboration) → Therefore we do X.

---

## 3. Methodology

### Current state
- Dataset: table exists; text also mentions “33,600” and pipeline. Good.
- Lifecycle model: full phase definitions in prose (PR created, Review, Revision, terminal outcomes). Dense.
- Actor classification: bullet list + validation "0.36% error rate (669 false positives…)."
- Taxonomy: table exists; text repeats criteria and mentions 15 PRs excluded (no-commit) plus 4,000 incomplete timelines.

### Refinements

| Action | Detail |
|--------|--------|
| **Lifecycle model** | State the model in one sentence with the arrow diagram. Add: “Phase definitions are given in Table~\ref{tab:phase-def}” (or in the figure caption of the pipeline/state machine). Move the sentence that scans the timeline and defines PR created / Review / Revision / terminal into a **compact table** (Phase | Definition) or into the caption of Figure~\ref{fig:pipeline-overview}. Text: 2–3 sentences max. |
| **Actor classification** | Keep the two bullets (Agent vs Human). Move the validation sentence to a footnote or one short line: "Validation against GitHub actor.type: 0.36\% error rate (see supplement)." |
| **Taxonomy** | Text: "We define six scenarios by initiator and terminal state (Table~\ref{tab:taxonomy}). We exclude 15 PRs with no committed event and 4,000 with incomplete timelines; analyses use 29,585 PRs. We classify tools as *Collaborator* (dominant Agent-Init, S1–S3) or *Assistant* (dominant Human-Init, S4–S6)." Remove the repeated criteria from the paragraph; the table holds them. |
| **Dataset composition** | Keep Table~\ref{tab:dataset}; in text say only “We use the AIDev dataset; composition by tool is in Table~\ref{tab:dataset}.” Event types: one line is enough. |

### Logical flow
What we did (workflow-centric, 33,600 PRs, 5 tools) → How we model (lifecycle + taxonomy) → Where the data and definitions live (tables/figures). Reader should leave methodology knowing the *concepts*, not memorizing numbers.

---

## 4. Results

### 4.1 Collaboration Type Distribution

| Action | Detail |
|--------|--------|
| **Reduce prose** | Current text lists χ², dof, p, Cramér's V and says “Full counts and 95% Wilson CIs… replication package.” Keep: “Table~\ref{tab:results} and Figure~\ref{fig:collab-dist} give the distribution by tool. The tool–scenario association is highly significant (Cramér's V = 0.51, p ≈ 0).” Remove repetition of “full counts and 95% Wilson CIs” if the table caption already says “95% Wilson CIs” and “full counts: replication package.” |
| **Delegate** | All percentages and counts → Table and Figure. Text states the test result and the main takeaway (two clusters visible). |

### 4.2 Paradigm Classification

| Action | Detail |
|--------|--------|
| **One headline sentence** | “Tools cluster into two paradigms: Collaborator (Cursor, Devin, Copilot) with 96–99% agent-initiated PRs, and Assistant (OpenAI, Claude) with 96–99.9% human-initiated PRs.” No need to repeat each tool’s percentage; the table has them. |
| **Devin S2** | Keep the Devin S2 paragraph as interpretive narrative; it explains an exception and motivates discussion. |

### 4.3 Phase Transitions and State Machine Diagrams

| Action | Detail |
|--------|--------|
| **Heavy delegation** | The two “Interpretation” sub-subsections (Transition Probabilities, Median Hours) list many numbers (0.908, 0.006, 0.52–0.54, 3.04 h, 17.87 h, etc.). **Move** these into: (1) figure captions for the five state machine figures (one sentence each: “Copilot: high P(Review|PR created), strong revision loop…”), and/or (2) a single **summary table** (e.g., “Key transition probabilities and median hours by paradigm”) in the main paper or supplement. |
| **Text replacement** | Replace the two long paragraphs with a short narrative (3–5 sentences): “Collaborator tools show high flow into Review and non-trivial revision loops; Assistant tools show direct resolution from PR created with little or no review. Median time in Review and in terminal states is longer for Collaborator tools. Figures~\ref{fig:sm-copilot}–\ref{fig:sm-claude} show the state machines; Table~\ref{tab:trans-summary} [if created] summarizes key transition probabilities and median hours.” Do not repeat every P(·|·) and median in the body. |
| **Logical flow** | “We computed transition probabilities and median hours per state. The pattern aligns with the paradigm split: [narrative]. See Figures X–Y.” |

### 4.4 Incomplete Timeline PRs

| Action | Detail |
|--------|--------|
| **Terminology and prevalence** | Keep the definition of “incomplete timeline” and the distinction from “Unmerged and closed.” Replace the long list “Copilot has the highest rate (42.4%, 2,107 of 4,971…) followed by…” with: “Table~\ref{tab:incomplete-timeline} shows prevalence by tool; Copilot has the highest rate (42.4%), OpenAI the lowest (4.3%).” |
| **Terminator / last event** | One sentence: “For incomplete PRs we record no resolver; the terminator (actor of the last event) and last event type indicate how activity ended (see supplement).” Move the sentence listing “copilot_work_finished (558), commented (275)…” to supplement or figure caption. |
| **Paradigm correlation** | Shorten the three bold paragraphs (Collaborator factors, Assistant factors, Implications) into one short paragraph: “Incomplete timeline rates correlate partially with paradigm (Collaborator tools higher on average) but with exceptions (e.g., Claude 26.1%). This suggests both paradigm-level and tool-specific factors (see Table~\ref{tab:incomplete-timeline} and~\ref{tab:incomplete-timeline-breakdown}).” |
| **Sub-categorization** | Already condensed. Keep: definition of Open / Abandoned / Incomplete Data, pointer to Table~\ref{tab:incomplete-timeline-breakdown}, one sentence on paradigm pattern, “Detailed heuristics in supplement.” |

### 4.5 Outcome Measures and Success Patterns

| Action | Detail |
|--------|--------|
| **Compress** | First paragraph: “S1 and S4 dominate and have 100% merge rate; S2 is rare (14 PRs). Merged scenarios are 100% merged by definition; Not-Merged (S3, S6) are 0%.” Second paragraph: One sentence on S5 (rare, selective delegation), one on complexity (S3 high, S4 low), one on terminator pattern; “Details in supplement.” |
| **Delegate** | Merge-rate breakdown, complexity stats, terminator counts → supplement or a single small table. |

### 4.6 Temporal Analysis

| Action | Detail |
|--------|--------|
| **Keep as is** | One sentence is appropriate. |

### Results: overall logical flow

1. **Distribution** → “Here’s how the six scenarios look across tools; the split is significant.”
2. **Paradigms** → “Tools fall into two clusters: Collaborator vs Assistant.”
3. **Phase transitions** → “Workflow dynamics match that split: review-heavy vs direct resolution; see figures.”
4. **Incomplete timelines** → “A nontrivial share of PRs lack terminal events; here’s how we classify and what it suggests.”
5. **Outcomes** → “Merge success and complexity align with the taxonomy.”
6. **Temporal** → “Data are recent; generalizability may be limited.”

Add a **one-sentence bridge** before Discussion: “Taken together, these results support a clear bifurcation of tools into Collaborator and Assistant paradigms, with distinct workflow dynamics and implications for practice.”

---

## 5. Discussion

### Current state
- Two paradigms summarized; link to Raisch & Krakowski and trust/complacency.
- Implications for practitioners and researchers in list form.

### Refinements

| Action | Detail |
|--------|--------|
| **Open with payoff** | First sentence: “Our results show that AI coding tools fall into two paradigms—Collaborator and Assistant—with different workflow dynamics and different implications for how teams should adopt and review agent output.” Then unpack. |
| **Keep paradigm paragraphs** | Collaborator vs Assistant summaries are readable; optional: trim repeated statistics (readers have seen them in Results). |
| **Implications** | If page limit is tight, consider moving the full numbered lists to supplement and keeping 2–3 headline recommendations in the main text. Otherwise keep; the lists are actionable and support motivation. |
| **Delegate** | No new tables required; optional “Recommendation → Rationale” table in supplement for practitioners. |

### Logical flow
What we found (two paradigms) → Why it matters (augmentation, trust, complacency) → What to do (practice + research).

---

## 6. Threats to Validity and Conclusion

### Current state
- Short and clear.

### Refinements

| Action | Detail |
|--------|--------|
| **No structural change** | Keep brevity. |
| **Conclusion** | Optional: first sentence could echo the payoff (“We analyzed 33,600 PR lifecycles and found that tools cluster into two paradigms…”) then contributions and availability. |

---

## 7. Cross-Cutting Principles

1. **So what first**  
   Start each major section with why the reader should care or what they will learn (one sentence).

2. **Signposting**  
   Use short bridging sentences: “We now turn to…”; “Taken together…”; “This has two implications.”

3. **Tables and figures do the work**  
   If a number appears in a table or figure, the text should not repeat it unless it’s the one number you want the reader to remember (e.g., Cramér's V = 0.51). Prefer “see Table X” or “Figure Y shows that….”

4. **One idea per paragraph**  
   Especially in Results: one paragraph = one finding or one contrast. Avoid packing multiple statistics into one paragraph when they can live in a table.

5. **Motivation in the intro**  
   The introduction should make the gap feel consequential (design, adoption, trust), not only “prior work looked at events.”

---

## 8. Implementation Checklist

- [ ] Introduction: add stakes in opening; one-sentence “consequential gap”; contributions distinct from abstract.
- [ ] Methodology: phase definitions → table or figure caption; actor validation → footnote/supplement; taxonomy paragraph trimmed to pointer + exclusion + paradigm labels.
- [ ] Results §4.1: one short paragraph + table/figure reference; no duplicate stats.
- [ ] Results §4.2: one headline sentence; keep Devin S2 narrative.
- [ ] Results §4.3: create summary table or enrich figure captions; replace long interpretation with 3–5 sentence narrative + “see Figures X–Y.”
- [ ] Results §4.4: prevalence → “see Table”; terminator detail → supplement; paradigm correlation shortened to one paragraph.
- [ ] Results §4.5: compress to 2 short paragraphs; details → supplement.
- [ ] Results: add one-sentence bridge before Discussion.
- [ ] Discussion: open with payoff sentence; optional trim of repeated stats.
- [ ] Conclusion: optional payoff echo in first sentence.

---

*This plan is a Layer 1–2 directive for narration refinement. Apply it when revising the manuscript; verify against the review rubric (e.g., no hallucinated numbers) when finalizing.*

# Peer Review Rubric (Layer 4)

This document defines the criteria used by the Peer Review layer to audit research outputs.

## Acceptance Criteria

### 1. Empirical Accuracy
- [ ] All statistics match generated artifacts (e.g., `archive/dataset_summary.json`, `.tmp/train_report.md`) or are regenerated deterministically from `data/raw/`
- [ ] PR counts verified against dataset
- [ ] Percentages calculated correctly
- [ ] No hallucinated numbers

### 2. Methodology Consistency
- [ ] Follows `config/methodology.md` (and, where relevant, the reference notebook implementation in `notebooks/methodology_walkthrough.ipynb`)
- [ ] Uses correct terminology (Agent, not “ML”) in prose and headings
- [ ] Classification logic matches the stated implementation (explicitly note whether results come from `src/` code, notebooks, or legacy `archive/` scripts)

### 3. Evidence Quality
- [ ] GitHub URLs are valid and accessible
- [ ] Exemplars are representative, not cherry-picked
- [ ] All collaboration types have examples

### 4. Citation Integrity
- [ ] All references exist in `data/external/` folder
- [ ] No fabricated citations
- [ ] Proper attribution format (IEEE)

### 5. Format Compliance
- [ ] Markdown properly structured
- [ ] Tables render correctly
- [ ] Images have valid paths

## Rejection Criteria

Any of the following results in **REJECTION**:
1. Numerical discrepancy with execution output
2. Missing or broken GitHub links
3. Terminology inconsistency
4. Methodology deviation from directives

## Audit Workflow

```
1. Draft complete → Run the relevant audit script (e.g., `archive/execution/audit_evidence.py` for the legacy evidence report pipeline)
2. Check passes → Approved for delivery
3. Check fails → Return to Layer 2 with revision list
```

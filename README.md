# Collaborator or Assistant? How AI Coding Agents Partition Work Across Pull Request Lifecycles

Research home for the AIware 2026 paper of the same name. This repository gathers, in one place, the
**paper**, the **conference talks**, the **poster**, and the **replication package** (raw PR-timeline
data and the methodology notebook) so that other researchers can read, present, and reproduce the work.

- **Authors:** Young Jo(seph) Chung and Safwat Hassan (University of Toronto)
- **Venue:** AIware '26 — ACM International Conference on AI-Powered Software Engineering, July 6–7, 2026, Montreal, Canada
- **Contact:** jo.chung@utoronto.ca

## Abstract

When AI coding agents open branches and submit pull requests (PRs), two questions co-determine oversight
design: who *starts* the work (operational agency) and who *authorizes* its completion (merge governance).
This study shows that tools occupy a **Collaborator–Assistant spectrum** on initiation and review routing,
while merge governance remains predominantly human across five tools (OpenAI Codex, GitHub Copilot, Devin,
Cursor, Claude Code). We analyze **29,585 PR lifecycles** using an **Initiator × Approver** taxonomy with
six interaction scenarios; lifecycle reconstruction supplies the *how* behind those roles. Collaborator
tools (Cursor, Devin, Copilot) concentrate agent initiation with human review on the path to merge;
Assistant tools (OpenAI, Claude) concentrate human initiation, and a large share of PRs resolve without a
recorded review step. Across the spectrum, agency and governance **decouple**: Collaborator workflows are
≥96% agent-initiated, yet terminal merge authority remains almost exclusively human. Where automation
executes a merge, logs record the executor but not the decision-maker, marking a boundary of observation.
The paper contributes the taxonomy, per-tool state machines, and this replication package.

## What is in this repository

| Path | Contents |
| --- | --- |
| [`paper/`](paper/) | The published paper (PDF) and its camera-ready LaTeX source. |
| [`talk/`](talk/) | The 5-slide lightning talk and the full conference talk (PDF + PowerPoint). |
| [`poster/`](poster/) | The 24×36 in. conference poster (PDF + PowerPoint). |
| [`notebooks/`](notebooks/) | The methodology notebook that reconstructs PR lifecycles and computes the metrics. |
| [`data/`](data/) | Raw per-tool PR-timeline event logs used by the notebook (Git LFS). |
| [`CITATION.cff`](CITATION.cff) | Machine-readable citation metadata. |
| [`LICENSE`](LICENSE) | MIT license for the code, notebooks, and documentation in this repository. |

### Paper

[`paper/AIWare2026_AI_Coding_Agents_Lifecycles.pdf`](paper/AIWare2026_AI_Coding_Agents_Lifecycles.pdf)
is the authoritative version. The camera-ready LaTeX source lives in
[`paper/source/`](paper/source/); it uses the ACM `acmart` class (`sigconf`), which is available from
[CTAN](https://ctan.org/pkg/acmart). References are embedded in the `.tex` file, so no external `.bib` is
required to compile.

### Talk

- [`talk/lightning/`](talk/lightning/) — the 5-slide / ~4:30 lightning talk (speaker notes embedded in the `.pptx`).
- [`talk/full-talk/`](talk/full-talk/) — the longer Montreal conference deck, with the per-tool
  state-machine figures under [`talk/full-talk/figures/`](talk/full-talk/figures/).

Both talks are provided as PDF (for viewing) and PowerPoint (for editing).

### Poster

[`poster/`](poster/) holds the conference poster as PDF and editable PowerPoint. It tells the six-scenario
Initiator × Approver story end to end.

## Replication package

The replication package has two parts: the **raw timeline data** (`data/`) and the **methodology
notebook** (`notebooks/`).

### Data provenance

The PR-timeline logs in `data/` are derived from the **AIDev** dataset of agent-associated pull requests
(Li, Zhang & Hassan), released on Hugging Face as
[`hao-li/AIDev`](https://huggingface.co/datasets/hao-li/AIDev) under CC-BY-4.0. The files here cover the
five agents in AIDev's curated (>100-star) subset:

```
data/pr_timelines_Claude_Code.json
data/pr_timelines_Copilot.json
data/pr_timelines_Cursor.json
data/pr_timelines_Devin.json
data/pr_timelines_OpenAI_Codex.json
```

Each file is a JSON object keyed by PR identifier, whose values are arrays of timeline event objects. The
paper's analytic sample of 29,585 lifecycles is obtained after the exclusions documented in the notebook
and in Section 3 of the paper (e.g., PRs with no commit event). These files are stored with **Git LFS**.

### How to reproduce

1. Install [Git LFS](https://git-lfs.com/) and clone with the large files:

   ```bash
   git lfs install
   git clone https://github.com/UtopianYoungChung/AIWare2026.git
   cd AIWare2026
   git lfs pull
   ```

2. Create an environment and install the analysis dependencies:

   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
   pip install pandas numpy jupyter
   ```

3. Open the methodology notebook and run it top to bottom:

   ```bash
   jupyter notebook notebooks/methodology.ipynb
   ```

### What the notebook does

`notebooks/methodology.ipynb` walks through the analysis end to end:

1. **Loads** the raw per-tool PR-timeline JSON from `data/`.
2. **Classifies actors** as Agent or Human, using GitHub's `actor.type == "Bot"` when present and falling
   back to login-naming patterns otherwise.
3. **Reconstructs a 5-phase PR lifecycle** (Initiation → Development → Review → Revision → Resolution) from
   the event sequence.
4. **Computes the metrics** behind the paper's figures (e.g., weighted collaboration scores, revision
   cycles, and the per-tool state machines).

`notebooks/methodology_ver01.ipynb` is retained as an earlier version for provenance.

> **Reproducibility note.** `committed` and `reviewed` events in the AIDev timelines carry no timestamps,
> so phase boundaries that depend on those events are derived from event *sequence* rather than wall-clock
> time. As a result, count- and proportion-based results (taxonomy distribution, routing/resolution rates,
> and the association statistics) reproduce closely, while exact median-duration figures depend on the
> full pipeline's timestamp joins.

## Citation

If you use this work, please cite the paper. See [`CITATION.cff`](CITATION.cff) for machine-readable
metadata, or use:

```bibtex
@inproceedings{chung2026collaborator,
  title     = {Collaborator or Assistant? How AI Coding Agents Partition Work Across Pull Request Lifecycles},
  author    = {Chung, Young Jo(seph) and Hassan, Safwat},
  booktitle = {Proceedings of the ACM International Conference on AI-Powered Software Engineering (AIware '26)},
  year      = {2026},
  address   = {Montreal, Canada}
}
```

Please also cite the underlying dataset (AIDev, `hao-li/AIDev`, CC-BY-4.0) when you use the data in `data/`.

## License

Code, notebooks, and documentation in this repository are released under the [MIT License](LICENSE). The
data in `data/` is derived from the AIDev dataset and remains subject to its original **CC-BY-4.0** terms.
The paper, talk, and poster PDFs are the authors' published/accepted artifacts and are shared here for
academic use with attribution.

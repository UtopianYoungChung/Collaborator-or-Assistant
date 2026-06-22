# Data Access

## Dataset

The analysis uses the **AIDev dataset** (Li, Zhang & Hassan, 2025), which provides PR timeline data from GitHub repositories where AI coding agents participated in development activities.

**Citation:**
> H. Li, H. Zhang, and A. E. Hassan. 2025. AIDev: Studying AI Coding Agents on GitHub. In *Proc. IEEE/ACM Int. Conf. Mining Software Repositories (MSR)*. Queen's University, Canada.

## Required Files

Place the following JSON files in `data/raw/` (relative to the project root):

| File | Approx. size |
|------|--------------|
| `pr_timelines_Claude_Code.json` | ~19 MB |
| `pr_timelines_Copilot.json` | ~257 MB |
| `pr_timelines_Cursor.json` | ~47 MB |
| `pr_timelines_Devin.json` | ~208 MB |
| `pr_timelines_OpenAI_Codex.json` | ~307 MB |

**Total:** ~838 MB

## Obtaining the Data

1. **Replication package dataset (AIWare 2026)**: The complete dataset for this paper is available at: **https://doi.org/10.6084/m9.figshare.31343038**. This includes the PR timeline JSON files used to reproduce all analysis and figures.

2. **AIDev dataset**: The underlying AIDev dataset is described in the AIDev paper (MSR 2025). Check the paper or authors' institutional page (Queen's University) for the original release.

3. **If you have the full AIWare repository**: The raw JSON files may already be present in `data/raw/`. Verify with:
   ```bash
   dir data\raw\pr_timelines_*.json   # Windows
   ls data/raw/pr_timelines_*.json     # Unix/macOS
   ```

**Format**: Each file is a JSON object. Keys are PR identifiers (e.g., `"3193888615.json"`); values are arrays of timeline event objects with fields such as `sha`, `author`, `event`, `timestamp`, `html_url`, etc.

## Verification

After placing the files, run the pipeline. The evidence statistics step will report totals per tool (see `config/progress_reconciliation.md` for expected ranges). Expected raw totals: Cursor ~1,541; Devin ~4,829; Copilot ~4,971; Claude Code ~459; OpenAI ~21,800; **Total 33,600**.

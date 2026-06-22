@echo off
REM Replication package: run full pipeline from AIWare project root
REM Usage: From project root, run: replication_package\run_replication.bat

cd /d "%~dp0\.."
if not exist "src\analysis\evidence_stats.py" (
    echo ERROR: Run this script from the AIWare project root (parent of replication_package).
    exit /b 1
)

echo === Step 1: Evidence statistics ===
python -m src.analysis.evidence_stats --out-json .tmp\evidence_stats.json --out-md .tmp\evidence_stats.md
if errorlevel 1 exit /b 1

echo.
echo === Step 2: Phase transition probabilities ===
python -m src.analysis.network_extraction --output-dir .tmp\networks --exclude-incomplete
if errorlevel 1 exit /b 1

echo.
echo === Step 3: Within-tool comparison (human-initiated PRs only; construct validity) ===
python -m src.analysis.within_tool_comparison
if errorlevel 1 exit /b 1

echo.
echo === Step 4: Temporal analysis (94%% Q2-Q3 concentration) ===
python -m src.analysis.temporal_trends --out-json .tmp/temporal_analysis.json
if errorlevel 1 exit /b 1

echo.
echo === Step 5: Downsampling robustness (OpenAI to Copilot n; Cramer V stability) ===
python -m src.analysis.downsample_robustness --n-match 4885 --seeds 10 --output .tmp/downsample_robustness.json
if errorlevel 1 exit /b 1

echo.
echo === Step 6: Within-repository control (Discussion / Threats) ===
python -m src.analysis.within_repository_analysis --min-prs 5 --repo-rule all_five_tools --out-json .tmp/within_repository_analysis.json --out-md .tmp/within_repository_analysis.md
if errorlevel 1 exit /b 1

echo.
echo === Step 7: Collaboration distribution figure ===
python -m src.analysis.plot_collaboration_distribution
if errorlevel 1 exit /b 1

echo.
echo === Step 8: State machine figures ===
python -m src.analysis.plot_state_machines
if errorlevel 1 exit /b 1

echo.
echo === Replication complete ===
echo Outputs: .tmp\evidence_stats.*, .tmp\networks\, .tmp\within_tool_human_initiated_report.*, .tmp\temporal_analysis.json
echo          .tmp\downsample_robustness.json, .tmp\within_repository_analysis.json/.md
echo          Submissions\fig_collab_distribution.pdf, Submissions\fig_state_machine_*.pdf
echo          .tmp\networks\s2_path_analysis.md (RQ3 path classification)

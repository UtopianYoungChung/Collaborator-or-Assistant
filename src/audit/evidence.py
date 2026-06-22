"""
Layer 4: Peer Review Audit Script

Validates evidence report against execution outputs.
Implements the "Reviewer 2" function from the 4-layer architecture.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_REPORT = PROJECT_ROOT / 'reports' / 'evidence_report.md'
REVIEWS_DIR = PROJECT_ROOT / 'reviews'


def check_statistics_accuracy():
    """Verify statistics in evidence report match actual data."""
    issues = []
    
    # Deterministic stats from the current canonical analyzer
    from src.analysis.evidence_stats import compute_evidence_stats
    stats = compute_evidence_stats()
    
    # Check if report exists
    if not EVIDENCE_REPORT.exists():
        issues.append("ERROR: Evidence report not found")
        return issues
    
    # Read report and verify numbers
    content = EVIDENCE_REPORT.read_text(encoding='utf-8')
    
    # Check total PR counts (accept either bold or plain tool names in table)
    for tool, expected_total in stats.totals_by_tool.items():
        pat = rf"(\*\*)?{re.escape(tool)}(\*\*)?\s*\|\s*{expected_total:,}\s*\|"
        if not re.search(pat, content):
            issues.append(f"WARN: {tool} total PR count not found or mismatched (expected {expected_total:,})")
    
    # Check overall total
    total_all = sum(stats.totals_by_tool.values())
    if not re.search(rf"TOTAL\*\*\s*\|\s*\*\*{total_all:,}\*\*", content) and not re.search(
        rf"TOTAL\s*\|\s*{total_all:,}\s*\|", content
    ):
        issues.append(f"WARN: Overall TOTAL count not found or mismatched (expected {total_all:,})")
    
    return issues


def check_github_urls():
    """Verify GitHub URLs are properly formatted."""
    issues = []
    
    if not EVIDENCE_REPORT.exists():
        return issues
    
    content = EVIDENCE_REPORT.read_text(encoding='utf-8')
    
    # Find all GitHub URLs
    github_pattern = r'https://github\.com/[\w\-\.]+/[\w\-\.]+/pull/\d+'
    urls = re.findall(github_pattern, content)
    
    if len(urls) < 50:
        issues.append(f"WARN: Only {len(urls)} GitHub URLs found, expected 60+")
    
    return issues


def check_terminology():
    """Ensure ML → Agent terminology update."""
    issues = []
    
    if not EVIDENCE_REPORT.exists():
        return issues
    
    content = EVIDENCE_REPORT.read_text(encoding='utf-8')
    
    # Check for old terminology
    ml_patterns = ['ML-Initiated', 'ML Events', 'ML-Autonomous', 'ML-Assisted']
    for pattern in ml_patterns:
        if pattern in content:
            issues.append(f"TERM: Found outdated terminology '{pattern}', should use 'Agent'")
    
    # Check for correct terminology
    agent_patterns = ['Agent-Initiated', 'Agent Events', 'Agent-Autonomous']
    for pattern in agent_patterns:
        if pattern not in content:
            issues.append(f"WARN: Expected terminology '{pattern}' not found")
    
    return issues


def check_collaboration_types():
    """Verify collaboration types are documented."""
    issues = []
    
    if not EVIDENCE_REPORT.exists():
        return issues
    
    content = EVIDENCE_REPORT.read_text(encoding='utf-8')
    
    required_types = [
        'Agent-Initiated + Human-Resolved',
        'Human-Initiated + Agent-Assisted',
        'Agent-Autonomous',
        'Human-Led',
        'Balanced Collaboration',
        'Unclassified',
    ]
    
    for ctype in required_types:
        if ctype not in content:
            issues.append(f"MISSING: Collaboration type '{ctype}' not documented")
    
    return issues


def check_scenario_mutual_exclusivity():
    """
    Verify that scenario (collaboration-type) assignment has no overcounts.

    Loads workflows from the canonical analyzer and asserts that the sum of
    type counts equals the number of PRs—each PR is counted exactly once.
    """
    issues = []
    try:
        from src.analysis.outcome_analysis import load_all_workflows
        from src.analysis.workflows import verify_scenario_mutual_exclusivity
    except ImportError as e:
        issues.append(f"ERROR: Cannot run scenario exclusivity check: {e}")
        return issues

    try:
        workflows = load_all_workflows()
    except Exception as e:
        issues.append(f"ERROR: Failed to load workflows for exclusivity check: {e}")
        return issues

    result = verify_scenario_mutual_exclusivity(workflows, raise_on_fail=False)
    if not result["passed"]:
        issues.append(
            f"ERROR: Scenario mutual exclusivity violated: sum of type counts ({result['sum_by_type']}) "
            f"!= number of workflows ({result['total']}). Overcount or undercount detected."
        )
    return issues


def check_uncertainty_reporting():
    """Check that the evidence report includes uncertainty quantification (CIs)."""
    issues = []
    if not EVIDENCE_REPORT.exists():
        return issues
    content = EVIDENCE_REPORT.read_text(encoding="utf-8")
    if "CI" not in content and "confidence interval" not in content.lower():
        issues.append("WARN: No CI/confidence-interval text found in evidence report")
    return issues


def check_ml_limitations_statement():
    """Check that ML model limitations are acknowledged if ML is referenced."""
    issues = []
    if not EVIDENCE_REPORT.exists():
        return issues
    content = EVIDENCE_REPORT.read_text(encoding="utf-8")
    mentions_ml = ("Naive Bayes" in content) or ("ML model" in content) or ("ml " in content.lower())
    if mentions_ml:
        if "limitation" not in content.lower():
            issues.append("WARN: Evidence report references ML but lacks an explicit limitations statement")
    return issues


def generate_review_log(issues: list) -> str:
    """Generate peer review log."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    log = []
    log.append(f"# Peer Review Audit Log")
    log.append(f"**Timestamp:** {timestamp}")
    log.append(f"**Artifact:** {EVIDENCE_REPORT}")
    log.append("")
    
    if issues:
        log.append("## Issues Found")
        log.append("")
        for issue in issues:
            if issue.startswith("ERROR"):
                log.append(f"- ❌ {issue}")
            elif issue.startswith("TERM"):
                log.append(f"- ⚠️ {issue}")
            elif issue.startswith("WARN"):
                log.append(f"- ⚡ {issue}")
            elif issue.startswith("MISSING"):
                log.append(f"- 🔍 {issue}")
            else:
                log.append(f"- {issue}")
        log.append("")
        log.append("**Status: REVISION REQUIRED**")
    else:
        log.append("## Result")
        log.append("")
        log.append("✅ All checks passed")
        log.append("")
        log.append("**Status: APPROVED**")
    
    return "\n".join(log)


def run_audit():
    """Run full peer review audit."""
    print("Layer 4: Peer Review Audit")
    print("=" * 60)
    
    all_issues = []
    
    print("Checking statistics accuracy...")
    all_issues.extend(check_statistics_accuracy())
    
    print("Checking GitHub URLs...")
    all_issues.extend(check_github_urls())
    
    print("Checking terminology...")
    all_issues.extend(check_terminology())
    
    print("Checking collaboration types...")
    all_issues.extend(check_collaboration_types())

    print("Checking scenario mutual exclusivity (no double counts)...")
    all_issues.extend(check_scenario_mutual_exclusivity())

    print("Checking uncertainty reporting...")
    all_issues.extend(check_uncertainty_reporting())

    print("Checking ML limitations statement...")
    all_issues.extend(check_ml_limitations_statement())
    
    # Generate review log
    log = generate_review_log(all_issues)
    
    # Save to reviews directory
    REVIEWS_DIR.mkdir(exist_ok=True)
    log_file = REVIEWS_DIR / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    log_file.write_text(log, encoding='utf-8')
    
    print("")
    print(log)
    print("")
    print(f"Review log saved to: {log_file}")
    
    return len(all_issues) == 0


if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)

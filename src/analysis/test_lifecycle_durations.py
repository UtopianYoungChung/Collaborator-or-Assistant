import sys
from pathlib import Path
from datetime import datetime
from typing import List

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from analysis.workflows import WorkflowEvent, assign_phases_temporal, WorkflowPhaseName

def test_lifecycle_durations():
    # Helper to create timestamps
    def ts(hour: int) -> str:
        return f"2025-07-01T{hour:02d}:00:00Z"

    events = [
        # PR created phase (from first event until first review after commit)
        WorkflowEvent(0, "labeled", "human_user", "User", False, ts(0)),
        WorkflowEvent(1, "committed", "human_user", "User", False, ts(1)),
        # Transition to Review at ts(3)
        WorkflowEvent(2, "reviewed", "reviewer_bot", "Bot", True, ts(3), "COMMENTED"),
        # Transition to Revision at ts(5)
        WorkflowEvent(3, "reviewed", "human_reviewer", "User", False, ts(5), "CHANGES_REQUESTED"),
        WorkflowEvent(4, "committed", "human_user", "User", False, ts(6)),
        # Transition back to Review at ts(8)
        WorkflowEvent(5, "review_requested", "human_user", "User", False, ts(8)),
        # Terminal transition to Resolution at ts(10)
        WorkflowEvent(6, "merged", "human_reviewer", "User", False, ts(10))
    ]

    phases, revision_cycles, durations = assign_phases_temporal(events)

    print(f"Revision Cycles: {revision_cycles}")
    for name, dur in durations.items():
        print(f"Phase {name}: {dur:.2f}h")

    # Expectations: PR created 0->3 (3h), Review 3->5 (2h), Revision 5->8 (3h), Review 8->10 (2h)
    assert abs(durations['pr_created'] - 3.0) < 0.01
    assert abs(durations['review'] - 4.0) < 0.01
    assert abs(durations['revision'] - 3.0) < 0.01
    assert revision_cycles == 1  # Saw request after changes requested and commit

    print("\n✓ Lifecycle duration and transition test passed!")

if __name__ == "__main__":
    test_lifecycle_durations()

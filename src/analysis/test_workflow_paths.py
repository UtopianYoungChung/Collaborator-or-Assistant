"""
Tests for RQ3: classify_workflow_path() – verifies all eight canonical paths.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from analysis.workflows import (
    WorkflowEvent,
    WorkflowPath,
    get_phase_transition_sequence,
    classify_workflow_path,
    get_revision_cycle_count,
)


def _ts(hour: int) -> str:
    return f"2025-07-01T{hour:02d}:00:00Z"


def _make_events(specs) -> list:
    """Create WorkflowEvent list from compact specs: (event_type, review_state|None)."""
    events = []
    for i, spec in enumerate(specs):
        if len(spec) == 2:
            etype, rstate = spec
        else:
            etype = spec[0]
            rstate = None
        events.append(
            WorkflowEvent(i, etype, "actor", "User", False, _ts(i), rstate)
        )
    return events


def test_T3_direct_merge():
    """PR Created → Merge (no review at all)."""
    events = _make_events([
        ("committed",),
        ("merged",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T3, f"Expected T3, got {path}"


def test_T4_direct_close():
    """PR Created → Close (no review)."""
    events = _make_events([
        ("committed",),
        ("closed",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T4, f"Expected T4, got {path}"


def test_T1_review_then_merge():
    """PR Created → Review → Merge (reviewed, no revision)."""
    events = _make_events([
        ("committed",),
        ("reviewed", "APPROVED"),
        ("merged",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T1, f"Expected T1, got {path}"


def test_T2_review_then_close():
    """PR Created → Review → Close (reviewed, no revision, unmerged)."""
    events = _make_events([
        ("committed",),
        ("reviewed", "COMMENTED"),
        ("closed",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T2, f"Expected T2, got {path}"


def test_T5a_one_revision_cycle_merge():
    """PR Created → Review → Revision (1 cycle) → Merge."""
    events = _make_events([
        ("committed",),
        ("reviewed", "APPROVED"),     # → Review
        ("reviewed", "CHANGES_REQUESTED"),  # → Revision
        ("committed",),               # revision work
        ("review_requested",),        # → back to Review
        ("merged",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T5a, f"Expected T5a, got {path}"


def test_T5b_two_revision_cycles_merge():
    """PR Created → Review → Revision → Review → Revision → Merge."""
    events = _make_events([
        ("committed",),
        ("reviewed", "APPROVED"),           # → Review
        ("reviewed", "CHANGES_REQUESTED"),  # → Revision (1st)
        ("committed",),
        ("review_requested",),              # → Review
        ("reviewed", "CHANGES_REQUESTED"),  # → Revision (2nd)
        ("committed",),
        ("review_requested",),              # → Review
        ("merged",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T5b, f"Expected T5b, got {path}"


def test_T6a_one_revision_cycle_close():
    """PR Created → Review → Revision (1 cycle) → Close."""
    events = _make_events([
        ("committed",),
        ("reviewed", "APPROVED"),
        ("reviewed", "CHANGES_REQUESTED"),
        ("committed",),
        ("review_requested",),
        ("closed",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T6a, f"Expected T6a, got {path}"


def test_T6b_two_revision_cycles_close():
    """PR Created → Review → Revision → Review → Revision → Close."""
    events = _make_events([
        ("committed",),
        ("reviewed", "APPROVED"),
        ("reviewed", "CHANGES_REQUESTED"),
        ("committed",),
        ("review_requested",),
        ("reviewed", "CHANGES_REQUESTED"),
        ("committed",),
        ("review_requested",),
        ("closed",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    assert path == WorkflowPath.T6b, f"Expected T6b, got {path}"


def test_empty_transitions():
    """Edge case: no transitions → UNKNOWN."""
    assert classify_workflow_path([]) == WorkflowPath.UNKNOWN


def test_revision_cycle_count():
    """get_revision_cycle_count counts Review→Revision transitions."""
    transitions = [
        ("pr_created", "review"),
        ("review", "revision"),        # 1
        ("revision", "review"),
        ("review", "revision"),        # 2
        ("revision", "review"),
        ("review", "merged_and_closed"),
    ]
    assert get_revision_cycle_count(transitions) == 2


def test_direct_to_revision_path():
    """PR Created → Revision (CHANGES_REQUESTED as first review) → ... → Merge."""
    events = _make_events([
        ("committed",),
        ("reviewed", "CHANGES_REQUESTED"),  # goes directly to Revision
        ("committed",),
        ("review_requested",),              # → Review
        ("merged",),
    ])
    seq = get_phase_transition_sequence(events)
    path = classify_workflow_path(seq)
    # This enters revision once (directly from pr_created), so T5a
    assert path == WorkflowPath.T5a, f"Expected T5a, got {path}"


if __name__ == "__main__":
    tests = [
        test_T3_direct_merge,
        test_T4_direct_close,
        test_T1_review_then_merge,
        test_T2_review_then_close,
        test_T5a_one_revision_cycle_merge,
        test_T5b_two_revision_cycles_merge,
        test_T6a_one_revision_cycle_close,
        test_T6b_two_revision_cycles_close,
        test_empty_transitions,
        test_revision_cycle_count,
        test_direct_to_revision_path,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed")
    if passed < len(tests):
        sys.exit(1)
    print("✓ All workflow path classification tests passed!")

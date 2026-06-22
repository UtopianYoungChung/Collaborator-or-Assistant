"""
Workflow-Centric Collaboration Analysis for AIDev Research

Analyzes complete PR workflows to demonstrate human-AI collaboration,
replacing the misleading n-gram pattern approach.
"""

import json
import os
import sys
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Iterable
from enum import Enum
import re

# Configure encoding for Windows (only in non-notebook environments)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    # In Jupyter notebooks, sys.stdout doesn't support reconfigure
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_dataset_dir() -> Path:
    """
    Resolve dataset location with environment override and layout fallback.

    Priority:
    1) AIWARE_DATA_DIR (if set and exists)
    2) REPO_ROOT/data/raw
    3) REPO_ROOT/data
    """
    env_dir = os.getenv("AIWARE_DATA_DIR")
    if env_dir:
        env_path = Path(env_dir).expanduser().resolve()
        if env_path.exists():
            return env_path
    raw_path = REPO_ROOT / "data" / "raw"
    if raw_path.exists():
        return raw_path
    data_path = REPO_ROOT / "data"
    if data_path.exists():
        return data_path
    return raw_path


DATASET_DIR = _resolve_dataset_dir()

FILES = {
    'Claude': 'pr_timelines_Claude_Code.json',
    'Copilot': 'pr_timelines_Copilot.json',
    'Cursor': 'pr_timelines_Cursor.json',
    'Devin': 'pr_timelines_Devin.json',
    'OpenAI': 'pr_timelines_OpenAI_Codex.json'
}

# Bot identification patterns (heuristic fallback when actor type metadata is absent)
BOT_PATTERNS = ['[bot]', 'bot', 'copilot', 'devin', 'cursor', 'codex', 'openai', 'claude']

# Initiator is defined as the actor of the first commit (first "committed" event);
# every PR requires commit(s), so this identifies who initiated the PR. See manuscript/methodology.md §3.3.4.
# Legacy: INITIATOR_SIGNIFICANT_EVENTS kept for reference/sensitivity analyses only; initiator role uses first commit.
INITIATOR_SIGNIFICANT_EVENTS = frozenset({
    'committed', 'assigned', 'commented', 'review_requested',
    'labeled', 'renamed', 'ready_for_review', 'reviewed', 'deployed',
    'head_ref_force_pushed', 'base_ref_force_pushed', 'mentioned', 'subscribed',
    'convert_to_draft', 'milestoned', 'unlabeled', 'review_request_removed',
    'added_to_merge_queue', 'removed_from_merge_queue', 'locked', 'unlocked',
    'reopened', 'unassigned', 'connected', 'disconnected', 'referenced',
})

# Weighted event scheme documented in `notebooks/DATA_PIPELINE.md` and `manuscript/methodology.md`.
EVENT_WEIGHTS = {
    'committed': 3.0,
    'reviewed': {
        'CHANGES_REQUESTED': 2.0,
        'APPROVED': 1.5,
        'COMMENTED': 1.0,
    },
    'commented': 1.0,
    'review_requested': 0.5,
    'assigned': 0.25,
    'labeled': 0.25,
    'default': 0.5,
}


@contextmanager
def temporary_event_weights(event_weights: dict):
    """
    Temporarily override the module-level EVENT_WEIGHTS.

    This is intended for deterministic *sensitivity analysis* scripts, and should
    not be used by the canonical evidence pipeline.
    """
    global EVENT_WEIGHTS
    old = EVENT_WEIGHTS
    EVENT_WEIGHTS = event_weights
    try:
        yield
    finally:
        EVENT_WEIGHTS = old


class WorkflowPhaseName(str, Enum):
    PR_CREATED = "pr_created"
    REVIEW = "review"
    REVISION = "revision"
    RESOLUTION = "resolution"


class CollaborationType(Enum):
    """
    Observable collaboration: initiator × merge outcome (merge-focused taxonomy).
    Merged PRs split by who merged (Human/Agent); non-merged (closed or incomplete timeline) collapsed.
    Six values are **scenarios** (S1–S6); one value is the **excluded cluster**, not a scenario.
    """
    # Agent-initiated (S1–S3)
    AGENT_INITIATED_HUMAN_MERGED = "Agent-Init + Human-Merged"
    AGENT_INITIATED_AGENT_MERGED = "Agent-Init + Agent-Merged"
    AGENT_INITIATED_NOT_MERGED = "Agent-Init + Not-Merged"
    # Human-initiated (S4–S6)
    HUMAN_INITIATED_HUMAN_MERGED = "Human-Init + Human-Merged"
    HUMAN_INITIATED_AGENT_MERGED = "Human-Init + Agent-Merged"
    HUMAN_INITIATED_NOT_MERGED = "Human-Init + Not-Merged"
    # Excluded cluster (not a scenario): timeline has no committed event; excluded from taxonomy.
    EXCLUDED_NO_COMMIT_IN_TIMELINE = "Excluded: No-Commit in Timeline"


# The six scenario types used for the taxonomy; excluded cluster is reported separately.
SCENARIO_TYPES = (
    CollaborationType.AGENT_INITIATED_HUMAN_MERGED,
    CollaborationType.AGENT_INITIATED_AGENT_MERGED,
    CollaborationType.AGENT_INITIATED_NOT_MERGED,
    CollaborationType.HUMAN_INITIATED_HUMAN_MERGED,
    CollaborationType.HUMAN_INITIATED_AGENT_MERGED,
    CollaborationType.HUMAN_INITIATED_NOT_MERGED,
)


@dataclass
class WorkflowEvent:
    """Represents a single event in the PR workflow."""
    index: int
    event_type: str
    actor: str
    actor_type: Optional[str]  # "User", "Bot", ... if present in dataset
    is_agent: bool
    timestamp: Optional[str] = None
    review_state: Optional[str] = None  # for `reviewed` events, normalized uppercase
    
    @property
    def actor_label(self) -> str:
        return "Agent" if self.is_agent else "Human"


@dataclass
class WorkflowPhase:
    """Represents a phase in the workflow lifecycle."""
    name: str
    events: List[WorkflowEvent] = field(default_factory=list)
    start_index: Optional[int] = None
    end_index: Optional[int] = None  # inclusive
    
    @property
    def agent_count(self) -> int:
        return sum(1 for e in self.events if e.is_agent)
    
    @property
    def human_count(self) -> int:
        return sum(1 for e in self.events if not e.is_agent)

    @property
    def agent_weighted(self) -> float:
        return sum(get_event_weight(e) for e in self.events if e.is_agent)

    @property
    def human_weighted(self) -> float:
        return sum(get_event_weight(e) for e in self.events if not e.is_agent)
    
    @property
    def primary_actor(self) -> str:
        if not self.events:
            return "None"
        a = self.agent_weighted
        h = self.human_weighted
        if a > h:
            return "Agent"
        elif h > a:
            return "Human"
        return "Mixed"


@dataclass
class PRWorkflow:
    """Complete workflow analysis for a PR."""
    pr_id: str
    url: Optional[str]
    repo: Optional[str]
    tool: str
    events: List[WorkflowEvent] = field(default_factory=list)
    phases: Dict[str, WorkflowPhase] = field(default_factory=dict)
    ml_analysis: Optional[Dict] = None  # ML model integration
    revision_cycles: int = 0
    phase_durations: Dict[str, float] = field(default_factory=dict)  # phase name -> duration in hours
    
    @property
    def total_events(self) -> int:
        return len(self.events)
    
    @property
    def agent_total(self) -> int:
        return sum(1 for e in self.events if e.is_agent)
    
    @property
    def human_total(self) -> int:
        return sum(1 for e in self.events if not e.is_agent)

    def get_weighted_scores(self) -> Tuple[float, float]:
        """Return (agent_weighted, human_weighted) for the whole PR."""
        a = sum(get_event_weight(e) for e in self.events if e.is_agent)
        h = sum(get_event_weight(e) for e in self.events if not e.is_agent)
        return a, h
    
    @property
    def collaboration_score(self) -> float:
        """
        Weighted collaboration score.
        Score near 1.0 = balanced; near 0.0 = one-sided.
        """
        a, h = self.get_weighted_scores()
        if a == 0 and h == 0:
            return 0.0
        return min(a, h) / max(a, h)
    
    @property
    def first_event_type(self) -> Optional[str]:
        """Event type of the first event in the timeline, or None if empty. Used for nuance when timeline has no committed event (excluded cluster)."""
        return self.events[0].event_type if self.events else None

    @property
    def last_event_type(self) -> Optional[str]:
        """Event type of the last event in the timeline, or None if empty. Used for nuance when resolver is No resolver (incomplete_timeline)."""
        return self.events[-1].event_type if self.events else None

    @property
    def initiator(self) -> str:
        """
        Who initiated the PR: the actor of the first commit (first "committed" event).
        When the timeline has no "committed" event, initiator is not defined; we return "No commit"
        so the collaboration_type becomes EXCLUDED_NO_COMMIT_IN_TIMELINE (excluded cluster). Use first_event_type
        for nuance (e.g. first event = assigned, closed, labeled). See config/methodology_20.md.
        """
        for e in self.events:
            if e.event_type == "committed":
                return e.actor_label
        return "No commit"  # timeline has no committed event; initiator undefined

    @property
    def resolver_origin(self) -> str:
        """
        How the PR was resolved: "merged" | "closed" | "incomplete_timeline".
        S3/S6 = unmerged & closed only. If the PR has any merged event, it counts as merged (S1/S2),
        regardless of event order (e.g. merged then closed). "closed" = closed without merge.
        "incomplete_timeline" = no merged/closed event in the timeline.
        """
        has_merged = any(e.event_type == 'merged' for e in self.events)
        has_closed = any(e.event_type == 'closed' for e in self.events)
        if has_merged:
            return "merged"
        if has_closed:
            return "closed"
        return "incomplete_timeline"

    @property
    def resolver(self) -> str:
        """Who resolved the PR (merged). Human or Agent when the PR was merged; "No resolver" when closed or incomplete_timeline."""
        if self.resolver_origin != "merged":
            return "No resolver"
        # Last merged event (chronologically) determines who merged
        for e in reversed(self.events):
            if e.event_type == 'merged':
                return e.actor_label
        return "No resolver"

    @property
    def closer(self) -> str:
        """Who closed the PR (unmerged). Human or Agent when the PR was closed without merge; "No closer" when merged or incomplete_timeline."""
        if self.resolver_origin != "closed":
            return "No closer"
        for e in reversed(self.events):
            if e.event_type == 'closed':
                return e.actor_label
        return "No closer"

    @property
    def terminator(self) -> str:
        """
        Who performed the last event in the timeline (the actor who "ended" the observed activity).
        When merged, terminator equals resolver; when closed, terminator equals closer; when incomplete_timeline,
        terminator is the actor of the last event. Returns "Unknown" only when there are no events.
        See manuscript/methodology.md §3.3.4.
        """
        if not self.events:
            return "Unknown"
        return self.events[-1].actor_label

    def get_revision_cycles(self) -> int:
        return self.revision_cycles
    
    @property
    def collaboration_type(self) -> CollaborationType:
        """
        Classify by initiator × merge outcome (Option C: merge-focused). Merged PRs split by resolver (Human/Agent);
        non-merged (closed or incomplete timeline) collapsed to Not-Merged. Each PR gets exactly one scenario (S1–S6).
        Use verify_scenario_mutual_exclusivity() to assert counts sum.
        """
        initiator = self.initiator
        if initiator == "Agent":
            if self.resolver_origin == "merged":
                return CollaborationType.AGENT_INITIATED_HUMAN_MERGED if self.resolver == "Human" else CollaborationType.AGENT_INITIATED_AGENT_MERGED
            return CollaborationType.AGENT_INITIATED_NOT_MERGED  # closed or incomplete_timeline
        if initiator == "Human":
            if self.resolver_origin == "merged":
                return CollaborationType.HUMAN_INITIATED_HUMAN_MERGED if self.resolver == "Human" else CollaborationType.HUMAN_INITIATED_AGENT_MERGED
            return CollaborationType.HUMAN_INITIATED_NOT_MERGED  # closed or incomplete_timeline
        return CollaborationType.EXCLUDED_NO_COMMIT_IN_TIMELINE  # initiator == "No commit" (excluded cluster)
    
    @property
    def ml_predicted_tool(self) -> Optional[str]:
        """Get ML-predicted tool if ML analysis is available."""
        return self.ml_analysis.get("predicted_tool") if self.ml_analysis else None
    
    @property
    def ml_validation_match(self) -> Optional[bool]:
        """Check if ML prediction matches actual tool."""
        return self.ml_analysis.get("tool_match") if self.ml_analysis else None

    # ========== OUTCOME MEASURES ==========

    @property
    def is_merged(self) -> bool:
        """True if PR was merged (vs closed without merge)."""
        return any(e.event_type == 'merged' for e in self.events)

    @property
    def is_closed(self) -> bool:
        """True if PR has a terminal event (merged or closed)."""
        return any(e.event_type in ('merged', 'closed') for e in self.events)

    @property
    def changes_requested_count(self) -> int:
        """Number of CHANGES_REQUESTED reviews."""
        return sum(1 for e in self.events 
                   if e.event_type == 'reviewed' and e.review_state == 'CHANGES_REQUESTED')

    @property
    def commit_count(self) -> int:
        """Number of commits in the PR."""
        return sum(1 for e in self.events if e.event_type == 'committed')

    @property
    def review_count(self) -> int:
        """Total number of review events."""
        return sum(1 for e in self.events if e.event_type == 'reviewed')

    @property
    def duration_hours(self) -> Optional[float]:
        """
        PR duration in hours (first to last timestamp).
        Returns None if fewer than 2 timestamps available.
        """
        from datetime import datetime
        timestamps = []
        for e in self.events:
            if e.timestamp:
                try:
                    # Handle ISO format with timezone
                    ts = e.timestamp.replace('Z', '+00:00')
                    if '+' not in ts and '-' not in ts[10:]:
                        ts = ts + '+00:00'
                    dt = datetime.fromisoformat(ts)
                    timestamps.append(dt)
                except (ValueError, TypeError):
                    continue
        if len(timestamps) < 2:
            return None
        duration = max(timestamps) - min(timestamps)
        return duration.total_seconds() / 3600.0


def is_bot(actor: Optional[dict]) -> bool:
    """
    Heuristic bot detector (fallback).

    Prefer using actor `type` metadata (Bot/User) when available. This function
    remains as a conservative substring-based fallback.
    """
    if not actor or not isinstance(actor, dict):
        return False
    login = str(actor.get('login', actor.get('name', ''))).lower()
    return any(p in login for p in BOT_PATTERNS)


def _extract_actor_dict(event: dict) -> Optional[dict]:
    return (event.get('actor') or event.get('author') or event.get('user') or event.get('committer'))


def get_actor_name(event: dict) -> str:
    """Extract actor login/name from event."""
    actor = _extract_actor_dict(event)
    if actor and isinstance(actor, dict):
        return actor.get('login', actor.get('name', 'unknown'))
    return 'unknown'


def get_actor_type(event: dict) -> Optional[str]:
    """Extract actor type (e.g., 'User', 'Bot') if present in dataset."""
    actor = _extract_actor_dict(event)
    if actor and isinstance(actor, dict):
        v = actor.get("type")
        return v if isinstance(v, str) else None
    return None


def is_agent_event(event: dict) -> bool:
    """
    Determine whether the event actor is an Agent.

    Grounded logic:
    - If dataset provides `actor.type == 'Bot'`, treat as Agent.
    - Otherwise fallback to substring-based bot patterns.
    """
    actor = _extract_actor_dict(event)
    actor_type = actor.get("type") if isinstance(actor, dict) else None
    if actor_type == "Bot":
        return True
    return is_bot(actor)


def _extract_timestamp(event: dict) -> Optional[str]:
    # Observed timestamp fields in this workspace include: created_at, submitted_at, committer.date
    v = event.get("created_at")
    if isinstance(v, str):
        return v
    v = event.get("submitted_at")
    if isinstance(v, str):
        return v
    committer = event.get("committer")
    if isinstance(committer, dict):
        d = committer.get("date")
        if isinstance(d, str):
            return d
    return None


def _extract_review_state(event: dict) -> Optional[str]:
    if event.get("event") != "reviewed":
        return None
    s = event.get("state")
    if isinstance(s, str):
        return s.strip().upper()
    return None


def get_event_weight(ev: WorkflowEvent) -> float:
    """Get weight for a WorkflowEvent."""
    if ev.event_type == "reviewed":
        state = (ev.review_state or "").upper()
        m = EVENT_WEIGHTS.get("reviewed", {})
        if isinstance(m, dict) and state in m:
            return float(m[state])
        # Default reviewed weight if state is missing/unexpected
        return float(m.get("COMMENTED", 1.0)) if isinstance(m, dict) else 1.0
    w = EVENT_WEIGHTS.get(ev.event_type)
    if isinstance(w, (int, float)):
        return float(w)
    return float(EVENT_WEIGHTS["default"])


def get_pr_url(events: List[dict]) -> Optional[str]:
    """Extract GitHub PR URL from events."""
    # Preferred: `html_url` fields already in GitHub UI format.
    for e in events:
        if isinstance(e, dict):
            url = e.get("html_url", "")
            if isinstance(url, str) and "/pull/" in url:
                parts = url.split("/pull/")
                if len(parts) >= 2:
                    pr_num = parts[1].split("#")[0].split("/")[0]
                    return parts[0] + "/pull/" + pr_num

    # Fallback: scan arbitrary string fields for a PR URL, or convert API URLs.
    # This is intentionally conservative and only returns URLs that can be normalized
    # into `https://github.com/{owner}/{repo}/pull/{number}`.
    gh_pr_pat = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
    api_pr_pat = re.compile(r"https://api\.github\.com/repos/([^/\s]+)/([^/\s]+)/pulls/(\d+)")

    def _walk(x: object) -> Optional[str]:
        if isinstance(x, dict):
            for v in x.values():
                out = _walk(v)
                if out:
                    return out
            return None
        if isinstance(x, list):
            for v in x:
                out = _walk(v)
                if out:
                    return out
            return None
        if isinstance(x, str):
            m = gh_pr_pat.search(x)
            if m:
                return m.group(0)
            m = api_pr_pat.search(x)
            if m:
                owner, repo, num = m.group(1), m.group(2), m.group(3)
                return f"https://github.com/{owner}/{repo}/pull/{num}"
        return None

    for e in events:
        if isinstance(e, dict):
            found = _walk(e)
            if found:
                return found

    return None


def get_repo_name(events: List[dict]) -> Optional[str]:
    """Extract repository name from events."""
    # Preferred: parse from `html_url` when present.
    for e in events:
        if isinstance(e, dict):
            url = e.get("html_url", "")
            if isinstance(url, str) and "github.com/" in url:
                tail = url.split("github.com/")[1]
                parts = tail.split("/")
                if len(parts) >= 2:
                    return parts[0] + "/" + parts[1]

    # Fallback: derive repo from the best-effort PR URL extraction.
    pr_url = get_pr_url(events)
    if pr_url and "github.com/" in pr_url:
        tail = pr_url.split("github.com/")[1]
        parts = tail.split("/")
        if len(parts) >= 2:
            return parts[0] + "/" + parts[1]

    return None


def assign_phases_temporal(events: List[WorkflowEvent]) -> Tuple[Dict[str, WorkflowPhase], int, Dict[str, float]]:
    """
    Assign events to workflow phases using the 4-phase temporal model:
    PR_CREATED → REVIEW ⇄ REVISION → RESOLUTION (terminal: Merged & Closed | Unmerged & Closed).

    The transition logic is grounded in `notebooks/DATA_PIPELINE.md` and
    `manuscript/methodology.md`.

    Refinement:
    - PR_CREATED → REVIEW on first review_requested or reviewed after at least one commit.
    - Returns phase durations in hours.
    """
    from datetime import datetime
    
    phases = {p.value: WorkflowPhase(name=p.value) for p in WorkflowPhaseName}
    phase_durations = {}

    state = WorkflowPhaseName.PR_CREATED
    revision_cycles = 0
    saw_changes_requested = False
    saw_commit_after_changes = False

    first_commit_seen = False
    
    # Store the timestamp of when each phase started
    phase_starts: Dict[str, datetime] = {}
    
    def get_dt(ev: WorkflowEvent) -> Optional[datetime]:
        if not ev.timestamp:
            return None
        try:
            ts = ev.timestamp.replace('Z', '+00:00')
            if '+' not in ts and '-' not in ts[10:]:
                ts = ts + '+00:00'
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    if events:
        dt0 = get_dt(events[0])
        if dt0:
            phase_starts[state.value] = dt0

    for e in events:
        prev_state = state
        
        # Terminal transition
        if e.event_type in ("merged", "closed"):
            state = WorkflowPhaseName.RESOLUTION

        # State transitions (non-terminal)
        elif state == WorkflowPhaseName.PR_CREATED:
            if e.event_type == "committed":
                first_commit_seen = True
            if first_commit_seen and (e.event_type == "review_requested" or e.event_type == "reviewed"):
                # First review event: if CHANGES_REQUESTED, go directly to Revision; else Review
                if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                    saw_changes_requested = True
                    saw_commit_after_changes = False
                    state = WorkflowPhaseName.REVISION
                else:
                    state = WorkflowPhaseName.REVIEW
        elif state == WorkflowPhaseName.REVIEW:
            if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                saw_changes_requested = True
                saw_commit_after_changes = False
                state = WorkflowPhaseName.REVISION
            elif e.event_type == "reviewed" and e.review_state == "APPROVED":
                pass
        elif state == WorkflowPhaseName.REVISION:
            if e.event_type == "committed":
                saw_commit_after_changes = True
            if e.event_type == "review_requested" or e.event_type == "reviewed":
                if saw_changes_requested and saw_commit_after_changes:
                    # Only increment cycles if we actually saw a request AFTER commits
                    if e.event_type == "review_requested":
                        revision_cycles += 1
                saw_changes_requested = False
                saw_commit_after_changes = False
                state = WorkflowPhaseName.REVIEW

        # Handle phase duration calculation
        if state != prev_state:
            now_dt = get_dt(e)
            if now_dt and prev_state.value in phase_starts:
                start_dt = phase_starts[prev_state.value]
                duration_h = (now_dt - start_dt).total_seconds() / 3600.0
                # Accumulate duration (relevant for iterative REVIEW ⇄ REVISION)
                phase_durations[prev_state.value] = phase_durations.get(prev_state.value, 0.0) + duration_h
                phase_starts[state.value] = now_dt

        # Append to current state phase
        phases[state.value].events.append(e)

    # Fill start/end indices
    for p in phases.values():
        if p.events:
            p.start_index = p.events[0].index
            p.end_index = p.events[-1].index

    return phases, revision_cycles, phase_durations


def get_phase_transition_sequence(events: List[WorkflowEvent]) -> List[Tuple[str, str]]:
    """
    Return the ordered sequence of (from_phase, to_phase) transitions for this
    workflow using the same state machine as assign_phases_temporal. Used to
    compute transition counts and probabilities per tool family.

    Terminal transitions distinguish outcome: "merged_and_closed" vs
    "unmerged_and_closed".
    """
    transitions: List[Tuple[str, str]] = []
    state = WorkflowPhaseName.PR_CREATED
    first_commit_seen = False

    for e in events:
        prev = state
        to_state_value: Optional[str] = None
        
        # Terminal transition
        if e.event_type == "merged":
            to_state_value = "merged_and_closed"
        elif e.event_type == "closed":
            to_state_value = "unmerged_and_closed"
        
        if to_state_value is not None:
            state = WorkflowPhaseName.RESOLUTION
        elif state == WorkflowPhaseName.PR_CREATED:
            if e.event_type == "committed":
                first_commit_seen = True
            if first_commit_seen and (e.event_type == "review_requested" or e.event_type == "reviewed"):
                # First review event: if CHANGES_REQUESTED, go directly to Revision; else Review
                if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                    state = WorkflowPhaseName.REVISION
                else:
                    state = WorkflowPhaseName.REVIEW
        elif state == WorkflowPhaseName.REVIEW:
            if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                state = WorkflowPhaseName.REVISION
        elif state == WorkflowPhaseName.REVISION:
            if e.event_type == "review_requested" or e.event_type == "reviewed":
                state = WorkflowPhaseName.REVIEW

        if to_state_value is not None:
            transitions.append((prev.value, to_state_value))
        elif state != prev:
            transitions.append((prev.value, state.value))

    return transitions


def get_phase_transition_sequence_with_durations(
    events: List[WorkflowEvent]
) -> List[Tuple[str, str, Optional[float]]]:
    """
    Return the ordered sequence of (from_phase, to_phase, duration_days) for
    this workflow. duration_days is the time from entering the from-phase until
    the transition (event that triggered the move). None if timestamp missing.
    """
    from datetime import datetime

    result: List[Tuple[str, str, Optional[float]]] = []
    state = WorkflowPhaseName.PR_CREATED
    first_commit_seen = False
    phase_start_dt: Optional[datetime] = None  # when we entered current state

    def parse_ts(ts: Optional[str]):
        if not ts:
            return None
        try:
            s = (ts or "").replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    for e in events:
        event_dt = parse_ts(e.timestamp)
        if phase_start_dt is None and event_dt is not None:
            phase_start_dt = event_dt  # first event defines start of PR created
        prev = state
        to_state_value: Optional[str] = None
        
        # Terminal transition
        if e.event_type == "merged":
            to_state_value = "merged_and_closed"
        elif e.event_type == "closed":
            to_state_value = "unmerged_and_closed"
        
        if to_state_value is not None:
            state = WorkflowPhaseName.RESOLUTION
        elif state == WorkflowPhaseName.PR_CREATED:
            if e.event_type == "committed":
                first_commit_seen = True
            if first_commit_seen and (e.event_type == "review_requested" or e.event_type == "reviewed"):
                # First review event: if CHANGES_REQUESTED, go directly to Revision; else Review
                if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                    state = WorkflowPhaseName.REVISION
                else:
                    state = WorkflowPhaseName.REVIEW
        elif state == WorkflowPhaseName.REVIEW:
            if e.event_type == "reviewed" and e.review_state == "CHANGES_REQUESTED":
                state = WorkflowPhaseName.REVISION
        elif state == WorkflowPhaseName.REVISION:
            if e.event_type == "review_requested" or e.event_type == "reviewed":
                state = WorkflowPhaseName.REVIEW

        # Record transition with duration from phase start to this event
        duration_days: Optional[float] = None
        if phase_start_dt is not None and event_dt is not None:
            delta = (event_dt - phase_start_dt).total_seconds()
            duration_days = delta / (24.0 * 3600.0)

        if to_state_value is not None:
            result.append((prev.value, to_state_value, duration_days))
        elif state != prev:
            result.append((prev.value, state.value, duration_days))

        # Update phase start: when we enter a new phase, start is this event
        if state != prev or to_state_value is not None:
            phase_start_dt = event_dt

    return result


# =====================================================================
# RQ3: End-to-end workflow path classification (T1–T6b)
# =====================================================================

class WorkflowPath:
    """
    Eight canonical end-to-end workflow paths through the state machine.
    Merged paths (T1, T3, T5a, T5b) are compatible with S1/S2/S4/S5.
    Unmerged paths (T2, T4, T6a, T6b) are compatible with S3/S6.
    T5/T6 are decomposed by revision cycle count (a=1, b=2+).
    """
    T1 = "T1: Create→Review→Merge"          # Reviewed, no revision, merged
    T2 = "T2: Create→Review→Close"          # Reviewed, no revision, unmerged
    T3 = "T3: Create→Merge"                 # Direct resolution (no review)
    T4 = "T4: Create→Close"                 # Abandoned without review
    T5a = "T5a: Create→Review→Revise(1)→Merge"   # 1 revision cycle, merged
    T5b = "T5b: Create→Review→Revise(2+)→Merge"  # 2+ revision cycles, merged
    T6a = "T6a: Create→Review→Revise(1)→Close"   # 1 revision cycle, unmerged
    T6b = "T6b: Create→Review→Revise(2+)→Close"  # 2+ revision cycles, unmerged
    UNKNOWN = "Unknown"                       # Edge case: no terminal event


# All path labels in display order
WORKFLOW_PATHS_MERGED = (WorkflowPath.T1, WorkflowPath.T3, WorkflowPath.T5a, WorkflowPath.T5b)
WORKFLOW_PATHS_UNMERGED = (WorkflowPath.T2, WorkflowPath.T4, WorkflowPath.T6a, WorkflowPath.T6b)
WORKFLOW_PATHS_ALL = WORKFLOW_PATHS_MERGED + WORKFLOW_PATHS_UNMERGED


def get_revision_cycle_count(transitions: List[Tuple[str, str]]) -> int:
    """
    Count the number of Review→Revision transitions in a transition sequence.
    Each Review→Revision transition represents one revision cycle.
    """
    count = 0
    for from_phase, to_phase in transitions:
        if from_phase == "review" and to_phase == "revision":
            count += 1
    return count


def classify_workflow_path(transitions: List[Tuple[str, str]]) -> str:
    """
    Classify a PR's transition sequence into one of eight canonical paths (T1–T6b).

    Logic:
    1. Determine terminal state: merged_and_closed vs unmerged_and_closed
    2. Check if review phase was entered (any transition with 'review' as target)
    3. Check if revision phase was entered + count cycles
    4. Map to the appropriate path

    Args:
        transitions: Output of get_phase_transition_sequence()

    Returns:
        One of the WorkflowPath string constants.
    """
    if not transitions:
        return WorkflowPath.UNKNOWN

    # Determine terminal state: scan for the FIRST terminal transition.
    # GitHub PRs often have both "merged" and "closed" events (auto-close after merge),
    # so get_phase_transition_sequence() may record two terminal transitions.
    # The first one is the authoritative outcome.
    terminal_states = {"merged_and_closed", "unmerged_and_closed"}
    is_merged = False
    is_unmerged = False
    for _, to in transitions:
        if to in terminal_states:
            is_merged = (to == "merged_and_closed")
            is_unmerged = (to == "unmerged_and_closed")
            break

    if not is_merged and not is_unmerged:
        return WorkflowPath.UNKNOWN

    # Check if review was entered (as a target of any transition)
    entered_review = any(to == "review" for _, to in transitions)

    # Check if revision was entered and count cycles
    entered_revision = any(to == "revision" for _, to in transitions)
    revision_cycles = get_revision_cycle_count(transitions)

    # Also count direct PR_created → revision transitions (first review was CHANGES_REQUESTED)
    direct_to_revision = any(
        from_p == "pr_created" and to == "revision"
        for from_p, to in transitions
    )
    if direct_to_revision:
        entered_revision = True
        # A direct pr_created→revision counts as entering revision without prior review,
        # but the PR_created→Revision→Review cycle still counts

    if is_merged:
        if entered_revision:
            # Count total revision entries (from review or directly from pr_created)
            total_revision_entries = sum(
                1 for _, to in transitions if to == "revision"
            )
            if total_revision_entries >= 2:
                return WorkflowPath.T5b
            else:
                return WorkflowPath.T5a
        elif entered_review:
            return WorkflowPath.T1
        else:
            return WorkflowPath.T3
    else:  # unmerged
        if entered_revision:
            total_revision_entries = sum(
                1 for _, to in transitions if to == "revision"
            )
            if total_revision_entries >= 2:
                return WorkflowPath.T6b
            else:
                return WorkflowPath.T6a
        elif entered_review:
            return WorkflowPath.T2
        else:
            return WorkflowPath.T4


def analyze_workflow(
    pr_id: str, 
    events: List[dict], 
    tool: str,
    ml_analyzer: Optional[object] = None
) -> PRWorkflow:
    """
    Analyze a complete PR workflow.
    
    Args:
        pr_id: PR identifier
        events: List of timeline events
        tool: Tool name (Claude, Copilot, Cursor, Devin, OpenAI)
        ml_analyzer: Optional MLWorkflowAnalyzer instance for ML integration
    """
    workflow = PRWorkflow(
        pr_id=pr_id,
        url=get_pr_url(events),
        repo=get_repo_name(events),
        tool=tool
    )
    
    # Process events into normalized WorkflowEvent list
    for i, event in enumerate(events):
        if not isinstance(event, dict) or 'event' not in event:
            continue
        
        event_type = event.get('event', '')
        actor_name = get_actor_name(event)
        actor_type = get_actor_type(event)
        actor_is_agent = is_agent_event(event)
        timestamp = _extract_timestamp(event)
        review_state = _extract_review_state(event)
        
        wf_event = WorkflowEvent(
            index=i,
            event_type=event_type,
            actor=actor_name,
            actor_type=actor_type,
            is_agent=actor_is_agent,
            timestamp=timestamp,
            review_state=review_state,
        )
        
        workflow.events.append(wf_event)

    # Assign phases + revision cycles using temporal model
    workflow.phases, workflow.revision_cycles, workflow.phase_durations = assign_phases_temporal(workflow.events)
    
    # Integrate ML analysis if analyzer is provided
    if ml_analyzer is not None:
        try:
            from src.analysis.ml_integration import integrate_ml_analysis
            workflow.ml_analysis = integrate_ml_analysis(workflow, ml_analyzer)
        except Exception:
            # Silently fail if ML analysis is unavailable (e.g., model not found)
            workflow.ml_analysis = None
    
    return workflow


def load_and_analyze_tool(
    tool: str, 
    max_prs: Optional[int] = None,
    ml_analyzer: Optional[object] = None
) -> List[PRWorkflow]:
    """
    Load and analyze all PRs for a tool.
    
    Args:
        tool: Tool name
        max_prs: Maximum number of PRs to analyze (None = all)
        ml_analyzer: Optional MLWorkflowAnalyzer instance for ML integration
    """
    filepath = DATASET_DIR / FILES[tool]
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    workflows = []
    for i, (pr_id, events) in enumerate(data.items()):
        if max_prs and i >= max_prs:
            break
        workflows.append(analyze_workflow(pr_id, events, tool, ml_analyzer))
    
    return workflows


def verify_scenario_mutual_exclusivity(
    workflows: List[PRWorkflow],
    *,
    raise_on_fail: bool = True,
) -> Dict:
    """
    Verify that scenario (collaboration-type) assignment has no overcounts.

    Each PR is assigned exactly one CollaborationType by the if/elif chain in
    collaboration_type. This function asserts that when we count by type
    (and by tool), the sum equals the number of workflows - i.e. no PR is
    counted more than once and none are missing.

    Returns:
        dict with keys: passed (bool), total (int), sum_by_type (int),
        counts_by_type (dict), per_tool (dict with total and sum_by_type per tool).
    Raises:
        AssertionError: If sum of type counts != len(workflows) and raise_on_fail.
    """
    total = len(workflows)
    counts_by_type: Dict[CollaborationType, int] = defaultdict(int)
    per_tool: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "counts_by_type": defaultdict(int)})

    for w in workflows:
        ct = w.collaboration_type
        counts_by_type[ct] += 1
        per_tool[w.tool]["total"] += 1
        per_tool[w.tool]["counts_by_type"][ct] += 1

    sum_by_type = sum(counts_by_type.values())
    passed = sum_by_type == total

    # Per-tool: each tool's type counts must sum to that tool's workflow count
    for tool, data in per_tool.items():
        tool_sum = sum(data["counts_by_type"].values())
        if tool_sum != data["total"]:
            passed = False
            break

    if raise_on_fail:
        assert sum_by_type == total, (
            f"Scenario mutual exclusivity violated: sum of type counts ({sum_by_type}) != "
            f"number of workflows ({total}). Overcount or undercount detected."
        )
        for tool, data in per_tool.items():
            tool_sum = sum(data["counts_by_type"].values())
            assert tool_sum == data["total"], (
                f"Tool {tool}: sum of type counts ({tool_sum}) != workflow count ({data['total']})"
            )

    return {
        "passed": passed,
        "total": total,
        "sum_by_type": sum_by_type,
        "counts_by_type": dict(counts_by_type),
        "per_tool": {
            k: {
                "total": v["total"],
                "sum_by_type": sum(v["counts_by_type"].values()),
            }
            for k, v in per_tool.items()
        },
    }


def generate_workflow_summary(workflow: PRWorkflow) -> str:
    """Generate a human-readable workflow summary."""
    lines = []
    lines.append(f"## {workflow.repo or workflow.pr_id}")
    if workflow.url:
        lines.append(f"**URL**: {workflow.url}")
    lines.append(f"**Tool**: {workflow.tool}")
    lines.append(f"**Collaboration Type**: {workflow.collaboration_type.value}")
    lines.append("")
    
    lines.append("### Workflow Summary")
    lines.append(f"- **Total Events**: {workflow.total_events}")
    lines.append(f"- **Agent Events**: {workflow.agent_total} ({100*workflow.agent_total/workflow.total_events:.1f}%)")
    lines.append(f"- **Human Events**: {workflow.human_total} ({100*workflow.human_total/workflow.total_events:.1f}%)")
    a_w, h_w = workflow.get_weighted_scores()
    lines.append(f"- **Weighted Collaboration Score**: {workflow.collaboration_score:.2f} (agent={a_w:.2f}, human={h_w:.2f})")
    lines.append(f"- **Revision Cycles**: {workflow.revision_cycles}")
    lines.append("")
    
    lines.append("### Phase Breakdown")
    lines.append("| Phase | Events | Agent | Human | Agent (w) | Human (w) | Primary |")
    lines.append("|-------|--------|-------|-------|-----------|-----------|---------|")
    for phase_name in [p.value for p in WorkflowPhaseName]:
        phase = workflow.phases.get(phase_name)
        if phase and phase.events:
            lines.append(
                f"| {phase_name.title()} | {len(phase.events)} | {phase.agent_count} | {phase.human_count} | "
                f"{phase.agent_weighted:.2f} | {phase.human_weighted:.2f} | {phase.primary_actor} |"
            )
    lines.append("")
    
    lines.append("### Event Timeline")
    for e in workflow.events:
        lines.append(f"- [{e.actor_label}] {e.event_type} by {e.actor}")
    
    return "\n".join(lines)


def find_exemplar_prs(collaboration_type: CollaborationType, 
                      tools: List[str] = None,
                      max_per_tool: int = 3) -> Dict[str, List[PRWorkflow]]:
    """Find PRs matching a specific collaboration type."""
    if tools is None:
        tools = list(FILES.keys())
    
    results = {}
    for tool in tools:
        workflows = load_and_analyze_tool(tool)
        matching = [w for w in workflows if w.collaboration_type == collaboration_type]
        # Prefer PRs with URLs
        matching.sort(key=lambda w: (w.url is not None, w.collaboration_score), reverse=True)
        results[tool] = matching[:max_per_tool]
    
    return results


def print_tool_summary(tool: str, max_prs: int = 100):
    """Print collaboration summary for a tool."""
    workflows = load_and_analyze_tool(tool, max_prs)
    
    print(f"\n{'='*60}")
    print(f"{tool} Collaboration Analysis ({len(workflows)} PRs)")
    print('='*60)
    
    # Count collaboration types
    type_counts = defaultdict(int)
    for w in workflows:
        type_counts[w.collaboration_type] += 1
    
    print("\nCollaboration Type Distribution:")
    for ct in CollaborationType:
        count = type_counts[ct]
        pct = 100 * count / len(workflows) if workflows else 0
        print(f"  {ct.value}: {count} ({pct:.1f}%)")
    
    # Show exemplars
    print("\nExemplars (Agent-Initiated + Human-Resolved):")
    exemplars = [w for w in workflows 
                 if w.collaboration_type == CollaborationType.AGENT_INITIATED_HUMAN_MERGED 
                 and w.url][:3]
    for w in exemplars:
        print(f"  - {w.url}")
        print(f"    Agent: {w.agent_total}, Human: {w.human_total}, Score: {w.collaboration_score:.2f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Workflow-centric collaboration analysis')
    parser.add_argument('--tool', type=str, help='Analyze specific tool')
    parser.add_argument('--exemplar', type=str, help='Generate exemplar report for PR URL pattern')
    parser.add_argument('--all', action='store_true', help='Analyze all tools')
    args = parser.parse_args()
    
    if args.all:
        for tool in FILES.keys():
            print_tool_summary(tool, max_prs=100)
    elif args.tool:
        print_tool_summary(args.tool)
    else:
        # Default: show summary for Devin (has LangBot exemplar)
        print_tool_summary('Devin', max_prs=50)

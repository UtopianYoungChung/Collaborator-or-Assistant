"""
Network Extraction for Groundtruth Analysis

Extracts network structures (nodes and edges) from PR workflows for:
1. Groundtruth validation
2. Network analysis
3. Pattern discovery

This module provides functions to extract various network representations
from the processed PRWorkflow objects.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime

from src.analysis.workflows import (
    PRWorkflow,
    WorkflowEvent,
    CollaborationType,
    load_and_analyze_tool,
    FILES,
    get_phase_transition_sequence,
    get_phase_transition_sequence_with_durations,
    classify_workflow_path,
    WorkflowPath,
    WORKFLOW_PATHS_ALL,
    WORKFLOW_PATHS_MERGED,
    WORKFLOW_PATHS_UNMERGED,
)

# Display labels aligned with state machine terminology (PR created, Review, Revision, Merged and closed, Unmerged and closed)
PATH_DISPLAY_LABELS = {
    WorkflowPath.T1: "PR created → Review → Merged and closed",
    WorkflowPath.T2: "PR created → Review → Unmerged and closed",
    WorkflowPath.T3: "PR created → Merged and closed",
    WorkflowPath.T4: "PR created → Unmerged and closed",
    WorkflowPath.T5a: "PR created → Review ⇄ Revision (1) → Merged and closed",
    WorkflowPath.T5b: "PR created → Review ⇄ Revision (2+) → Merged and closed",
    WorkflowPath.T6a: "PR created → Review ⇄ Revision (1) → Unmerged and closed",
    WorkflowPath.T6b: "PR created → Review ⇄ Revision (2+) → Unmerged and closed",
    WorkflowPath.UNKNOWN: "Unknown",
}


@dataclass
class NetworkNode:
    """Represents a node in a network."""
    node_id: str
    node_type: str
    attributes: Dict


@dataclass
class NetworkEdge:
    """Represents an edge in a network."""
    source: str
    target: str
    weight: float
    attributes: Dict


def extract_actor_network(workflows: List[PRWorkflow]) -> Tuple[Dict[str, NetworkNode], List[NetworkEdge]]:
    """
    Extract actor collaboration network from workflows.
    
    Nodes: Individual actors (humans and Agent actors)
    Edges: Co-participation in PRs (weighted by number of shared PRs)
    
    Returns:
        Tuple of (nodes_dict, edges_list)
    """
    nodes: Dict[str, NetworkNode] = {}
    edges_data: Dict[Tuple[str, str], Dict] = defaultdict(lambda: {
        "pr_ids": [],
        "collaboration_types": [],
        "tools": [],
        "collaboration_scores": []
    })
    
    for workflow in workflows:
        # Collect all actors in this PR
        actors_in_pr: Set[str] = set()
        actor_types: Dict[str, str] = {}
        
        for event in workflow.events:
            actor_id = event.actor
            actor_type = "Agent" if event.is_agent else "Human"
            
            actors_in_pr.add(actor_id)
            actor_types[actor_id] = actor_type
            
            # Update or create node
            if actor_id not in nodes:
                nodes[actor_id] = NetworkNode(
                    node_id=actor_id,
                    node_type=actor_type,
                    attributes={
                        "pr_count": 0,
                        "tool_distribution": defaultdict(int),
                        "collaboration_scores": [],
                        "event_count": 0
                    }
                )
            
            # Update node attributes
            nodes[actor_id].attributes["pr_count"] += 1
            nodes[actor_id].attributes["tool_distribution"][workflow.tool] += 1
            nodes[actor_id].attributes["collaboration_scores"].append(
                workflow.collaboration_score
            )
            nodes[actor_id].attributes["event_count"] += 1
        
        # Create edges (co-participation in PR)
        actors_list = list(actors_in_pr)
        for i, actor1 in enumerate(actors_list):
            for actor2 in actors_list[i+1:]:
                # Sort to ensure consistent edge direction
                edge_key = tuple(sorted([actor1, actor2]))
                
                edges_data[edge_key]["pr_ids"].append(workflow.pr_id)
                edges_data[edge_key]["collaboration_types"].append(
                    workflow.collaboration_type.value
                )
                edges_data[edge_key]["tools"].append(workflow.tool)
                edges_data[edge_key]["collaboration_scores"].append(
                    workflow.collaboration_score
                )
    
    # Convert edges_data to NetworkEdge objects
    edges: List[NetworkEdge] = []
    for (source, target), data in edges_data.items():
        # Calculate average collaboration score
        avg_score = (
            sum(data["collaboration_scores"]) / len(data["collaboration_scores"])
            if data["collaboration_scores"] else 0.0
        )
        
        # Count unique tools
        unique_tools = list(set(data["tools"]))
        
        edges.append(NetworkEdge(
            source=source,
            target=target,
            weight=len(data["pr_ids"]),  # Number of shared PRs
            attributes={
                "pr_ids": data["pr_ids"],
                "collaboration_types": data["collaboration_types"],
                "unique_tools": unique_tools,
                "tool_count": len(unique_tools),
                "avg_collaboration_score": avg_score
            }
        ))
    
    # Convert tool_distribution to regular dict for serialization
    for node in nodes.values():
        if isinstance(node.attributes["tool_distribution"], defaultdict):
            node.attributes["tool_distribution"] = dict(node.attributes["tool_distribution"])
    
    return nodes, edges


def extract_repository_tool_network(workflows: List[PRWorkflow]) -> Tuple[Dict[str, NetworkNode], List[NetworkEdge]]:
    """
    Extract repository-tool bipartite network.
    
    Nodes: Repositories and Tools
    Edges: Tool usage in repository (weighted by PR count)
    
    Returns:
        Tuple of (nodes_dict, edges_list)
    """
    repo_nodes: Dict[str, NetworkNode] = {}
    tool_nodes: Dict[str, NetworkNode] = {}
    edges_data: Dict[Tuple[str, str], Dict] = defaultdict(lambda: {
        "pr_ids": [],
        "collaboration_types": defaultdict(int),
        "collaboration_scores": [],
        "revision_cycles": []
    })
    
    for workflow in workflows:
        if not workflow.repo:
            continue
        
        repo_id = workflow.repo
        tool_id = workflow.tool
        
        # Update repository node
        if repo_id not in repo_nodes:
            repo_nodes[repo_id] = NetworkNode(
                node_id=repo_id,
                node_type="repository",
                attributes={
                    "pr_count": 0,
                    "tools": set(),
                    "collaboration_type_dist": defaultdict(int)
                }
            )
        repo_nodes[repo_id].attributes["pr_count"] += 1
        repo_nodes[repo_id].attributes["tools"].add(tool_id)
        repo_nodes[repo_id].attributes["collaboration_type_dist"][workflow.collaboration_type.value] += 1
        
        # Update tool node
        if tool_id not in tool_nodes:
            tool_nodes[tool_id] = NetworkNode(
                node_id=tool_id,
                node_type="tool",
                attributes={
                    "pr_count": 0,
                    "repositories": set(),
                    "collaboration_type_dist": defaultdict(int)
                }
            )
        tool_nodes[tool_id].attributes["pr_count"] += 1
        tool_nodes[tool_id].attributes["repositories"].add(repo_id)
        tool_nodes[tool_id].attributes["collaboration_type_dist"][workflow.collaboration_type.value] += 1
        
        # Update edge
        edge_key = (repo_id, tool_id)
        edges_data[edge_key]["pr_ids"].append(workflow.pr_id)
        edges_data[edge_key]["collaboration_types"][workflow.collaboration_type.value] += 1
        edges_data[edge_key]["collaboration_scores"].append(workflow.collaboration_score)
        
        # Get revision cycles if available
        try:
            revision_cycles = workflow.get_revision_cycles()
            edges_data[edge_key]["revision_cycles"].append(revision_cycles)
        except:
            pass
    
    # Combine nodes
    nodes = {**repo_nodes, **tool_nodes}
    
    # Convert sets to lists for serialization
    for node in nodes.values():
        if "tools" in node.attributes and isinstance(node.attributes["tools"], set):
            node.attributes["tools"] = list(node.attributes["tools"])
        if "repositories" in node.attributes and isinstance(node.attributes["repositories"], set):
            node.attributes["repositories"] = list(node.attributes["repositories"])
        if isinstance(node.attributes.get("collaboration_type_dist"), defaultdict):
            node.attributes["collaboration_type_dist"] = dict(node.attributes["collaboration_type_dist"])
    
    # Convert edges_data to NetworkEdge objects
    edges: List[NetworkEdge] = []
    for (repo, tool), data in edges_data.items():
        avg_score = (
            sum(data["collaboration_scores"]) / len(data["collaboration_scores"])
            if data["collaboration_scores"] else 0.0
        )
        avg_cycles = (
            sum(data["revision_cycles"]) / len(data["revision_cycles"])
            if data["revision_cycles"] else 0.0
        )
        
        edges.append(NetworkEdge(
            source=repo,
            target=tool,
            weight=len(data["pr_ids"]),  # Number of PRs
            attributes={
                "pr_ids": data["pr_ids"],
                "collaboration_type_dist": dict(data["collaboration_types"]),
                "avg_collaboration_score": avg_score,
                "avg_revision_cycles": avg_cycles
            }
        ))
    
    return nodes, edges


def extract_phase_transition_network(workflows: List[PRWorkflow]) -> Tuple[Dict[str, NetworkNode], List[NetworkEdge]]:
    """
    Extract phase transition network from workflows.
    
    Nodes: Workflow phases (PR created, Review, Revision, Resolution)
    Edges: Transitions between phases (weighted by frequency)
    
    Returns:
        Tuple of (nodes_dict, edges_list)
    """
    phase_nodes: Dict[str, NetworkNode] = {}
    edges_data: Dict[Tuple[str, str], Dict] = defaultdict(lambda: {
        "pr_ids": [],
        "time_deltas": [],
        "primary_actors": []
    })
    
    for workflow in workflows:
        # Get phase sequence (ordered by temporal occurrence)
        phase_sequence = []
        for phase_name in ['pr_created', 'review', 'revision', 'resolution']:
            phase = workflow.phases.get(phase_name)
            if phase and phase.events:
                # Get first event timestamp if available
                start_time = None
                if phase.events[0].timestamp:
                    try:
                        start_time = phase.events[0].timestamp
                    except:
                        pass
                
                phase_sequence.append({
                    "name": phase_name,
                    "primary_actor": phase.primary_actor,
                    "start_time": start_time,
                    "event_count": len(phase.events)
                })
        
        # Update nodes
        for phase_info in phase_sequence:
            phase_name = phase_info["name"]
            if phase_name not in phase_nodes:
                phase_nodes[phase_name] = NetworkNode(
                    node_id=phase_name,
                    node_type="phase",
                    attributes={
                        "pr_count": 0,
                        "agent_dominant_count": 0,
                        "human_dominant_count": 0,
                        "mixed_count": 0,
                        "total_event_count": 0
                    }
                )
            
            phase_nodes[phase_name].attributes["pr_count"] += 1
            phase_nodes[phase_name].attributes["total_event_count"] += phase_info["event_count"]
            
            primary_actor = phase_info["primary_actor"]
            if primary_actor == "Agent":
                phase_nodes[phase_name].attributes["agent_dominant_count"] += 1
            elif primary_actor == "Human":
                phase_nodes[phase_name].attributes["human_dominant_count"] += 1
            else:
                phase_nodes[phase_name].attributes["mixed_count"] += 1
        
        # Update edges (transitions)
        for i in range(len(phase_sequence) - 1):
            source = phase_sequence[i]["name"]
            target = phase_sequence[i+1]["name"]
            edge_key = (source, target)
            
            edges_data[edge_key]["pr_ids"].append(workflow.pr_id)
            edges_data[edge_key]["primary_actors"].append(phase_sequence[i]["primary_actor"])
            
            # Calculate time delta if timestamps available
            if phase_sequence[i]["start_time"] and phase_sequence[i+1]["start_time"]:
                try:
                    # Handle ISO8601 format with timezone
                    t1_str = phase_sequence[i]["start_time"].replace('Z', '+00:00')
                    t2_str = phase_sequence[i+1]["start_time"].replace('Z', '+00:00')
                    t1 = datetime.fromisoformat(t1_str)
                    t2 = datetime.fromisoformat(t2_str)
                    delta_seconds = (t2 - t1).total_seconds()
                    edges_data[edge_key]["time_deltas"].append(delta_seconds)
                except Exception:
                    pass
    
    # Convert edges_data to NetworkEdge objects
    edges: List[NetworkEdge] = []
    for (source, target), data in edges_data.items():
        # Count primary actor distribution
        primary_actor_dist = {}
        for actor in data["primary_actors"]:
            primary_actor_dist[actor] = primary_actor_dist.get(actor, 0) + 1
        
        # Calculate average time delta
        avg_time_delta = None
        if data["time_deltas"]:
            avg_time_delta = sum(data["time_deltas"]) / len(data["time_deltas"])
        
        edges.append(NetworkEdge(
            source=source,
            target=target,
            weight=len(data["pr_ids"]),  # Transition count
            attributes={
                "pr_ids": data["pr_ids"],
                "primary_actor_dist": primary_actor_dist,
                "avg_time_delta_seconds": avg_time_delta,
                "avg_time_delta_hours": avg_time_delta / 3600.0 if avg_time_delta else None
            }
        ))
    
    return phase_nodes, edges


# Display names for terminal states (merged vs unmerged)
TERMINAL_DISPLAY = {
    "resolution": "Closed",  # legacy if ever passed
    "merged_and_closed": "Merged and closed",
    "unmerged_and_closed": "Unmerged and closed",
}
PHASE_DISPLAY = {
    "pr_created": "PR created",
    "review": "Review",
    "revision": "Revision",
}

# All transitions the state machine can produce:
# - PR created -> Revision when first review is CHANGES_REQUESTED
# - Closed -> terminal: when a PR has both merged and closed events (resolution state emits to specific outcome)
CANONICAL_TRANSITIONS = frozenset({
    ("PR created", "Review"),
    ("PR created", "Revision"),
    ("PR created", "Merged and closed"),
    ("PR created", "Unmerged and closed"),
    ("Review", "Revision"),
    ("Review", "Merged and closed"),
    ("Review", "Unmerged and closed"),
    ("Revision", "Review"),
    ("Revision", "Merged and closed"),
    ("Revision", "Unmerged and closed"),
    ("Closed", "Merged and closed"),
    ("Closed", "Unmerged and closed"),
})


def phase_display_name(phase: str) -> str:
    """Map internal phase name to diagram label."""
    return TERMINAL_DISPLAY.get(phase, PHASE_DISPLAY.get(phase, phase.capitalize()))


def verify_transition_coverage(
    counts_by_tool: Dict[str, Dict[Tuple[str, str], int]],
    transition_order: List[Tuple[str, str]],
) -> Tuple[bool, List[str]]:
    """
    Verify that we cover all transitions: every observed (from, to) is in the
    canonical set, and every canonical transition is in the report order.
    Returns (ok, list of warning messages).
    """
    warnings: List[str] = []
    order_set = frozenset(transition_order)
    # Every canonical transition should be in the report order
    missing_in_order = CANONICAL_TRANSITIONS - order_set
    if missing_in_order:
        warnings.append(
            f"Canonical transitions missing from report order: {sorted(missing_in_order)}"
        )
    # Every observed transition should be canonical (or at least documented)
    observed = set()
    for tool_edges in counts_by_tool.values():
        observed.update(tool_edges.keys())
    unexpected = observed - CANONICAL_TRANSITIONS
    if unexpected:
        warnings.append(
            f"Observed transitions not in canonical set: {sorted(unexpected)}"
        )
    return (len(warnings) == 0, warnings)


def compute_phase_transition_probabilities_by_tool(
    workflows: List[PRWorkflow],
) -> Tuple[Dict[str, Dict[Tuple[str, str], int]], Dict[str, Dict[Tuple[str, str], float]]]:
    """
    Compute transition counts and P(to | from) per tool family.

    Uses the same state machine as assign_phases_temporal; terminal outcomes
    are "Merged and closed" vs "Unmerged and closed" (from event type).

    Returns:
        (counts_by_tool, probs_by_tool)
        - counts_by_tool[tool][(from_phase, to_phase)] = count
        - probs_by_tool[tool][(from_phase, to_phase)] = P(to | from) for that tool
        Phase names in keys use display form (e.g. "Closed" not "resolution").
    """
    # Count transitions per tool: (from, to) -> count
    counts_by_tool: Dict[str, Dict[Tuple[str, str], int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for w in workflows:
        tool = w.tool
        seq = get_phase_transition_sequence(w.events)
        for from_phase, to_phase in seq:
            from_d = phase_display_name(from_phase)
            to_d = phase_display_name(to_phase)
            counts_by_tool[tool][(from_d, to_d)] += 1

    # Convert to plain dict and compute P(to | from) per tool
    counts_final: Dict[str, Dict[Tuple[str, str], int]] = {}
    probs_by_tool: Dict[str, Dict[Tuple[str, str], float]] = {}

    for tool, edges in counts_by_tool.items():
        counts_final[tool] = dict(edges)
        # For each from_phase, sum counts over all to_phases
        from_totals: Dict[str, int] = defaultdict(int)
        for (f, t), c in edges.items():
            from_totals[f] += c
        probs_by_tool[tool] = {
            (f, t): count / from_totals[f] if from_totals[f] else 0.0
            for (f, t), count in edges.items()
        }

    return counts_final, probs_by_tool


def _median(values: List[float]) -> float:
    """Median of a non-empty list; caller must ensure non-empty or handle empty."""
    if not values:
        return float("nan")
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def compute_median_duration_days_by_tool(
    workflows: List[PRWorkflow],
) -> Dict[str, Dict[Tuple[str, str], float]]:
    """
    For each tool and each (from_phase, to_phase), compute median duration in days
    from entering the from-phase until the transition (event that triggered the move).
    Returns median_days_by_tool[tool][(from_d, to_d)] = median_days (NaN if no valid durations).
    """
    # Collect durations per (tool, from_d, to_d)
    durations: Dict[str, Dict[Tuple[str, str], List[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for w in workflows:
        seq = get_phase_transition_sequence_with_durations(w.events)
        for from_phase, to_phase, duration_days in seq:
            if duration_days is not None and not (duration_days != duration_days):  # not NaN
                from_d = phase_display_name(from_phase)
                to_d = phase_display_name(to_phase)
                durations[w.tool][(from_d, to_d)].append(duration_days)
    # Median per (tool, from, to)
    result: Dict[str, Dict[Tuple[str, str], float]] = {}
    for tool, edges in durations.items():
        result[tool] = {
            (f, t): _median(vals) for (f, t), vals in edges.items()
        }
    return result


# Phases (states) for median-time-per-state; terminal states get median time-to-outcome.
PHASE_ORDER_FOR_MEDIAN = [
    "PR created",
    "Review",
    "Revision",
    "Merged and closed",
    "Unmerged and closed",
]


def compute_median_hours_per_phase_per_tool(
    workflows: List[PRWorkflow],
) -> Dict[str, Dict[str, float]]:
    """
    For each tool and each phase (state), compute median time in hours.

    - Non-terminal phases (PR created, Review, Revision): median of
      time spent in that phase before transitioning out (one value per transition
      out of that phase; multiple per PR for Review/Revision), in hours.
    - Terminal phases (Merged and closed, Unmerged and closed): median of total
      PR duration in hours for PRs that ended in that outcome.

    Returns median_hours[tool][phase] = median hours (nan if no data).
    """
    # Non-terminal: pool duration in hours (duration_days * 24) for all transitions (from_phase, *)
    by_phase: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for w in workflows:
        seq = get_phase_transition_sequence_with_durations(w.events)
        for from_phase, to_phase, duration_days in seq:
            if duration_days is not None and not (duration_days != duration_days):
                from_d = phase_display_name(from_phase)
                by_phase[w.tool][from_d].append(duration_days * 24.0)
    # Terminal: total PR duration in hours for PRs ending in merged vs unmerged
    merged_durations: Dict[str, List[float]] = defaultdict(list)
    unmerged_durations: Dict[str, List[float]] = defaultdict(list)
    for w in workflows:
        seq = get_phase_transition_sequence(w.events)
        if not seq:
            continue
        _, last_to = seq[-1]
        total_hours = w.duration_hours
        if total_hours is None:
            continue
        if last_to == "merged_and_closed":
            merged_durations[w.tool].append(total_hours)
        elif last_to == "unmerged_and_closed":
            unmerged_durations[w.tool].append(total_hours)
    # Build result: median per (tool, phase) in hours
    result: Dict[str, Dict[str, float]] = {}
    for tool in set(by_phase.keys()) | set(merged_durations.keys()) | set(unmerged_durations.keys()):
        result[tool] = {}
        for phase in PHASE_ORDER_FOR_MEDIAN:
            if phase in ("Merged and closed", "Unmerged and closed"):
                vals = merged_durations[tool] if phase == "Merged and closed" else unmerged_durations[tool]
            else:
                vals = by_phase.get(tool, {}).get(phase, [])
            med = _median(vals)
            result[tool][phase] = med
    return result


def _format_phase_clarifications() -> List[str]:
    """Return Phase definitions and clarifications (PR created, review_requested, diagram style)."""
    return [
        "## Phase definitions and clarifications",
        "",
        "1. **PR created**: The **PR created** phase runs from the first event (PR creation) until the first \\(\\texttt{review\\_requested}\\) or \\(\\texttt{reviewed}\\) event after at least one \\(\\texttt{committed}\\) event. That commit may be part of the initial push that opened the PR or a later push.",
        "",
        "2. **Review requested**: \\(\\texttt{review\\_requested}\\) or \\(\\texttt{reviewed}\\) (after at least one commit) triggers the transition from PR created to Review. A PR can be reviewed without a formal “review requested” event; in this state machine we transition from PR created to Review on either event, so PRs that are reviewed without \\(\\texttt{review\\_requested}\\) still enter Review and may go from PR created directly to merged or closed if they never see review.",
        "",
        "3. **Diagram style**: Any diagram of the state machine (PR created → Review ⇄ Revision → Merged/Unmerged and closed) should use **solid arrows throughout**; do not mix solid and dashed lines.",
        "",
        "---",
        "",
    ]


def _format_method_section() -> List[str]:
    """Return the Method subsection (formula and reasons) for the report."""
    return [
        "## Method",
        "",
        "### Formula",
        "",
        "For each tool family, the **phase transition probability** from phase \\(A\\) to phase \\(B\\) is the fraction of all exits from \\(A\\) that go to \\(B\\):",
        "",
        "\\[ P(B \\mid A,\\ \\text{tool}) = \\frac{N(A \\to B)}{\\sum_{B'} N(A \\to B')} \\]",
        "",
        "where \\(N(A \\to B)\\) is the count of transitions from \\(A\\) to \\(B\\) observed for that tool across all PRs. The denominator is the total number of transitions *from* \\(A\\) (to any target) for that tool. Hence for each tool and each from-phase \\(A\\), the probabilities over targets sum to 1.",
        "",
        "### Reasons",
        "",
        "1. **Conditional probability**: \\(P(B \\mid A)\\) answers “Given the PR is in phase \\(A\\), how likely is the next transition to \\(B\\)?” This describes workflow structure (e.g. how often PR created leads to Review vs to a terminal state) without being confounded by how often \\(A\\) is reached.",
        "",
        "2. **By tool family**: Computing these probabilities separately per tool allows comparison of workflow patterns across AI coding tools (e.g. Collaborator vs Assistant paradigms).",
        "",
        "3. **Terminal outcomes**: The two terminal states **Merged and closed** and **Unmerged and closed** are distinguished by the event type that triggered the transition (\\(\\texttt{merged}\\) vs \\(\\texttt{closed}\\)). This supports outcome-oriented analysis (successful integration vs closed without merge).",
        "",
        "4. **Transition sequence**: For each PR, the ordered sequence of (from-phase, to-phase) pairs is produced by the same state machine used in phase assignment (PR created → Review ⇄ Revision; terminal events emit merged_and_closed or unmerged_and_closed). Every such transition is counted; multiple revision cycles within a PR contribute multiple Review ⇄ Revision transitions.",
        "",
        "---",
        "",
    ]


def _interpretation_per_tool(
    tool: str,
    counts: Dict[Tuple[str, str], int],
    probs: Dict[Tuple[str, str], float],
) -> List[str]:
    """Generate a short interpretation paragraph for one tool from its counts and probs."""
    p_rev_given_pr = probs.get(("PR created", "Review"), 0.0)
    p_revision_pr = probs.get(("PR created", "Revision"), 0.0)
    p_merged_pr = probs.get(("PR created", "Merged and closed"), 0.0)
    p_unmerged_pr = probs.get(("PR created", "Unmerged and closed"), 0.0)
    p_revision_review = probs.get(("Review", "Revision"), 0.0)
    p_merged_review = probs.get(("Review", "Merged and closed"), 0.0)
    p_unmerged_review = probs.get(("Review", "Unmerged and closed"), 0.0)
    p_review_revision = probs.get(("Revision", "Review"), 0.0)

    lines = [f"**{tool}**"]
    # PR created exits (Review, Revision when first review is CHANGES_REQUESTED, or terminal)
    lines.append(
        f"- From PR created: P(Review | PR created) = {p_rev_given_pr:.3f}; "
        f"P(Revision | PR created) = {p_revision_pr:.3f}; "
        f"P(Merged and closed | PR created) = {p_merged_pr:.3f}; "
        f"P(Unmerged and closed | PR created) = {p_unmerged_pr:.3f}. "
        "So PRs that leave PR created enter Review, enter Revision (when the first review is CHANGES_REQUESTED), or resolve directly."
    )
    # Review exits
    lines.append(
        f"- From Review: P(Revision | Review) = {p_revision_review:.3f}; "
        f"P(Merged and closed | Review) = {p_merged_review:.3f}; "
        f"P(Unmerged and closed | Review) = {p_unmerged_review:.3f}. "
        "When review occurs, this tool’s PRs resolve to merged or unmerged with the above distribution; revision loops are more likely when P(Revision | Review) is higher."
    )
    # Revision exit
    lines.append(
        f"- From Revision: P(Review | Revision) = {p_review_revision:.3f}. "
        "After revision, PRs return to Review (or in edge cases transition to a terminal state)."
    )
    lines.append("")
    return lines


def export_phase_transition_probabilities_report(
    workflows: List[PRWorkflow],
    output_path: Path,
) -> None:
    """
    Write a Markdown report of phase transition probabilities per tool family,
    including method (formula and reasons) and interpretation of each result.
    """
    counts, probs = compute_phase_transition_probabilities_by_tool(workflows)
    median_days = compute_median_duration_days_by_tool(workflows)
    lines = [
        "# Phase Transition Probabilities by Tool Family",
        "",
        "Overall probability of each phase transition for each tool family, "
        "from the PR workflow state machine (PR created → Review ⇄ Revision → Merged/Unmerged and closed).",
        "",
    ]

    # Phase definitions and clarifications
    lines.extend(_format_phase_clarifications())

    # Method: formula and reasons
    lines.extend(_format_method_section())

    # Median time (hours) per phase (state) per tool — for display on state machine diagrams
    median_per_phase = compute_median_hours_per_phase_per_tool(workflows)
    lines.append("## Median time (hours) per phase (state)")
    lines.append("")
    lines.append(
        "Median hours spent in each phase (or, for terminal states, median time from PR open to that outcome). "
        "Use these values on top of each state in the state machine diagrams."
    )
    lines.append("")
    tools_sorted = sorted(median_per_phase.keys())
    header = "| Phase | " + " | ".join(tools_sorted) + " |"
    sep = "|-------|" + "|".join(["------:" for _ in tools_sorted]) + "|"
    lines.append(header)
    lines.append(sep)
    for phase in PHASE_ORDER_FOR_MEDIAN:
        row_vals = []
        for t in tools_sorted:
            v = median_per_phase.get(t, {}).get(phase, float("nan"))
            row_vals.append(f"{v:.1f}" if v == v else "—")
        lines.append("| " + phase + " | " + " | ".join(row_vals) + " |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Canonical list of all possible transitions (ensures we report every edge; PR created -> Revision when first review is CHANGES_REQUESTED)
    transition_order = list(CANONICAL_TRANSITIONS)
    transition_order.sort(key=lambda x: (x[0], x[1]))

    # Verify we cover all transitions (no missing canonical, no unexpected observed)
    ok, coverage_warnings = verify_transition_coverage(counts, transition_order)
    if not ok:
        for w in coverage_warnings:
            lines.append(f"<!-- Verification: {w} -->")
        lines.append("")

    for tool in sorted(counts.keys()):
        lines.append(f"## {tool}")
        lines.append("")
        lines.append("| From | To | Median (h) | Count | P(To \\| From) |")
        lines.append("|------|-----|----------:|------:|-------------:|")
        tool_counts = counts[tool]
        tool_probs = probs[tool]
        tool_med = median_days.get(tool, {})
        for (f, t) in transition_order:
            c = tool_counts.get((f, t), 0)
            p = tool_probs.get((f, t), 0.0)
            if c > 0 or p > 0:
                md = tool_med.get((f, t))
                # Convert days to hours for display
                if md is not None and md == md:
                    med_str = f"{(md * 24.0):.1f}"
                else:
                    med_str = "—"
                lines.append(f"| {f} | {t} | {med_str} | {c} | {p:.3f} |")
        # Include any other observed transition not in the canonical list
        for (f, t) in sorted(tool_counts.keys()):
            if (f, t) not in transition_order:
                c = tool_counts[(f, t)]
                p = tool_probs[(f, t)]
                md = tool_med.get((f, t))
                if md is not None and md == md:
                    med_str = f"{(md * 24.0):.1f}"
                else:
                    med_str = "—"
                lines.append(f"| {f} | {t} | {med_str} | {c} | {p:.3f} |")
        lines.append("")

    # Interpretation of each result (by tool)
    lines.append("---")
    lines.append("")
    lines.append("## Interpretation of Results")
    lines.append("")
    lines.append(
        "For each tool, the tables give the exact transition counts and P(To | From). "
        "Below, key transitions are summarized and interpreted per tool."
    )
    lines.append("")

    for tool in sorted(counts.keys()):
        lines.extend(_interpretation_per_tool(tool, counts[tool], probs[tool]))

    lines.append("### Paradigm summary")
    lines.append("")
    lines.append(
        "- **Collaborator tools** (Copilot, Cursor, Devin) tend to show higher P(Review | PR created) and more Review ⇄ Revision activity; many PRs go through formal review before resolution."
    )
    lines.append(
        "- **Assistant tools** (OpenAI, Claude) tend to show lower P(Review | PR created) and higher P(Merged and closed | PR created); many PRs resolve directly from PR created without a review phase."
    )
    lines.append(
        "- **Merged and closed** vs **Unmerged and closed** distinguish successful integration from PRs closed without merge; the balance varies by tool and by from-phase."
    )
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Phase transition probability report written to {output_path}")

    # Export median hours per phase per tool for state machine diagrams
    median_per_phase = compute_median_hours_per_phase_per_tool(workflows)
    json_path = output_path.parent / "median_hours_per_phase_by_tool.json"
    # Convert nan to null for JSON
    exportable = {}
    for tool, phases in median_per_phase.items():
        exportable[tool] = {
            p: (v if v == v else None) for p, v in phases.items()
        }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(exportable, f, indent=2)
    print(f"Median hours per phase (for diagrams) written to {json_path}")


# =====================================================================
# RQ3: S2 End-to-End Workflow Path Analysis
# =====================================================================

def compute_s2_path_distribution(
    workflows: List[PRWorkflow],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Compute end-to-end workflow path distribution for S2 (Agent-Init +
    Agent-Merged) and S3 (Agent-Init + Not-Merged) PRs.

    Returns:
        {
          "S2": {tool: {path_label: count, ...}, ...},
          "S3": {tool: {path_label: count, ...}, ...},
          "totals": {"S2": int, "S3": int},
        }
    """
    result: Dict[str, Dict[str, Dict[str, int]]] = {
        "S2": defaultdict(lambda: defaultdict(int)),
        "S3": defaultdict(lambda: defaultdict(int)),
    }
    totals = {"S2": 0, "S3": 0}

    for w in workflows:
        ct = w.collaboration_type
        if ct == CollaborationType.AGENT_INITIATED_AGENT_MERGED:
            scenario = "S2"
        elif ct == CollaborationType.AGENT_INITIATED_NOT_MERGED:
            scenario = "S3"
        else:
            continue

        seq = get_phase_transition_sequence(w.events)
        path = classify_workflow_path(seq)
        result[scenario][w.tool][path] += 1
        totals[scenario] += 1

    # Convert nested defaultdicts to plain dicts
    plain: Dict[str, Dict[str, Dict[str, int]]] = {}
    for scenario in ("S2", "S3"):
        plain[scenario] = {
            tool: dict(paths) for tool, paths in result[scenario].items()
        }
    plain["totals"] = totals  # type: ignore[assignment]
    return plain


def export_s2_path_analysis_report(
    workflows: List[PRWorkflow],
    output_path: Path,
) -> None:
    """
    Write a Markdown report of S2/S3 end-to-end workflow path distributions
    per tool (RQ3 data).
    """
    dist = compute_s2_path_distribution(workflows)
    lines = [
        "# RQ3: S2 End-to-End Workflow Path Distribution",
        "",
        "Classifies each S2 (Agent-Init + Agent-Merged) and S3 (Agent-Init + Not-Merged) PR "
        "into one of eight canonical paths based on its phase transition sequence. "
        "Path labels use state machine terminology: PR created, Review, Revision, Merged and closed, Unmerged and closed.",
        "",
        f"**S2 total:** {dist['totals']['S2']} PRs | **S3 total:** {dist['totals']['S3']} PRs",
        "",
    ]

    for scenario, label, paths_group in [
        ("S2", "S2: Agent-Initiated + Agent-Merged (merged paths)", WORKFLOW_PATHS_MERGED),
        ("S3", "S3: Agent-Initiated + Not-Merged (contrast)", WORKFLOW_PATHS_UNMERGED),
    ]:
        lines.append(f"## {label}")
        lines.append("")

        tool_data = dist[scenario]
        tools = sorted(tool_data.keys()) if tool_data else []

        if not tools:
            lines.append("_No PRs in this scenario._")
            lines.append("")
            continue

        # Table header
        header = "| Path | " + " | ".join(tools) + " | Total |"
        sep = "|------|" + "|".join(["------:" for _ in tools]) + "|------:|"
        lines.append(header)
        lines.append(sep)

        for path in paths_group:
            row_vals = []
            row_total = 0
            for t in tools:
                c = tool_data.get(t, {}).get(path, 0)
                row_vals.append(str(c))
                row_total += c
            label = PATH_DISPLAY_LABELS.get(path, path)
            lines.append(f"| {label} | " + " | ".join(row_vals) + f" | {row_total} |")

        lines.append("")

        # Also show paths from the OTHER group that appear (they shouldn't for S2/S3,
        # but guard against edge cases)
        other_paths = WORKFLOW_PATHS_UNMERGED if scenario == "S2" else WORKFLOW_PATHS_MERGED
        unexpected = []
        for path in other_paths:
            total = sum(tool_data.get(t, {}).get(path, 0) for t in tools)
            if total > 0:
                unexpected.append((path, total))
        if unexpected:
            lines.append("⚠️ Unexpected paths in " + scenario + ":")
            for p, c in unexpected:
                lines.append(f"  - {PATH_DISPLAY_LABELS.get(p, p)}: {c}")
            lines.append("")

    # Per-PR detail for S2 (small sample, useful for verification)
    lines.append("## S2 Per-PR Detail")
    lines.append("")
    lines.append("| Tool | PR ID | Path | Rev. Cycles | Duration (h) | URL |")
    lines.append("|------|-------|------|:-----------:|-------------:|-----|")
    for w in workflows:
        if w.collaboration_type != CollaborationType.AGENT_INITIATED_AGENT_MERGED:
            continue
        seq = get_phase_transition_sequence(w.events)
        path = classify_workflow_path(seq)
        path_label = PATH_DISPLAY_LABELS.get(path, path)
        dur = w.duration_hours
        dur_str = f"{dur:.1f}" if dur is not None else "—"
        url_cell = f"[Link]({w.url})" if w.url else "—"
        lines.append(f"| {w.tool} | {w.pr_id[:20]} | {path_label} | {w.revision_cycles} | {dur_str} | {url_cell} |")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"S2 path analysis report written to {output_path}")


def export_network_to_json(
    nodes: Dict[str, NetworkNode],
    edges: List[NetworkEdge],
    output_path: Path
) -> None:
    """Export network to JSON format."""
    network_data = {
        "nodes": [
            {
                "id": node.node_id,
                "type": node.node_type,
                **node.attributes
            }
            for node in nodes.values()
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "weight": edge.weight,
                **edge.attributes
            }
            for edge in edges
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(network_data, f, indent=2, ensure_ascii=False)
    
    print(f"Exported network to {output_path}")
    print(f"  Nodes: {len(network_data['nodes'])}")
    print(f"  Edges: {len(network_data['edges'])}")


def extract_all_networks(
    workflows: List[PRWorkflow],
    output_dir: Path
) -> None:
    """
    Extract all network types and export to JSON files.
    
    Args:
        workflows: List of PRWorkflow objects
        output_dir: Directory to save network JSON files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting networks from {len(workflows)} workflows...")
    
    # Actor network
    print("\n1. Extracting actor collaboration network...")
    actor_nodes, actor_edges = extract_actor_network(workflows)
    export_network_to_json(
        actor_nodes,
        actor_edges,
        output_dir / "actor_network.json"
    )
    
    # Repository-tool network
    print("\n2. Extracting repository-tool network...")
    repo_tool_nodes, repo_tool_edges = extract_repository_tool_network(workflows)
    export_network_to_json(
        repo_tool_nodes,
        repo_tool_edges,
        output_dir / "repository_tool_network.json"
    )
    
    # Phase transition network
    print("\n3. Extracting phase transition network...")
    phase_nodes, phase_edges = extract_phase_transition_network(workflows)
    export_network_to_json(
        phase_nodes,
        phase_edges,
        output_dir / "phase_transition_network.json"
    )

    # Phase transition probabilities by tool family
    print("\n4. Computing phase transition probabilities by tool family...")
    export_phase_transition_probabilities_report(
        workflows,
        output_dir / "phase_transition_probabilities_by_tool.md",
    )

    # S2 end-to-end path analysis (RQ3)
    print("\n5. Computing S2/S3 end-to-end workflow path distribution...")
    export_s2_path_analysis_report(
        workflows,
        output_dir / "s2_path_analysis.md",
    )
    
    print("\n✓ Network extraction complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract network structures from PR workflows"
    )
    parser.add_argument(
        "--tool",
        choices=list(FILES.keys()),
        help="Extract networks for specific tool (default: all tools)"
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        help="Maximum PRs to process per tool (for testing)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".tmp/networks"),
        help="Output directory for network JSON files"
    )
    parser.add_argument(
        "--exclude-incomplete",
        action="store_true",
        help="Exclude PRs with no merged/closed event (matches evidence_stats --exclude-incomplete)"
    )
    
    args = parser.parse_args()
    
    # Load workflows
    if args.tool:
        tools = [args.tool]
    else:
        tools = list(FILES.keys())
    
    all_workflows = []
    for tool in tools:
        print(f"Loading workflows for {tool}...")
        workflows = load_and_analyze_tool(tool, max_prs=args.max_prs)
        if args.exclude_incomplete:
            before = len(workflows)
            workflows = [w for w in workflows if getattr(w, "resolver_origin", None) != "incomplete_timeline"]
            print(f"  Loaded {len(workflows)} workflows (excluded {before - len(workflows)} incomplete)")
        else:
            print(f"  Loaded {len(workflows)} workflows")
        all_workflows.extend(workflows)
    
    # Extract networks
    extract_all_networks(all_workflows, args.output_dir)

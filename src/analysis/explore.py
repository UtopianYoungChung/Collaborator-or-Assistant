"""
Dataset Exploration Script for AIDev PR Timelines
Analyzes the structure and content of PR timeline data from 5 AI coding tools.
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Configure encoding for Windows (only in non-notebook environments)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    # In Jupyter notebooks, sys.stdout doesn't support reconfigure
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "data" / "raw"

FILES = {
    'Claude': 'pr_timelines_Claude_Code.json',
    'Copilot': 'pr_timelines_Copilot.json',
    'Cursor': 'pr_timelines_Cursor.json',
    'Devin': 'pr_timelines_Devin.json',
    'OpenAI': 'pr_timelines_OpenAI_Codex.json'
}


def load_dataset(tool_name: str) -> dict:
    """Load PR timeline data for a specific tool."""
    filepath = DATASET_DIR / FILES[tool_name]
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_event_types(data: dict) -> Counter:
    """Extract all event types from a dataset."""
    event_types = Counter()
    for pr_id, events in data.items():
        for event in events:
            if isinstance(event, dict) and 'event' in event:
                event_types[event['event']] += 1
    return event_types


def classify_actor(actor: dict) -> str:
    """Classify an actor as 'bot' or 'human'."""
    if not actor or not isinstance(actor, dict):
        return 'unknown'
    login = actor.get('login', actor.get('name', ''))
    if '[bot]' in str(login) or 'bot' in str(login).lower():
        return 'bot'
    return 'human' if login else 'unknown'


def analyze_actors(data: dict) -> dict:
    """Analyze bot vs human activity in a dataset."""
    results = {'bot': Counter(), 'human': Counter(), 'unknown': 0}
    
    for pr_id, events in data.items():
        for event in events:
            if isinstance(event, dict):
                actor = (event.get('actor') or event.get('author') or 
                        event.get('user') or event.get('committer'))
                actor_type = classify_actor(actor)
                if actor_type == 'unknown':
                    results['unknown'] += 1
                else:
                    login = actor.get('login', actor.get('name', ''))
                    results[actor_type][login] += 1
    return results


def summarize_dataset(tool_name: str) -> dict:
    """Generate summary statistics for a tool's dataset."""
    data = load_dataset(tool_name)
    event_types = get_event_types(data)
    actor_analysis = analyze_actors(data)
    
    total_prs = len(data)
    total_events = sum(len(events) for events in data.values())
    
    return {
        'tool': tool_name,
        'total_prs': total_prs,
        'total_events': total_events,
        'avg_events_per_pr': total_events / total_prs if total_prs > 0 else 0,
        'event_types': event_types,
        'bot_events': sum(actor_analysis['bot'].values()),
        'human_events': sum(actor_analysis['human'].values()),
        'unique_humans': len(actor_analysis['human']),
        'top_bots': actor_analysis['bot'].most_common(5)
    }


def print_summary():
    """Print summary for all tools."""
    print("=" * 70)
    print("AIDev Dataset Summary")
    print("=" * 70)
    
    totals = {'prs': 0, 'events': 0}
    
    for tool in FILES.keys():
        summary = summarize_dataset(tool)
        totals['prs'] += summary['total_prs']
        totals['events'] += summary['total_events']
        
        print(f"\n{tool}:")
        print(f"  PRs: {summary['total_prs']:,}")
        print(f"  Total events: {summary['total_events']:,}")
        print(f"  Avg events/PR: {summary['avg_events_per_pr']:.1f}")
        print(f"  Bot events: {summary['bot_events']:,}")
        print(f"  Human events: {summary['human_events']:,}")
        print(f"  Unique humans: {summary['unique_humans']:,}")
        print(f"  Top 5 event types:")
        for evt, count in summary['event_types'].most_common(5):
            pct = 100 * count / summary['total_events']
            print(f"    {evt}: {count:,} ({pct:.1f}%)")
    
    print(f"\n{'=' * 70}")
    print(f"TOTAL: {totals['prs']:,} PRs, {totals['events']:,} events")
    print("=" * 70)


if __name__ == "__main__":
    print_summary()

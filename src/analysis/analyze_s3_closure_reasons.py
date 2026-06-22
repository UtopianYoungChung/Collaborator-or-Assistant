
import json
import re
from pathlib import Path

import sys

# Configure encoding for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    pass

def analyze_raw_reasons():
    # Direct raw load to get message bodies
    tools = ['Devin', 'Copilot']
    
    dataset_dir = Path(r"d:\OneDrive - University of Toronto\Year 2026\AIWare\data\raw")
    files = {
        'Devin': 'pr_timelines_Devin.json',
        'Copilot': 'pr_timelines_Copilot.json'
    }

    # Enhanced patterns
    patterns = {
        "Inactivity": re.compile(r"(inactivity|stale)", re.IGNORECASE),
        "Error": re.compile(r"(unexpected error|hit an error|encoding error)", re.IGNORECASE),
        "Redundant": re.compile(r"(closing in favor of|superseded by|duplicate)", re.IGNORECASE)
    }
    
    print(f"{'Tool':<10} | {'Agent-Closed':<15} | {'Inactivity':<12} | {'Error':<8} | {'Redundant':<10} | {'Other':<8}")
    print("-" * 80)

    for tool in tools:
        filepath = dataset_dir / files[tool]
        if not filepath.exists():
            print(f"File not found: {filepath}")
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        agent_closed_count = 0
        counts = {k: 0 for k in patterns}
        other_reasons = []
        
        for pr_id, events in data.items():
            # Check if this is S3 Agent-Closed
            
            # --- Identify Initiator ---
            initiator_is_agent = False
            first_commit = next((e for e in events if e.get('event') == 'committed'), None)
            
            if first_commit:
                actor = first_commit.get('actor', {}) or first_commit.get('committer', {})
                login = str(actor.get('login', actor.get('name', ''))).lower()
                atype = actor.get('type')
                
                if atype == 'Bot' or any(x in login for x in ['bot', 'devin', 'copilot', 'snyk']):
                    initiator_is_agent = True
            
            if not initiator_is_agent:
                continue

            # --- Identify Closure ---
            has_merged = any(e.get('event') == 'merged' for e in events)
            if has_merged:
                continue # S1/S2

            closed_events = [e for e in events if e.get('event') == 'closed']
            if not closed_events:
                continue # Incomplete timeline
                
            # Check who closed it
            last_closed = closed_events[-1]
            closer_actor = last_closed.get('actor', {})
            
            if not closer_actor:
                closer_login = 'unknown'
                closer_type = None
            else:
                closer_login = str(closer_actor.get('login', closer_actor.get('name', ''))).lower()
                closer_type = closer_actor.get('type')
            
            closer_is_agent = False
            if closer_type == 'Bot' or any(x in closer_login for x in ['bot', 'devin', 'copilot']):
                closer_is_agent = True
                
            if not closer_is_agent:
                continue

            # === Verified S3 Agent-Closed ===
            agent_closed_count += 1
            
            # --- Identify Reason ---
            reason_found = False
            
            # Scan comments by agent (reversed)
            for e in reversed(events):
                if e.get('event') == 'commented':
                    body = e.get('body', '') or ''
                    matched = False
                    for category, pattern in patterns.items():
                        if pattern.search(body):
                            counts[category] += 1
                            matched = True
                            break
                    if matched:
                        reason_found = True
                        break
            
            if not reason_found:
                # Capture the last comment for "Other" analysis
                last_comment = next((e.get('body', '') for e in reversed(events) if e.get('event') == 'commented'), "No comment")
                other_reasons.append(last_comment[:100].replace('\n', ' '))

        print(f"{tool:<10} | {agent_closed_count:<15} | {counts['Inactivity']:<12} | {counts['Error']:<8} | {counts['Redundant']:<10} | {len(other_reasons):<8}")

        if other_reasons:
            print(f"\nSample 'Other' reasons for {tool}:")
            for r in other_reasons[:5]:
                safe_r = r.encode('utf-8', errors='replace').decode('utf-8')
                print(f" - {safe_r}")
            print("")

if __name__ == "__main__":
    analyze_raw_reasons()

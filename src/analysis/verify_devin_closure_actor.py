
import json
import re
from pathlib import Path
import sys

# Configure encoding for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    pass

def verify_devin_closure_actor():
    filepath = Path(r"d:\OneDrive - University of Toronto\Year 2026\AIWare\data\raw\pr_timelines_Devin.json")
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    inactivity_pattern = re.compile(r"(inactivity|stale)", re.IGNORECASE)
    
    print(f"{'PR ID':<15} | {'Closer Actor':<30} | {'Closer Type':<15} | {'Inactivity Reason?':<10}")
    print("-" * 80)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    count = 0
    devin_closers = 0
    github_action_closers = 0
    
    for pr_id, events in data.items():
        # ... (Initiator check same as before to ensure S3 context) ...
        # Simplified: just look for PRs closed by *any* bot and see who it is
        
        closed_events = [e for e in events if e.get('event') == 'closed']
        if not closed_events:
            continue
            
        last_closed = closed_events[-1]
        actor = last_closed.get('actor', {})
        if not actor:
            continue
            
        login = str(actor.get('login', '')).lower()
        atype = actor.get('type')
        
        # Check if reason is inactivity
        is_inactivity = False
        for e in reversed(events):
            if e.get('event') == 'commented':
                body = e.get('body', '') or ''
                if inactivity_pattern.search(body):
                    is_inactivity = True
                    break
        
        # We only care about the ones we previously flagged as "Agent-Closed" (which includes devin/bot)
        # In our previous script, we filtered by:
        # closer_type == 'Bot' or any(x in closer_login for x in ['bot', 'devin', 'copilot'])
        
        if atype == 'Bot' or 'bot' in login or 'devin' in login:
            # specifically check for inactivity ones
            if is_inactivity:
                count += 1
                if count <= 20:
                    print(f"{pr_id:<15} | {login:<30} | {atype:<15} | {is_inactivity}")
                
                if 'devin' in login:
                    devin_closers += 1
                elif 'github-actions' in login:
                    github_action_closers += 1

    print("-" * 80)
    print(f"Total Inactivity Closures Analyzed: {count}")
    print(f"Closed by 'devin-ai-integration[bot]': {devin_closers}")
    print(f"Closed by 'github-actions[bot]': {github_action_closers}")

if __name__ == "__main__":
    verify_devin_closure_actor()

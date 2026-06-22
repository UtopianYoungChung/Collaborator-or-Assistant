
import json
import re
from pathlib import Path
import sys
import random

# Configure encoding for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    pass

def sample_devin_closure_messages():
    filepath = Path(r"d:\OneDrive - University of Toronto\Year 2026\AIWare\data\raw\pr_timelines_Devin.json")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    inactivity_pattern = re.compile(r"(inactivity|stale)", re.IGNORECASE)
    
    unique_messages = set()
    
    for pr_id, events in data.items():
        # Check if closed by Devin
        closed_events = [e for e in events if e.get('event') == 'closed']
        if not closed_events:
            continue
            
        last_closed = closed_events[-1]
        actor = last_closed.get('actor', {})
        if not actor:
            continue
            
        login = str(actor.get('login', '')).lower()
        if 'devin' not in login:
            continue
            
        # Find the comment
        for e in reversed(events):
            if e.get('event') == 'commented':
                body = e.get('body', '') or ''
                if inactivity_pattern.search(body):
                    # Clean up the message for display (take first line or reasonable chunk)
                    clean_body = body.strip().replace('\n', ' ')
                    if len(clean_body) > 150:
                        clean_body = clean_body[:150] + "..."
                    unique_messages.add(clean_body)
                    break
    
    print(f"Found {len(unique_messages)} unique variations of inactivity messages.")
    print("-" * 80)
    for msg in list(unique_messages)[:20]:
        print(f" - {msg}")

if __name__ == "__main__":
    sample_devin_closure_messages()


import json
from pathlib import Path

def inspect_devin_closure():
    filepath = Path(r"d:\OneDrive - University of Toronto\Year 2026\AIWare\data\raw\pr_timelines_Devin.json")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"Total PRs: {len(data)}")
        item_keys = list(data.keys())
        print(f"Sample keys: {item_keys[:5]}")
        
        target_prs = ['2768448959', '2819000175', '3023333914'] # whitphx/vscode-emacs-mcx#2148, airbytehq/airbyte#52634
        
        print("\n--- Inspecting Devin PR Closures ---")
        
        for pr_id, events in data.items():
            base_id = str(pr_id).replace('.json', '')
            if base_id in target_prs:
                print(f"\nPR ID: {pr_id}")
                # Print last 5 events to see context
                for event in events[-5:]:
                    etype = event.get('event')
                    actor = event.get('actor', {}).get('login') if isinstance(event.get('actor'), dict) else None
                    body = event.get('body') or event.get('message')
                    try:
                        print(f"  Event: {etype}, Actor: {actor}")
                        if body:
                            safe_body = body[:200].encode('utf-8', errors='replace').decode('utf-8')
                            print(f"    Body: {safe_body}...")
                    except Exception:
                        print(f"  Event: {etype} (encoding error)")
                        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_devin_closure()

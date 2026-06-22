
import json
import os
from pathlib import Path
from src.analysis.workflows import (
    load_and_analyze_tool, 
    CollaborationType, 
    PRWorkflow
)

def find_s3_agent_closed():
    tools = ['Claude', 'Copilot', 'Cursor', 'Devin', 'OpenAI']
    
    print(f"{'Tool':<15} | {'S3 Total':<10} | {'S3 Agent-Closed':<15}")
    print("-" * 45)
    
    all_agent_closed_s3 = []
    
    for tool in tools:
        try:
            workflows = load_and_analyze_tool(tool)
            s3_workflows = [w for w in workflows if w.collaboration_type == CollaborationType.AGENT_INITIATED_NOT_MERGED]
            
            # Agent-closed means resolver_origin == 'closed' AND closer == 'Agent'
            # Note: S3 also includes 'incomplete_timeline', so we must check resolver_origin
            agent_closed_s3 = [w for w in s3_workflows if w.resolver_origin == 'closed' and w.closer == 'Agent']
            
            print(f"{tool:<15} | {len(s3_workflows):<10} | {len(agent_closed_s3):<15}")
            
            for w in agent_closed_s3:
                all_agent_closed_s3.append({
                    'tool': tool,
                    'pr_id': w.pr_id,
                    'url': w.url,
                    'repo': w.repo
                })
        except Exception as e:
            print(f"Error analyzing {tool}: {e}")

    print("\n--- Examples of S3 PRs closed by Agents (grouped by tool) ---")
    if not all_agent_closed_s3:
        print("No S3 PRs closed by agents found.")
    else:
        for tool in tools:
            tool_examples = [pr for pr in all_agent_closed_s3 if pr['tool'] == tool]
            if tool_examples:
                print(f"\nTool: {tool} ({len(tool_examples)} PRs)")
                for i, pr in enumerate(tool_examples[:5]):
                    print(f"  {i+1}. {pr['repo']}#{pr['pr_id']} - {pr['url']}")
                if len(tool_examples) > 5:
                    print(f"  ... and {len(tool_examples) - 5} more.")

if __name__ == "__main__":
    find_s3_agent_closed()

"""Shared state definition for the LangGraph workflow.

The `AgentState` TypedDict represents the evolving blackboard-style state that
is passed between nodes in the graph. Each node reads and writes a subset of
these fields while building up the final analysis and execution trace.
"""

from typing import Dict, List, Optional, TypedDict, Any

print("[DEBUG] app.state: Module import start")


class StepDict(TypedDict):
    module: str
    prompt: Dict[str, Any]
    response: Dict[str, Any]


class AgentState(TypedDict, total=False):
    resume_text: str
    github_url: Optional[str]       
    github_username: Optional[str]  

    # Screening Data
    screening_decision: Optional[str] 
    screening_feedback: Optional[str]

    # Git Loop Data
    user_repos_metadata: Optional[str]      
    git_plan: Optional[str]                 
    technical_analysis: Optional[str]       
    git_iteration_count: int 
    
    # New Field: Track visited repos to avoid duplicates
    visited_repos: Optional[List[str]] 

    # Replan Logic
    replan_decision: str

    # Final Output
    final_analysis: str

    steps: List[StepDict]


print("[DEBUG] app.state: Module import end")

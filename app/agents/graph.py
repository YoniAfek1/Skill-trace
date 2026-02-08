"""Graph wiring for the multi-agent LangGraph workflow.

This module connects the individual agent nodes into a StateGraph, defining
the high-level control flow: input parsing, resume screening, supervisor
routing, GitHub analysis loop, and final aggregation.
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from app.state import AgentState
from app.agents.nodes import (
    input_parser_node,
    screening_agent_node,
    git_planner_node,
    git_executor_node,
    git_replan_node,
    final_analysis_node,
)

print("[DEBUG] app.agents.graph: Module import start")


def _supervisor_decision(state: AgentState) -> Literal["git_planner", "final_analysis"]:
    """Decide whether to enter the Git loop or finish early.

    The supervisor looks at the high-level screening decision and the presence
    of a GitHub URL. If the candidate is deemed irrelevant or no URL is found,
    the graph jumps directly to the final analysis node; otherwise it proceeds
    to the Git planner.

    Args:
        state: Current `AgentState` with screening information and URL.

    Returns:
        The name of the next logical node: either ``\"git_planner\"`` or
        ``\"final_analysis\"``.
    """
    print("[DEBUG] _supervisor_decision: start")
    # Extract decision (default NO if missing for safety).
    decision = state.get("screening_decision", "NO")
    url = state.get("github_url")

    print(f"[DEBUG] Supervisor Check -> Decision: {decision}, URL: {url}")

    # 1. Check the screening decision.
    if decision == "NO":
        print("[DEBUG] supervisor: Rejected (Decision is NO). Going to Final Analysis.")
        return "final_analysis"

    # 2. Ensure a GitHub URL exists.
    if not url:
        print("[DEBUG] supervisor: No URL found. Going to Final Analysis.")
        return "final_analysis"

    # 3. Approved: continue with Git analysis.
    print("[DEBUG] supervisor: Approved. Going to Git Planner.")
    return "git_planner"


def _router_git_replan(state: AgentState) -> Literal["git_planner", "final_analysis"]:
    """Route back into the Git loop or exit based on the replanner decision.

    Args:
        state: Current `AgentState` containing the `replan_decision` flag.

    Returns:
        ``\"git_planner\"`` when another iteration is required, otherwise
        ``\"final_analysis\"``.
    """
    decision = state.get("replan_decision", "FINISH")
    if decision == "RETRY":
        return "git_planner"
    return "final_analysis"


def build_graph():
    """Construct and compile the LangGraph StateGraph for this project.

    The resulting graph function can be invoked with an initial `AgentState`
    and will drive the entire multi-agent pipeline until termination.

    Returns:
        A compiled LangGraph application that can be used by the FastAPI layer.
    """
    print("[DEBUG] build_graph: start")
    workflow = StateGraph(AgentState)

    # --- Nodes ---
    workflow.add_node("input_parser", input_parser_node)
    workflow.add_node("screening", screening_agent_node)
    workflow.add_node("git_planner", git_planner_node)
    workflow.add_node("git_executor", git_executor_node)
    workflow.add_node("git_replan", git_replan_node)
    workflow.add_node("final_analysis", final_analysis_node)

    # --- Edges ---

    # Entry
    workflow.set_entry_point("input_parser")
    workflow.add_edge("input_parser", "screening")

    # Supervisor decision
    workflow.add_conditional_edges(
        "screening",
        _supervisor_decision,
        {
            "git_planner": "git_planner",
            "final_analysis": "final_analysis",
        },
    )

    # Git loop
    workflow.add_edge("git_planner", "git_executor")
    workflow.add_edge("git_executor", "git_replan")

    # Replan loop
    workflow.add_conditional_edges(
        "git_replan",
        _router_git_replan,
        {
            "git_planner": "git_planner",
            "final_analysis": "final_analysis",
        },
    )

    # Exit
    workflow.add_edge("final_analysis", END)

    return workflow.compile()


print("[DEBUG] app.agents.graph: Module import end")
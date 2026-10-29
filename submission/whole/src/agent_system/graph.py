from typing import Literal
from langgraph.graph import END, StateGraph

from agent_system.agents.reviewer import reviewer_node
from agent_system.agents.secretary import secretary_node
from agent_system.agents.swe import swe_node
from agent_system.state import AgentState

MAX_RETRIES = 3


def should_continue(state: AgentState) -> Literal["swe", "__end__"]:
    """
    Conditional routing edge after Reviewer:
    - If compilation succeeded (compiler_error is None), terminate workflow.
    - If compilation failed and retries remain, send the error back for another attempt.
    - If max retries exceeded, terminate workflow.
    """
    if state.compiler_error is None:
        return END

    if state.retry_count < MAX_RETRIES:
        return "swe"

    return END


def create_agent_graph():
    """Compiles the Secretary -> SWE -> Reviewer LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # 1. Register agent nodes
    workflow.add_node("secretary", secretary_node)
    workflow.add_node("swe", swe_node)
    workflow.add_node("reviewer", reviewer_node)

    # 2. Define flow edges
    workflow.set_entry_point("secretary")
    workflow.add_edge("secretary", "swe")
    workflow.add_edge("swe", "reviewer")

    # 3. Add the retry loop for compilation errors
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "swe": "swe",
            END: END,
        },
    )

    return workflow.compile()
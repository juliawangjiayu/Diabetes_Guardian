"""
agent/graph.py

LangGraph StateGraph definition for the diabetes monitoring agent.
Pipeline: Investigator → Reflector → (conditional) Communicator → END
"""

from langgraph.graph import END, StateGraph

from agent.nodes.communicator import communicator_node
from agent.nodes.investigator import investigator_node
from agent.nodes.reflector import reflector_node
from agent.state import AgentState


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph workflow.

    Flow:
    1. Investigator: gathers context from MCP Servers
    2. Reflector: LLM-based clinical risk assessment
    3. Communicator: generates and sends user notification (only if action needed)
    """
    graph = StateGraph(AgentState)

    graph.add_node("investigator", investigator_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("communicator", communicator_node)

    graph.set_entry_point("investigator")
    graph.add_edge("investigator", "reflector")

    # Skip communicator if no intervention is needed
    graph.add_conditional_edges(
        "reflector",
        lambda state: (
            "communicator" if state["intervention_action"] != "NO_ACTION" else END
        ),
    )
    graph.add_edge("communicator", END)

    return graph.compile()

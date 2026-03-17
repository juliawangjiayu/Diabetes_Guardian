"""
agent/graph.py

LangGraph StateGraph definition.
Three-node pipeline: Investigator -> Reflector -> Communicator (conditional).
"""

from langgraph.graph import END, StateGraph

from agent.nodes.communicator import communicator_node
from agent.nodes.investigator import investigator_node
from agent.nodes.reflector import reflector_node
from agent.state import AgentState


def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("investigator", investigator_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("communicator", communicator_node)

    graph.set_entry_point("investigator")
    graph.add_edge("investigator", "reflector")
    graph.add_edge("reflector", "communicator")
    graph.add_edge("communicator", END)

    return graph.compile()

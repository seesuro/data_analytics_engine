# Analytics graph implementation
from langgraph.graph import StateGraph

from state.analytics_state import AnalyticsState
from agents.planner_agent import planner_agent
from agents.analysis_agent import analysis_agent
from agents.visualization_agent import visualization_agent
from agents.reporting_agent import reporting_agent


def build_graph():
    graph = StateGraph(AnalyticsState)

    graph.add_node("planner", planner_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("viz", visualization_agent)
    graph.add_node("report", reporting_agent)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "analysis")
    graph.add_edge("analysis", "viz")
    graph.add_edge("viz", "report")

    return graph.compile()


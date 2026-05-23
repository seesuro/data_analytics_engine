# Analytics graph implementation
from langgraph.graph import StateGraph

from state.analytics_state import AnalyticsState

from agents.planner_agent import planner_agent
from agents.analysis_agent import analysis_agent
from agents.visualization_agent import visualization_agent
from agents.reporting_agent import reporting_agent
from agents.sql_agent import sql_agent
from agents.intent_router import intent_router
from agents.sql_repair_agent import sql_repair_agent


def build_graph():
    graph = StateGraph(AnalyticsState)

    graph.add_node("intent_router", intent_router)
    graph.add_node("planner", planner_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("sql", sql_agent)
    graph.add_node("sql_repair", sql_repair_agent)
    graph.add_node("viz", visualization_agent)
    graph.add_node("report", reporting_agent)

    graph.set_entry_point("intent_router")

    # Routing logic based on detected intent
    def intent_edge(state):
        intent = state.get("intent")
        if intent in ("list_tables", "describe_table"):
            return "viz"  # go directly to viz (and then report)
        else:
            return "planner"

    graph.add_conditional_edges("intent_router", intent_edge)
    graph.add_edge("planner", "analysis")
    graph.add_edge("analysis", "sql")

    def sql_edge(state):
        if state.get("sql_error") and state.get("sql_repair_attempts", 0) < state.get("max_sql_repair_attempts", 1):
            return "sql_repair"
        return "viz"

    graph.add_conditional_edges("sql", sql_edge)
    graph.add_edge("sql_repair", "sql")
    graph.add_edge("viz", "report")

    return graph.compile()


# Planner agent implementation
from engine.runtime import runtime_from_state
from llm.llm_factory import resolve_llm
from utils.debug import debug_state


def planner_agent(state):
    llm = resolve_llm(state)
    debug_state("Planner Agent Input", state)
    metadata = runtime_from_state(state).metadata
    prompt = f"""
You are a senior data analyst planning a DuckDB query.

User question:
{state['user_query']}

Available metadata:
{metadata}

Create a compact analysis plan for generating SQL.
Rules:
- Use only tables and columns present in metadata.
- Identify required table, measures, dimensions, filters, grouping, ordering, and row limits.
- Do not invent columns or business definitions.
- If the question is ambiguous, choose the simplest reasonable interpretation and state the assumption.
- Keep the plan under 8 bullets.
"""

    response = llm.invoke(prompt)
    state["plan"] = response.content
    debug_state("Planner Agent Output", state)
    return state

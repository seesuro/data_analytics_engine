# Planner agent implementation
from llm.llm_factory import get_llm
from utils.debug import debug_state
def planner_agent(state):
    llm = get_llm()
    debug_state("Planner Agent Input", state)
    prompt = f"""
    You are a data planner.
    User query: {state['user_query']}

    Create a step-by-step plan.
    """

    response = llm.invoke(prompt)
    state["plan"] = response.content
    debug_state("Planner Agent Output", state)
    return state
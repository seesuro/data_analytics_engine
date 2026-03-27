# Planner agent implementation
from llm.llm_factory import get_llm

def planner_agent(state):
    llm = get_llm()
    prompt = f"""
    You are a data planner.
    User query: {state['user_query']}

    Create a step-by-step plan.
    """

    response = llm.invoke(prompt)
    state["plan"] = response.content
    return state
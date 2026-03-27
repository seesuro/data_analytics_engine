# Analysis agent implementation
from llm.llm_factory import get_llm


def analysis_agent(state):
    llm = get_llm()

    prompt = f"""
    Convert the plan into SQL.

    Plan:
    {state['plan']}
    """

    response = llm.invoke(prompt)
    state["sql_query"] = response.content
    return state
# Reporting agent implementation
from llm.llm_factory import get_llm


def reporting_agent(state):
    llm = get_llm()

    prompt = f"""
    Summarize the analysis result:

    {state['result']}
    """

    response = llm.invoke(prompt)
    state["report"] = response.content
    return state
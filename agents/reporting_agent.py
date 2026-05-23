# Reporting agent implementation
from llm.llm_factory import resolve_llm
from utils.debug import debug_state

def reporting_agent(state):
    llm = resolve_llm(state)
    debug_state("Reporting Agent Input", state)
    # Format DataFrame result for LLM if needed
    result = state.get("result")
    if result is not None:
        try:
            # If result is a DataFrame, convert to string
            import pandas as pd
            if isinstance(result, pd.DataFrame):
                result_str = result.to_markdown(index=False)
            else:
                result_str = str(result)
        except Exception:
            result_str = str(result)
    else:
        result_str = "No result available."

    prompt = f"""
    Summarize the analysis result:

    {result_str}
    """

    response = llm.invoke(prompt)
    state["report"] = response.content
    debug_state("Reporting Agent Output", state)
    return state

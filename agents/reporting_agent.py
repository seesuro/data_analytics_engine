# Reporting agent implementation
from llm.llm_factory import resolve_llm
from utils.debug import debug_state

def reporting_agent(state):
    llm = resolve_llm(state)
    debug_state("Reporting Agent Input", state)
    sql_error = state.get("sql_error")
    if sql_error:
        state["report"] = f"SQL execution failed: {sql_error}"
        debug_state("Reporting Agent Output", state)
        return state

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
You are a concise data analyst writing a final answer for a user.

User question:
{state.get('user_query', '')}

SQL executed:
{state.get('sql_query', '')}

Result table:
{result_str}

Write a short answer grounded only in the result table.
Rules:
- Mention the key finding first.
- Include relevant numbers exactly as shown.
- Do not invent causes, recommendations, or missing context.
- If the result is empty or unavailable, say that clearly.
"""

    response = llm.invoke(prompt)
    state["report"] = response.content
    debug_state("Reporting Agent Output", state)
    return state

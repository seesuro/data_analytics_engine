# Analysis agent implementation
from llm.llm_factory import get_llm
from utils.debug import debug_state
import json
def analysis_agent(state):
    llm = get_llm()
    debug_state("Analysis Agent Input", state)

    # Use metadata in the prompt for deterministic SQL
    metadata = state.get("metadata", {})
    metadata_str = json.dumps(metadata, indent=2) if metadata else "No metadata available."


    prompt = f"""
    Convert the plan into a single deterministic SQL query.
    Use the following metadata for table and column names:
    {metadata_str}

    Plan:
    {state['plan']}

    IMPORTANT: Output ONLY the SQL query, with NO explanations, comments, or markdown formatting. Do not use code fences. The output must be valid SQL that can be executed directly.
    """


    response = llm.invoke(prompt)
    sql_query = response.content.strip()
    # Remove markdown code fences if present
    if sql_query.startswith("```sql"):
        sql_query = sql_query.removeprefix("```sql").strip()
    if sql_query.startswith("```"):
        sql_query = sql_query.removeprefix("```").strip()
    if sql_query.endswith("```"):
        sql_query = sql_query.removesuffix("```").strip()
    state["sql_query"] = sql_query

    # Do NOT execute SQL here; handled by sql_agent for separation of concerns
    debug_state("After Analysis Agent", state)
    return state
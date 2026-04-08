# Intent router agent for schema/meta queriess
from utils.debug import debug_state
from llm.llm_factory import get_llm

def intent_router(state):
    query = state["user_query"]
    db = state["db"]
    debug_state("Intent Router Input", state)

    llm = get_llm()
    prompt = f"""
    Classify the following user query into one of these intents:
    - list_tables: if the user wants to see what tables or data are available
    - describe_table: if the user wants to see the schema or columns of a specific table
    - analysis: for all other analytical or data questions

    User query: \"{query}\"

    Respond with only the intent name (list_tables, describe_table, or analysis).
    If describe_table, also extract the table name as: describe_table:<table_name>
    """

    response = llm.invoke(prompt)
    intent_line = response.content.strip().lower()

    if intent_line.startswith("list_tables"):
        state["result"] = db.list_tables()
        state["intent"] = "list_tables"
        debug_state("Intent Router Output (list_tables)", state)
        return state
    elif intent_line.startswith("describe_table"):
        # Extract table name if present
        parts = intent_line.split(":")
        table = parts[1].strip() if len(parts) > 1 else None
        if table:
            state["result"] = db.describe_table(table)
            state["intent"] = "describe_table"
        else:
            state["result"] = None
            state["intent"] = "describe_table"
            state["sql_error"] = "Table name not found in query."
        debug_state("Intent Router Output (describe_table)", state)
        return state
    else:
        state["intent"] = "analysis"
        debug_state("Intent Router Output (analysis)", state)
        return state

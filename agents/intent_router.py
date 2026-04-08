# Intent router agent for schema/meta queries
from utils.debug import debug_state
import re

def intent_router(state):
    query = state["user_query"].lower()
    db = state["db"]
    debug_state("Intent Router Input", state)
    # Simple keyword-based intent detection
    if "list tables" in query or "show tables" in query:
        state["result"] = db.list_tables()
        state["intent"] = "list_tables"
        debug_state("Intent Router Output (list_tables)", state)
        return state
    elif "describe table" in query:
        # Extract table name
        match = re.search(r"describe table (\w+)", query)
        table = match.group(1) if match else None
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

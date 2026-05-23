# Intent router agent for schema/meta queriess
from utils.debug import debug_state
from llm.llm_factory import resolve_llm

def intent_router(state):
    query = state["user_query"]
    db = state["db"]
    debug_state("Intent Router Input", state)

    llm = resolve_llm(state)
    metadata = state.get("metadata", {})
    table_names = sorted(metadata.get("tables", {}).keys())
    prompt = f"""
You classify user requests for a DuckDB analytics assistant.

Allowed intents:
- list_tables: user asks what datasets/tables are available.
- describe_table:<table_name>: user asks for columns/schema/data dictionary for one table.
- analysis: user asks for calculations, comparisons, trends, aggregations, filters, rankings, or business answers.

Known tables: {table_names}
User query: {query}

Output exactly one line and nothing else.
If the user asks to describe a table, output describe_table:<table_name> using one known table name.
Otherwise output exactly list_tables or analysis.
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

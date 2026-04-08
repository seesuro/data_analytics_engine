# SQL execution agent implementation
from utils.debug import debug_state

def sql_agent(state):
    debug_state("SQL Agent Input", state)
    sql_query = state.get("sql_query")
    db = state.get("db")
    if db is not None and sql_query:
        try:
            df = db.run_query(sql_query)
            state["result"] = df
            state["sql_error"] = None
        except Exception as e:
            state["result"] = None
            state["sql_error"] = str(e)
    else:
        state["result"] = None
        state["sql_error"] = "No database connection or SQL query provided."
    debug_state("SQL Agent Output", state)
    return state

import json

from llm.llm_factory import resolve_llm
from utils.debug import debug_state


def sql_repair_agent(state):
    llm = resolve_llm(state)
    debug_state("SQL Repair Agent Input", state)

    metadata = state.get("metadata", {})
    metadata_str = json.dumps(metadata, indent=2) if metadata else "No metadata available."
    repair_attempts = state.get("sql_repair_attempts", 0) + 1

    prompt = f"""
You repair DuckDB SQL for an analytics engine.

User question:
{state.get('user_query', '')}

Schema metadata:
{metadata_str}

Previous plan:
{state.get('plan', '')}

Failed SQL:
{state.get('sql_query', '')}

DuckDB error:
{state.get('sql_error', '')}

Rules:
- Output exactly one corrected DuckDB SELECT query and nothing else.
- Use only table and column names from the schema metadata.
- Do not use markdown, comments, prose, code fences, or trailing semicolons.
- Do not use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, COPY, PRAGMA, or multiple statements.
"""

    response = llm.invoke(prompt)
    sql_query = response.content.strip()
    if sql_query.startswith("```sql"):
        sql_query = sql_query.removeprefix("```sql").strip()
    if sql_query.startswith("```"):
        sql_query = sql_query.removeprefix("```").strip()
    if sql_query.endswith("```"):
        sql_query = sql_query.removesuffix("```").strip()

    state["sql_query"] = sql_query
    state["sql_repair_attempts"] = repair_attempts
    state["sql_error"] = None
    debug_state("SQL Repair Agent Output", state)
    return state

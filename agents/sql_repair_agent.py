import json

from engine.runtime import runtime_from_state
from engine.sql_candidate import parse_sql_candidate
from llm.llm_factory import resolve_llm
from utils.debug import debug_state


def sql_repair_agent(state):
    llm = resolve_llm(state)
    debug_state("SQL Repair Agent Input", state)

    metadata = runtime_from_state(state).metadata
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
- Output exactly one JSON object and nothing else: {{"sql": "<corrected_duckdb_select_query>", "rationale": "<short repair reason>"}}
- Use only table and column names from the schema metadata.
- Do not use markdown, code fences, or trailing semicolons.
- Do not use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, COPY, PRAGMA, or multiple statements.
"""

    response = llm.invoke(prompt)
    sql_candidate = parse_sql_candidate(response.content)

    state["sql_candidate"] = sql_candidate
    state["sql_query"] = sql_candidate.sql
    state["sql_repair_attempts"] = repair_attempts
    state["sql_error"] = None
    debug_state("SQL Repair Agent Output", state)
    return state

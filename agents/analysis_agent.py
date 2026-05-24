import json

from engine.sql_candidate import parse_sql_candidate
from llm.llm_factory import resolve_llm
from utils.debug import debug_state


def analysis_agent(state):
    llm = resolve_llm(state)
    debug_state("Analysis Agent Input", state)

    metadata = state.get("metadata", {})
    metadata_str = json.dumps(metadata, indent=2) if metadata else "No metadata available."

    prompt = f"""
You generate DuckDB SQL for an analytics engine.

User question:
{state.get('user_query', '')}

Schema metadata:
{metadata_str}

Analysis plan:
{state['plan']}

Rules:
- Output exactly one JSON object and nothing else: {{"sql": "<duckdb_select_query>", "rationale": "<short reason>"}}
- Do not use markdown or code fences.
- Use only table and column names from the schema metadata.
- Prefer explicit column aliases for aggregations.
- Use GROUP BY when selecting dimensions with aggregations.
- Do not use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, COPY, PRAGMA, or multiple statements.
- Do not add a trailing semicolon.
"""

    response = llm.invoke(prompt)
    sql_candidate = parse_sql_candidate(response.content)
    state["sql_candidate"] = sql_candidate
    state["sql_query"] = sql_candidate.sql

    debug_state("After Analysis Agent", state)
    return state

# Analysis agent implementation
from llm.llm_factory import resolve_llm
from utils.debug import debug_state
import json
def analysis_agent(state):
    llm = resolve_llm(state)
    debug_state("Analysis Agent Input", state)

    # Use metadata in the prompt for deterministic SQL
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
- Output exactly one DuckDB SELECT query and nothing else.
- Do not use markdown, comments, prose, or code fences.
- Use only table and column names from the schema metadata.
- Prefer explicit column aliases for aggregations.
- Use GROUP BY when selecting dimensions with aggregations.
- Do not use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, COPY, PRAGMA, or multiple statements.
- Do not add a trailing semicolon.
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

# Intent router agent for schema/meta queriess
import json

from contracts import IntentDecision, IntentType
from utils.debug import debug_state
from llm.llm_factory import resolve_llm


def parse_intent_decision(raw_output: str) -> IntentDecision:
    cleaned = raw_output.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()
    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    try:
        return IntentDecision.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValueError):
        legacy = cleaned.lower()
        if legacy.startswith("describe_table"):
            parts = legacy.split(":", 1)
            return IntentDecision(
                intent=IntentType.DESCRIBE_TABLE,
                table_name=parts[1].strip() if len(parts) > 1 and parts[1].strip() else None,
            )
        if legacy.startswith("list_tables"):
            return IntentDecision(intent=IntentType.LIST_TABLES)
        return IntentDecision(intent=IntentType.ANALYSIS)


def intent_router(state):
    query = state["user_query"]
    db = state["db"]
    debug_state("Intent Router Input", state)

    llm = resolve_llm(state)
    metadata = state.get("metadata", {})
    table_names = sorted(metadata.get("tables", {}).keys())
    prompt = f"""
You classify user requests for a DuckDB analytics assistant.

Allowed intent values:
- list_tables: user asks what datasets/tables are available.
- describe_table: user asks for columns/schema/data dictionary for one table.
- analysis: user asks for calculations, comparisons, trends, aggregations, filters, rankings, or business answers.

Known tables: {table_names}
User query: {query}

Output exactly one JSON object and nothing else:
{{"intent": "list_tables", "table_name": null}}
{{"intent": "describe_table", "table_name": "<known_table_name>"}}
{{"intent": "analysis", "table_name": null}}
If the user asks to describe a table, use one known table name.
"""

    response = llm.invoke(prompt)
    decision = parse_intent_decision(response.content)
    state["intent_decision"] = decision

    if decision.intent == IntentType.LIST_TABLES:
        state["result"] = db.list_tables()
        state["intent"] = decision.intent.value
        debug_state("Intent Router Output (list_tables)", state)
        return state
    elif decision.intent == IntentType.DESCRIBE_TABLE:
        table = decision.table_name
        if table:
            state["result"] = db.describe_table(table)
            state["intent"] = decision.intent.value
        else:
            state["result"] = None
            state["intent"] = decision.intent.value
            state["sql_error"] = "Table name not found in query."
        debug_state("Intent Router Output (describe_table)", state)
        return state
    else:
        state["intent"] = decision.intent.value
        debug_state("Intent Router Output (analysis)", state)
        return state

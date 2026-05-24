from types import SimpleNamespace

from agents.intent_router import intent_router, parse_intent_decision
from contracts import IntentType


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


class _StubDB:
    def list_tables(self):
        return [("t1",), ("t2",)]

    def describe_table(self, table_name: str):
        return {"table": table_name}


def test_intent_router_list_tables():
    state = {
        "user_query": "what tables exist?",
        "db": _StubDB(),
        "llm": _StubLLM('{"intent": "list_tables", "table_name": null}'),
    }
    out = intent_router(state)

    assert out["intent"] == "list_tables"
    assert out["intent_decision"].intent == IntentType.LIST_TABLES
    assert out["result"] == [("t1",), ("t2",)]


def test_intent_router_describe_table_with_name():
    state = {
        "user_query": "describe sales",
        "db": _StubDB(),
        "llm": _StubLLM('{"intent": "describe_table", "table_name": "sales"}'),
    }
    out = intent_router(state)

    assert out["intent"] == "describe_table"
    assert out["result"] == {"table": "sales"}


def test_parse_intent_decision_accepts_json_code_fence():
    decision = parse_intent_decision('```json\n{"intent": "analysis", "table_name": null}\n```')

    assert decision.intent == IntentType.ANALYSIS
    assert decision.table_name is None


def test_parse_intent_decision_accepts_legacy_describe_table():
    decision = parse_intent_decision("describe_table:sales")

    assert decision.intent == IntentType.DESCRIBE_TABLE
    assert decision.table_name == "sales"


def test_parse_intent_decision_defaults_invalid_output_to_analysis():
    decision = parse_intent_decision("I think you should analyze this.")

    assert decision.intent == IntentType.ANALYSIS

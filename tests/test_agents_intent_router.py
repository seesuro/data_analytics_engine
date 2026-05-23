from types import SimpleNamespace

from agents.intent_router import intent_router


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
    state = {"user_query": "what tables exist?", "db": _StubDB(), "llm": _StubLLM("list_tables")}
    out = intent_router(state)

    assert out["intent"] == "list_tables"
    assert out["result"] == [("t1",), ("t2",)]


def test_intent_router_describe_table_with_name():
    state = {"user_query": "describe sales", "db": _StubDB(), "llm": _StubLLM("describe_table:sales")}
    out = intent_router(state)

    assert out["intent"] == "describe_table"
    assert out["result"] == {"table": "sales"}

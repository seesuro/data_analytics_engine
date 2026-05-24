from types import SimpleNamespace

from agents.sql_repair_agent import sql_repair_agent


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_sql_repair_agent_rewrites_sql_and_increments_attempts():
    state = {
        "user_query": "show regions",
        "plan": "Use sales table.",
        "sql_query": "SELECT bad_column FROM sales",
        "sql_error": "Binder Error: column not found",
        "metadata": {"tables": {"sales": {"columns": {"region": "VARCHAR"}}}},
        "llm": _StubLLM('{"sql": "SELECT region FROM sales", "rationale": "Use existing region column"}'),
        "sql_repair_attempts": 0,
    }

    out = sql_repair_agent(state)

    assert out["sql_query"] == "SELECT region FROM sales"
    assert out["sql_candidate"].rationale == "Use existing region column"
    assert out["sql_error"] is None
    assert out["sql_repair_attempts"] == 1


def test_sql_repair_agent_keeps_raw_sql_fallback():
    state = {
        "user_query": "show regions",
        "plan": "Use sales table.",
        "sql_query": "SELECT bad_column FROM sales",
        "sql_error": "Binder Error: column not found",
        "metadata": {"tables": {"sales": {"columns": {"region": "VARCHAR"}}}},
        "llm": _StubLLM("```sql\nSELECT region FROM sales\n```"),
        "sql_repair_attempts": 0,
    }

    out = sql_repair_agent(state)

    assert out["sql_query"] == "SELECT region FROM sales"

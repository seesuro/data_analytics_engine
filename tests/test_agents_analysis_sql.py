from types import SimpleNamespace

from agents.analysis_agent import analysis_agent


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_analysis_agent_strips_sql_code_fences(monkeypatch):
    monkeypatch.setattr(
        "agents.analysis_agent.get_llm",
        lambda: _StubLLM("```sql\nSELECT 1 AS one;\n```"),
    )

    state = {"plan": "Any plan", "metadata": {"tables": {}}}
    out = analysis_agent(state)
    assert out["sql_query"].strip() == "SELECT 1 AS one;"


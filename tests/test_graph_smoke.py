from types import SimpleNamespace

import pandas as pd

from graph.analytics_graph import build_graph


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


class _StubDB:
    def run_query(self, _sql: str):
        return pd.DataFrame({"region": ["east", "west"], "revenue": [100, 200]})

    def list_tables(self):
        return [("sales",)]

    def describe_table(self, table_name: str):
        return pd.DataFrame({"column_name": ["region"], "column_type": ["VARCHAR"]})


def test_graph_runs_analysis_path(monkeypatch):
    # intent_router -> analysis path, analysis_agent -> SQL, reporting_agent -> summary
    monkeypatch.setattr("agents.intent_router.get_llm", lambda: _StubLLM("analysis"))
    monkeypatch.setattr("agents.analysis_agent.get_llm", lambda: _StubLLM("SELECT 1"))
    monkeypatch.setattr("agents.reporting_agent.get_llm", lambda: _StubLLM("summary"))

    # Avoid opening a GUI plot during tests
    monkeypatch.setattr("agents.visualization_agent.plot_bar", lambda *_args, **_kwargs: None)

    graph = build_graph()
    state = {"user_query": "total revenue by region", "db": _StubDB(), "metadata": {"tables": {}}}
    out = graph.invoke(state)

    assert out["intent"] == "analysis"
    assert out["sql_query"].strip() == "SELECT 1 LIMIT 500"
    assert out["report"] == "summary"

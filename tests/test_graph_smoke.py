from types import SimpleNamespace

import pandas as pd

from graph.analytics_graph import build_graph


class _StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(content=content)


class _StubDB:
    def run_query(self, _sql: str):
        return pd.DataFrame({"region": ["east", "west"], "revenue": [100, 200]})

    def list_tables(self):
        return [("sales",)]

    def describe_table(self, table_name: str):
        return pd.DataFrame({"column_name": ["region"], "column_type": ["VARCHAR"]})


def test_graph_runs_analysis_path(monkeypatch):
    # Avoid opening a GUI plot during tests
    monkeypatch.setattr("agents.visualization_agent.plot_bar", lambda *_args, **_kwargs: None)

    graph = build_graph()
    state = {
        "user_query": "total revenue by region",
        "db": _StubDB(),
        "metadata": {"tables": {}},
        "llm": _StubLLM(["analysis", "plan", "SELECT 1", "summary"]),
    }
    out = graph.invoke(state)

    assert out["intent"] == "analysis"
    assert out["sql_query"].strip() == "SELECT 1 LIMIT 500"
    assert out["report"] == "summary"

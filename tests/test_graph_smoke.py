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
    def __init__(self):
        self.queries = []

    def run_query(self, _sql: str):
        self.queries.append(_sql)
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
        "llm": _StubLLM(['{"intent": "analysis", "table_name": null}', "plan", "SELECT 1", "summary"]),
    }
    out = graph.invoke(state)

    assert out["intent"] == "analysis"
    assert out["sql_query"].strip() == "SELECT 1 LIMIT 500"
    assert out["report"] == "summary"


class _RepairDB(_StubDB):
    def run_query(self, sql: str):
        self.queries.append(sql)
        if "bad_column" in sql:
            raise RuntimeError("Binder Error: bad_column not found")
        return pd.DataFrame({"region": ["east"], "revenue": [100]})


def test_graph_repairs_failed_sql(monkeypatch):
    monkeypatch.setattr("agents.visualization_agent.plot_bar", lambda *_args, **_kwargs: None)
    db = _RepairDB()

    graph = build_graph()
    state = {
        "user_query": "total revenue by region",
        "db": db,
        "metadata": {"tables": {"sales": {"columns": {"region": "VARCHAR", "revenue": "BIGINT"}}}},
        "llm": _StubLLM(
            [
                '{"intent": "analysis", "table_name": null}',
                "plan",
                "SELECT bad_column FROM sales",
                "SELECT region, SUM(revenue) AS revenue FROM sales GROUP BY region",
                "summary",
            ]
        ),
        "sql_repair_attempts": 0,
        "max_sql_repair_attempts": 1,
    }

    out = graph.invoke(state)

    assert out["sql_error"] is None
    assert out["sql_repair_attempts"] == 1
    assert out["sql_query"] == "SELECT region, SUM(revenue) AS revenue FROM sales GROUP BY region LIMIT 500"
    assert db.queries == [
        "SELECT bad_column FROM sales LIMIT 500",
        "SELECT region, SUM(revenue) AS revenue FROM sales GROUP BY region LIMIT 500",
    ]
    assert out["report"] == "summary"

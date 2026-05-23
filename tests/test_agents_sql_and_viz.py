import pandas as pd

from agents.sql_agent import sql_agent
from agents.visualization_agent import visualization_agent


class _OkDB:
    def run_query(self, _sql: str):
        return pd.DataFrame({"x": [1], "y": [2]})


class _FailDB:
    def run_query(self, _sql: str):
        raise RuntimeError("boom")


def test_sql_agent_success_sets_result_and_clears_error():
    state = {"db": _OkDB(), "sql_query": "SELECT 1"}
    out = sql_agent(state)
    assert isinstance(out["result"], pd.DataFrame)
    assert out["sql_error"] is None


def test_sql_agent_failure_sets_error():
    state = {"db": _FailDB(), "sql_query": "SELECT 1"}
    out = sql_agent(state)
    assert out["result"] is None
    assert "boom" in out["sql_error"]


def test_sql_agent_missing_inputs_sets_error():
    out = sql_agent({})
    assert out["result"] is None
    assert "No database connection" in out["sql_error"]


def test_visualization_agent_schema_dataframe_prints(monkeypatch, capsys):
    # Avoid GUI plotting
    monkeypatch.setattr("agents.visualization_agent.plot_bar", lambda *_a, **_k: None)

    df = pd.DataFrame({"column_name": ["id"], "column_type": ["INTEGER"]})
    visualization_agent({"result": df})

    captured = capsys.readouterr().out
    assert "Table schema" in captured


def test_visualization_agent_list_tables_prints(capsys):
    visualization_agent({"result": [("t1",), ("t2",)]})
    captured = capsys.readouterr().out
    assert "Tables available" in captured
    assert "t1" in captured
    assert "t2" in captured


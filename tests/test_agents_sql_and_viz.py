import pandas as pd

from agents.sql_agent import sql_agent
from agents.visualization_agent import visualization_agent
from engine.runtime import AnalyticsRuntime


class _OkDB:
    def __init__(self):
        self.query = None

    def run_query(self, _sql: str):
        self.query = _sql
        return pd.DataFrame({"x": [1], "y": [2]})


class _FailDB:
    def run_query(self, _sql: str):
        raise RuntimeError("boom")


def test_sql_agent_success_sets_result_and_clears_error():
    db = _OkDB()
    state = {"db": db, "sql_query": "SELECT 1"}
    out = sql_agent(state)
    assert isinstance(out["result"], pd.DataFrame)
    assert out["sql_error"] is None
    assert out["sql_query"] == "SELECT 1 LIMIT 500"
    assert db.query == "SELECT 1 LIMIT 500"


def test_sql_agent_uses_runtime_db():
    db = _OkDB()
    state = {"runtime": AnalyticsRuntime(db=db), "sql_query": "SELECT 1"}

    out = sql_agent(state)

    assert isinstance(out["result"], pd.DataFrame)
    assert db.query == "SELECT 1 LIMIT 500"


def test_sql_agent_rejects_non_select_query():
    state = {"db": _OkDB(), "sql_query": "DROP TABLE sales"}
    out = sql_agent(state)
    assert out["result"] is None
    assert "Only SELECT queries" in out["sql_error"]


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


def test_visualization_agent_saves_chart_artifact(tmp_path):
    df = pd.DataFrame({"region": ["East", "West"], "revenue": [100, 200]})

    out = visualization_agent({"result": df, "artifact_dir": tmp_path})

    assert len(out["artifacts"]) == 1
    artifact = out["artifacts"][0]
    assert artifact.artifact_type == "chart"
    assert artifact.mime_type == "image/png"
    assert artifact.path.exists()


def test_visualization_agent_saves_chart_artifact_with_runtime(tmp_path):
    df = pd.DataFrame({"region": ["East", "West"], "revenue": [100, 200]})
    runtime = AnalyticsRuntime(artifact_dir=tmp_path)

    out = visualization_agent({"result": df, "runtime": runtime})

    assert out["artifacts"] is runtime.artifacts
    assert len(runtime.artifacts) == 1

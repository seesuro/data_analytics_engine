from pathlib import Path

from engine.analytics_engine import AnalyticsEngine


class _FakeGraph:
    def __init__(self):
        self.received_state = None

    def invoke(self, state):
        self.received_state = state
        return {**state, "report": "done"}


def test_analytics_engine_builds_initial_state():
    graph = _FakeGraph()
    engine = AnalyticsEngine(graph=graph)
    db = object()
    metadata = {"tables": {"sales": {"columns": {"region": "VARCHAR"}}}}

    out = engine.run("total revenue", db=db, metadata=metadata)

    assert graph.received_state["user_query"] == "total revenue"
    assert graph.received_state["runtime"].db is db
    assert graph.received_state["runtime"].metadata == metadata
    assert graph.received_state["artifacts"] == []
    assert "db" not in graph.received_state
    assert "metadata" not in graph.received_state
    assert "artifact_dir" not in graph.received_state
    assert out["report"] == "done"


def test_analytics_engine_accepts_artifact_dir(tmp_path):
    graph = _FakeGraph()
    engine = AnalyticsEngine(graph=graph)

    engine.run("total revenue", db=object(), metadata={}, artifact_dir=Path(tmp_path))

    assert graph.received_state["runtime"].artifact_dir == tmp_path


def test_analytics_engine_accepts_injected_llm():
    graph = _FakeGraph()
    engine = AnalyticsEngine(graph=graph)
    llm = object()

    engine.run("total revenue", db=object(), metadata={}, llm=llm)

    assert graph.received_state["runtime"].llm is llm


def test_analytics_engine_sets_sql_repair_defaults():
    graph = _FakeGraph()
    engine = AnalyticsEngine(graph=graph)

    engine.run("total revenue", db=object(), metadata={}, max_sql_repair_attempts=2)

    assert graph.received_state["sql_repair_attempts"] == 0
    assert graph.received_state["max_sql_repair_attempts"] == 2

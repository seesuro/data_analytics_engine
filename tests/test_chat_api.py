from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app import create_app
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_chat_api_runs_engine_and_persists_run(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    monkeypatch.setattr("agents.intent_router.get_llm", lambda: _StubLLM("analysis"))
    monkeypatch.setattr("agents.planner_agent.get_llm", lambda: _StubLLM("Aggregate revenue by region."))
    monkeypatch.setattr(
        "agents.analysis_agent.get_llm",
        lambda: _StubLLM("SELECT region, SUM(revenue) AS total_revenue FROM sales GROUP BY region ORDER BY region"),
    )
    monkeypatch.setattr("agents.reporting_agent.get_llm", lambda: _StubLLM("Done."))

    client = TestClient(create_app(store))
    response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "Revenue by region", "preview_limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "succeeded"
    assert body["run"]["sql_run"]["sql"].endswith("LIMIT 500")
    assert body["run"]["result_preview"]["columns"] == ["region", "total_revenue"]
    assert body["run"]["result_preview"]["row_count"] == 2
    assert body["run"]["result_preview"]["truncated"] is True
    assert body["run"]["report"] == "Done."
    assert body["events"][0]["event_type"] == "completed"

    db = DBManager(str(store.project_db_path(project)))
    try:
        runs = DuckDBRegistry(db).list_runs()
        assert len(runs) == 1
        assert runs.loc[0, "status"] == "succeeded"
    finally:
        db.close()


def test_chat_api_returns_404_for_missing_project(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.post(
        "/chat",
        json={"project_id": str(uuid4()), "message": "Revenue by region"},
    )

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]

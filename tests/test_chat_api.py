from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app import create_app
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


class _StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(content=content)


def test_chat_api_runs_engine_and_persists_run(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    llm = _StubLLM(
        [
            '{"intent": "analysis", "table_name": null}',
            "Aggregate revenue by region.",
            "SELECT region, SUM(revenue) AS total_revenue FROM sales GROUP BY region ORDER BY region",
            "Done.",
        ]
    )
    client = TestClient(create_app(store, llm=llm))
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
        registry = DuckDBRegistry(db)
        runs = registry.list_runs()
        events = registry.list_run_events()
        messages = registry.list_chat_messages()
        assert len(runs) == 1
        assert len(events) == 1
        assert events[0].message == "Run completed."
        assert runs.loc[0, "status"] == "succeeded"
        assert [message.role.value for message in messages] == ["user", "assistant"]
    finally:
        db.close()


def test_chat_api_runs_eda_tool_and_persists_messages(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    client = TestClient(create_app(store))
    response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "Show missing values in sales"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["tool_call"]["tool_name"] == "missing_summary"
    assert body["run"]["tool_result"]["result"]["table_name"] == "sales"
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"

    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        events = registry.list_run_events(body["run"]["run_id"])
        assert events[0].payload["tool_call"]["tool_name"] == "missing_summary"
        assert events[0].payload["result_summary"]["summary_type"] == "missing_values"
        assert events[0].payload["result_summary"]["missing_column_count"] == 0
        assert len(registry.list_chat_messages()) == 2
        assert registry.get_run(body["run"]["run_id"]).tool_call.tool_name == "missing_summary"
    finally:
        db.close()


def test_chat_api_runs_cleaning_command_and_persists_messages(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n1,East,100\n2,West,\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    client = TestClient(create_app(store))
    start_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "start cleaning sales"},
    )
    drop_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "drop duplicates by order_id"},
    )

    assert start_response.status_code == 200
    assert drop_response.status_code == 200
    assert start_response.json()["run"]["report"].startswith("Started a cleaning draft")
    assert "drop_duplicates" in drop_response.json()["messages"][1]["payload"]["cleaning"]["latest_action"]

    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        assert len(registry.list_cleaning_flows()) == 1
        assert len(registry.list_cleaning_actions()) == 2
        assert len(registry.list_chat_messages()) == 4
    finally:
        db.close()


def test_chat_api_routes_null_handling_questions_to_guidance(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,,\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    client = TestClient(create_app(store))
    response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "How should I handle nulls in sales?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["tool_call"] is None
    assert "Suggested next actions" in body["run"]["report"]
    assert "High missingness warning" in body["run"]["report"]
    assert "impute numeric revenue median" in body["run"]["report"]
    assert "start cleaning sales" in body["run"]["report"]
    assert body["messages"][1]["payload"]["cleaning"]["recommendations"][0]["risk_level"] == "high"


def test_chat_api_runs_eda_against_active_cleaning_draft(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)

    client = TestClient(create_app(store))
    start_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "start cleaning sales"},
    )
    impute_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "impute numeric revenue median"},
    )
    eda_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "Show missing values"},
    )

    assert start_response.status_code == 200
    assert impute_response.status_code == 200
    assert eda_response.status_code == 200
    result = eda_response.json()["run"]["tool_result"]["result"]
    assert result["table_name"].startswith("sales_draft_")
    assert next(column for column in result["columns"] if column["column"] == "revenue")["missing_count"] == 0


def test_chat_api_returns_404_for_missing_project(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.post(
        "/chat",
        json={"project_id": str(uuid4()), "message": "Revenue by region"},
    )

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]

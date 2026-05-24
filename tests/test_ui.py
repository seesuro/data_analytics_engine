from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import create_app
from ingestion.project_ingestion import ProjectIngestionService
from storage.project_store import ProjectStore


class _StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(content=content)


def test_ui_home_page_shows_create_project_form(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.get("/")

    assert response.status_code == 200
    assert "Create Project" in response.text
    assert "No projects yet" in response.text
    assert "hx-post=\"/ui/projects\"" in response.text
    assert 'src="/static/htmx-lite.js"' in response.text


def test_ui_create_project_returns_workspace(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.post("/ui/projects", data={"project_name": "Retail Demo", "project_slug": "retail-demo"})

    assert response.status_code == 201
    assert "Retail Demo" in response.text
    assert "Upload Dataset" in response.text
    assert "Ask a Question" in response.text
    assert 'hx-swap-oob="innerHTML"' in response.text


def test_ui_upload_dataset_refreshes_workspace_with_table(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    client = TestClient(create_app(store))

    response = client.post(
        f"/ui/projects/{project.project_slug}/datasets",
        files={"file": ("sales.csv", b"Order ID,Region,Revenue\n1,East,100\n2,West,200\n", "text/csv")},
    )

    assert response.status_code == 200
    assert "Uploaded sales.csv as table sales with 2 rows" in response.text
    assert "<td>sales</td>" in response.text
    assert "order_id" in response.text


def test_ui_chat_returns_run_card(tmp_path):
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
            "East generated 100 and West generated 200.",
        ]
    )
    client = TestClient(create_app(store, llm=llm))

    response = client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "Revenue by region"},
    )

    assert response.status_code == 200
    assert "Revenue by region" in response.text
    assert "East generated 100 and West generated 200." in response.text
    assert "SELECT region, SUM(revenue)" in response.text
    assert "<img src=" in response.text
    assert "Open workflow trace" in response.text


def test_ui_chat_returns_eda_tool_card(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)
    client = TestClient(create_app(store))

    response = client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "Show missing values in sales"},
    )

    assert response.status_code == 200
    assert "Tool:" in response.text
    assert "missing_summary" in response.text
    assert "missing_count" in response.text


def test_ui_chat_returns_null_handling_guidance(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,,\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)
    client = TestClient(create_app(store))

    response = client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "How should I handle nulls in sales?"},
    )

    assert response.status_code == 200
    assert "Suggested next actions" in response.text
    assert "High missingness warning" in response.text
    assert "impute numeric revenue median" in response.text
    assert "missing_summary" not in response.text
    assert "<ul>" in response.text


def test_ui_chat_returns_cleaning_command_card(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n1,East,100\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)
    client = TestClient(create_app(store))

    response = client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "start cleaning sales"},
    )

    assert response.status_code == 200
    assert "Started a cleaning draft" in response.text


def test_ui_workspace_shows_active_cleaning_draft(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n", encoding="utf-8")
    ProjectIngestionService(store).ingest_file(project.project_slug, source)
    client = TestClient(create_app(store))
    client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "start cleaning sales"},
    )
    client.post(
        f"/ui/projects/{project.project_slug}/chat",
        data={"message": "drop duplicates by order_id"},
    )

    response = client.get(f"/ui/projects/{project.project_slug}/workspace")

    assert response.status_code == 200
    assert "Active cleaning draft" in response.text
    assert "EDA checks without a table name will use this draft" in response.text
    assert "Cleaning Action History" in response.text
    assert "start_flow" in response.text
    assert "drop_duplicates" in response.text
    assert "Open workflow trace" in response.text
    assert "Chat Transcript" in response.text
    assert "You:" in response.text
    assert "Assistant:" in response.text

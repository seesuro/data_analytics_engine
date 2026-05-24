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


def _prepare_project_with_run(tmp_path):
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
    chat_response = client.post(
        "/chat",
        json={"project_id": str(project.project_id), "message": "Revenue by region"},
    )
    assert chat_response.status_code == 200
    return store, project, client, chat_response.json()["run"]


def test_runs_api_lists_and_fetches_runs(tmp_path):
    _store, project, client, run = _prepare_project_with_run(tmp_path)

    listed = client.get(f"/projects/{project.project_slug}/runs")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["run_id"] == run["run_id"]

    fetched = client.get(f"/projects/{project.project_slug}/runs/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["run_id"]
    assert fetched.json()["status"] == "succeeded"

    trace = client.get(f"/projects/{project.project_slug}/runs/{run['run_id']}/trace")
    assert trace.status_code == 200
    assert trace.json()["run"]["run_id"] == run["run_id"]
    assert trace.json()["events"][0]["event_type"] == "completed"
    assert trace.json()["events"][0]["message"] == "Run completed."

    messages = client.get(f"/projects/{project.project_slug}/messages")
    assert messages.status_code == 200
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]


def test_runs_api_serves_artifact(tmp_path):
    _store, project, client, run = _prepare_project_with_run(tmp_path)
    filename = run["artifacts"][0]["path"].split("\\")[-1].split("/")[-1]

    response = client.get(f"/projects/{project.project_slug}/artifacts/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content


def test_runs_api_returns_404_for_missing_run_and_artifact(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    client = TestClient(create_app(store))

    missing_run = client.get(f"/projects/{project.project_slug}/runs/missing")
    assert missing_run.status_code == 404

    missing_trace = client.get(f"/projects/{project.project_slug}/runs/missing/trace")
    assert missing_trace.status_code == 404

    missing_artifact = client.get(f"/projects/{project.project_slug}/artifacts/missing.png")
    assert missing_artifact.status_code == 404

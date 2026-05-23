from fastapi.testclient import TestClient

from app import create_app
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


def test_upload_dataset_ingests_csv_into_project(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_app(store))
    project = store.create_project("Retail Demo")

    response = client.post(
        f"/projects/{project.project_slug}/datasets",
        files={"file": ("sales.csv", b"Order ID,Region,Revenue\n1,East,100\n2,West,200\n", "text/csv")},
    )

    assert response.status_code == 201
    dataset = response.json()
    assert dataset["status"] == "ready"
    assert dataset["source_filename"] == "sales.csv"
    assert dataset["table_name"] == "sales"
    assert dataset["row_count"] == 2

    db = DBManager(str(store.project_db_path(project)))
    try:
        result = db.run_query("SELECT SUM(revenue) AS total_revenue FROM sales")
        assert result.loc[0, "total_revenue"] == 300
        assert DuckDBRegistry(db).metadata()["tables"]["sales"]["row_count"] == 2
    finally:
        db.close()


def test_upload_dataset_returns_404_for_missing_project(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.post(
        "/projects/missing/datasets",
        files={"file": ("sales.csv", b"a,b\n1,2\n", "text/csv")},
    )

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]


def test_upload_dataset_returns_failed_dataset_for_unsupported_file(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_app(store))
    project = store.create_project("Retail Demo")

    response = client.post(
        f"/projects/{project.project_id}/datasets",
        files={"file": ("notes.txt", b"not tabular", "text/plain")},
    )

    assert response.status_code == 201
    dataset = response.json()
    assert dataset["status"] == "failed"
    assert dataset["error"] == "Unsupported file"

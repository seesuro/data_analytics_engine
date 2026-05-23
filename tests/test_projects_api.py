from fastapi.testclient import TestClient

from app import create_app
from storage.project_store import ProjectStore


def test_projects_api_create_list_and_get(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    created = client.post(
        "/projects",
        json={"project_name": "Retail Demo", "project_slug": "retail-demo"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["project_slug"] == "retail-demo"
    assert body["project_name"] == "Retail Demo"
    assert body["project_id"]

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    by_slug = client.get("/projects/retail-demo")
    assert by_slug.status_code == 200
    assert by_slug.json()["project_id"] == body["project_id"]

    by_id = client.get(f"/projects/{body['project_id']}")
    assert by_id.status_code == 200
    assert by_id.json()["project_slug"] == "retail-demo"


def test_projects_api_rejects_duplicate_slug(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))
    payload = {"project_name": "Retail Demo", "project_slug": "retail-demo"}

    assert client.post("/projects", json=payload).status_code == 201
    duplicate = client.post("/projects", json=payload)

    assert duplicate.status_code == 400
    assert "Project slug already exists" in duplicate.json()["detail"]


def test_projects_api_returns_404_for_missing_project(tmp_path):
    client = TestClient(create_app(ProjectStore(tmp_path / "projects")))

    response = client.get("/projects/missing")

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]

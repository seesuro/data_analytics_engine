from pathlib import Path

import pytest

from storage.project_store import ProjectStore


def test_create_project_builds_uuid_folder_and_index(tmp_path):
    store = ProjectStore(tmp_path)

    project = store.create_project("Retail Demo")

    assert project.project_slug == "retail-demo"
    assert project.path == tmp_path / str(project.project_id)
    assert store.project_db_path(project) == project.path / "db.duckdb"
    assert store.raw_dir(project).is_dir()
    assert store.artifacts_dir(project).is_dir()
    assert (tmp_path / "index.json").exists()


def test_list_and_lookup_projects_by_slug_or_uuid(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create_project("Retail Demo")

    projects = store.list_projects()

    assert len(projects) == 1
    assert projects[0].project_id == project.project_id
    assert store.get_project("retail-demo").project_id == project.project_id
    assert store.get_project(project.project_id).project_slug == "retail-demo"
    assert store.get_project(str(project.project_id)).project_slug == "retail-demo"


def test_create_project_rejects_duplicate_slug(tmp_path):
    store = ProjectStore(tmp_path)
    store.create_project("Retail Demo")

    with pytest.raises(ValueError, match="Project slug already exists"):
        store.create_project("Retail Demo")


def test_create_project_accepts_explicit_slug(tmp_path):
    store = ProjectStore(tmp_path)

    project = store.create_project("Retail Demo", project_slug="sales-lab")

    assert project.project_slug == "sales-lab"
    assert store.get_project("sales-lab").project_name == "Retail Demo"


def test_get_project_raises_for_unknown_project(tmp_path):
    store = ProjectStore(tmp_path)

    with pytest.raises(KeyError, match="Project not found"):
        store.get_project("missing")


def test_slugify_rejects_empty_slug():
    with pytest.raises(ValueError, match="at least one letter or number"):
        ProjectStore.slugify("!!!")


def test_project_paths_are_paths_after_json_roundtrip(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create_project("Retail Demo")

    reloaded_store = ProjectStore(Path(tmp_path))
    reloaded_project = reloaded_store.get_project(project.project_slug)

    assert isinstance(reloaded_project.path, Path)
    assert reloaded_store.raw_dir(reloaded_project).is_dir()

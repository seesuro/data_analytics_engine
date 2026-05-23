import json
import re
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterator
from uuid import UUID, uuid4

from config.settings import PROJECTS_ROOT
from contracts import Project


class ProjectStore:
    _locks: dict[str, Lock] = {}

    def __init__(self, root: str | Path = PROJECTS_ROOT):
        self.root = Path(root)
        self.index_path = self.root / "index.json"

    def create_project(self, project_name: str, project_slug: str | None = None) -> Project:
        slug = project_slug or self.slugify(project_name)
        index = self._read_index()
        if slug in index["by_slug"]:
            raise ValueError(f"Project slug already exists: {slug}")

        project_id = uuid4()
        project = Project(
            project_id=project_id,
            project_slug=slug,
            project_name=project_name.strip(),
            path=self.root / str(project_id),
        )
        project.path.mkdir(parents=True, exist_ok=False)
        self.raw_dir(project).mkdir()
        self.artifacts_dir(project).mkdir()

        index["projects"].append(project.model_dump(mode="json"))
        index["by_slug"][project.project_slug] = str(project.project_id)
        self._write_index(index)
        return project

    def list_projects(self) -> list[Project]:
        index = self._read_index()
        return [Project.model_validate(project) for project in index["projects"]]

    def get_project(self, project_id_or_slug: str | UUID) -> Project:
        index = self._read_index()
        lookup = str(project_id_or_slug)
        project_id = index["by_slug"].get(lookup, lookup)

        for project in index["projects"]:
            if project["project_id"] == project_id:
                return Project.model_validate(project)

        raise KeyError(f"Project not found: {project_id_or_slug}")

    def project_db_path(self, project: Project) -> Path:
        return project.path / "db.duckdb"

    def raw_dir(self, project: Project) -> Path:
        return project.path / "raw"

    def artifacts_dir(self, project: Project) -> Path:
        return project.path / "artifacts"

    @contextmanager
    def write_lock(self, project: Project) -> Iterator[None]:
        lock_key = str(project.project_id)
        lock = self._locks.setdefault(lock_key, Lock())
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @staticmethod
    def slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        if not slug:
            raise ValueError("Project name must contain at least one letter or number.")
        return slug

    def _read_index(self) -> dict:
        if not self.index_path.exists():
            return {"projects": [], "by_slug": {}}
        with self.index_path.open("r", encoding="utf-8") as index_file:
            return json.load(index_file)

    def _write_index(self, index: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w", encoding="utf-8") as index_file:
            json.dump(index, index_file, indent=2)

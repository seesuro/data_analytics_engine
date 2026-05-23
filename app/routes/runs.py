from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import FileResponse

from contracts import Run
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


router = APIRouter(prefix="/projects/{project_id_or_slug}", tags=["runs"])


def get_project_store(request: Request) -> ProjectStore:
    return request.app.state.project_store


@router.get("/runs")
def list_runs(project_id_or_slug: Annotated[str, Path(min_length=1)], request: Request) -> list[dict]:
    store = get_project_store(request)
    try:
        project = store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db = DBManager(str(store.project_db_path(project)))
    try:
        return DuckDBRegistry(db).list_runs().to_dict(orient="records")
    finally:
        db.close()


@router.get("/runs/{run_id}", response_model=Run)
def get_run(
    project_id_or_slug: Annotated[str, Path(min_length=1)],
    run_id: Annotated[str, Path(min_length=1)],
    request: Request,
) -> Run:
    store = get_project_store(request)
    try:
        project = store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db = DBManager(str(store.project_db_path(project)))
    try:
        try:
            return DuckDBRegistry(db).get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("/artifacts/{filename}")
def get_artifact(
    project_id_or_slug: Annotated[str, Path(min_length=1)],
    filename: Annotated[str, Path(min_length=1)],
    request: Request,
) -> FileResponse:
    store = get_project_store(request)
    try:
        project = store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    artifact_path = (store.artifacts_dir(project) / filename).resolve()
    artifacts_dir = store.artifacts_dir(project).resolve()
    if artifacts_dir not in artifact_path.parents or not artifact_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    return FileResponse(artifact_path)

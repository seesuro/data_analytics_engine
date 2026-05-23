from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from contracts import Project
from storage.project_store import ProjectStore


class ProjectCreateRequest(BaseModel):
    project_name: str = Field(min_length=1)
    project_slug: str | None = None


router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_store(request: Request) -> ProjectStore:
    return request.app.state.project_store


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, request: Request) -> Project:
    store = get_project_store(request)
    try:
        return store.create_project(project_name=payload.project_name, project_slug=payload.project_slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[Project])
def list_projects(request: Request) -> list[Project]:
    return get_project_store(request).list_projects()


@router.get("/{project_id_or_slug}", response_model=Project)
def get_project(project_id_or_slug: Annotated[str, Path(min_length=1)], request: Request) -> Project:
    try:
        return get_project_store(request).get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

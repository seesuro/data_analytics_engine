import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Path as ApiPath, Request, UploadFile, status

from contracts import Dataset
from ingestion.project_ingestion import ProjectIngestionService
from storage.project_store import ProjectStore


router = APIRouter(prefix="/projects/{project_id_or_slug}/datasets", tags=["datasets"])


def get_project_store(request: Request) -> ProjectStore:
    return request.app.state.project_store


@router.post("", response_model=Dataset, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    project_id_or_slug: Annotated[str, ApiPath(min_length=1)],
    request: Request,
    file: Annotated[UploadFile, File()],
) -> Dataset:
    store = get_project_store(request)
    try:
        store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    with TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / file.filename
        with source_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        return ProjectIngestionService(store).ingest_file(project_id_or_slug, source_path)

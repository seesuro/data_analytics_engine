from fastapi import APIRouter, HTTPException, Request, status

from contracts import ChatRequest, ChatResponse
from engine.analytics_engine import AnalyticsEngine
from engine.run_mapper import state_to_chat_response
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


router = APIRouter(prefix="/chat", tags=["chat"])


def get_project_store(request: Request) -> ProjectStore:
    return request.app.state.project_store


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    store = get_project_store(request)
    try:
        project = store.get_project(payload.project_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        state = AnalyticsEngine().run(
            question=payload.message,
            db=db,
            metadata=registry.metadata(),
            artifact_dir=store.artifacts_dir(project),
        )
        response = state_to_chat_response(
            state=state,
            project_id=project.project_id,
            question=payload.message,
            preview_limit=payload.preview_limit,
        )
        registry.register_run(response.run)
        return response
    finally:
        db.close()

from fastapi import APIRouter, HTTPException, Request, status

from contracts import ChatMessage, ChatRequest, ChatResponse, ChatRole
from engine.cleaning_engine import CleaningEngine
from engine.eda_engine import EDAEngine
from engine.run_mapper import state_to_chat_response
from engine.sql_engine import SQLEngine
from engine.table_context import working_table_context
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
        metadata = registry.metadata()
        eda_metadata = working_table_context(db, registry, metadata).metadata
        cleaning_engine = CleaningEngine()
        eda_engine = EDAEngine()
        if cleaning_engine.can_handle(payload.message, metadata):
            response = cleaning_engine.run(
                message=payload.message,
                project_id=project.project_id,
                db=db,
                registry=registry,
                metadata=metadata,
            )
        elif eda_engine.can_handle(payload.message, eda_metadata):
            response = eda_engine.run(
                message=payload.message,
                project_id=project.project_id,
                db=db,
                metadata=eda_metadata,
                llm=request.app.state.llm,
            )
        else:
            state = SQLEngine().run(
                question=payload.message,
                db=db,
                metadata=metadata,
                artifact_dir=store.artifacts_dir(project),
                llm=request.app.state.llm,
            )
            response = state_to_chat_response(
                state=state,
                project_id=project.project_id,
                question=payload.message,
                preview_limit=payload.preview_limit,
            )
            response.messages.extend(
                [
                    ChatMessage(project_id=project.project_id, role=ChatRole.USER, content=payload.message, run_id=response.run.run_id),
                    ChatMessage(
                        project_id=project.project_id,
                        role=ChatRole.ASSISTANT,
                        content=response.run.report or response.run.error or "No response generated.",
                        run_id=response.run.run_id,
                    ),
                ]
            )
        registry.register_run(response.run)
        registry.register_chat_messages(response.messages)
        return response
    finally:
        db.close()

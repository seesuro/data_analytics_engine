from contracts import ChatMessage, ChatResponse, ChatRole, Project
from engine.cleaning_engine import CleaningEngine
from engine.eda_engine import EDAEngine
from engine.run_mapper import state_to_chat_response
from engine.sql_engine import SQLEngine
from engine.table_context import working_table_context
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


def run_project_chat(
    *,
    store: ProjectStore,
    project: Project,
    message: str,
    preview_limit: int,
    llm,
) -> ChatResponse:
    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        metadata = registry.metadata()
        eda_metadata = working_table_context(db, registry, metadata).metadata
        response = _run_engine(
            message=message,
            project=project,
            db=db,
            registry=registry,
            metadata=metadata,
            eda_metadata=eda_metadata,
            preview_limit=preview_limit,
            artifact_dir=store.artifacts_dir(project),
            llm=llm,
        )
        registry.register_run(response.run)
        registry.register_run_events(response.events)
        registry.register_chat_messages(response.messages)
        return response
    finally:
        db.close()


def _run_engine(
    *,
    message: str,
    project: Project,
    db,
    registry: DuckDBRegistry,
    metadata: dict,
    eda_metadata: dict,
    preview_limit: int,
    artifact_dir,
    llm,
) -> ChatResponse:
    cleaning_engine = CleaningEngine()
    if cleaning_engine.can_handle(message, metadata):
        return cleaning_engine.run(
            message=message,
            project_id=project.project_id,
            db=db,
            registry=registry,
            metadata=metadata,
        )

    eda_engine = EDAEngine()
    if eda_engine.can_handle(message, eda_metadata):
        return eda_engine.run(
            message=message,
            project_id=project.project_id,
            db=db,
            metadata=eda_metadata,
            llm=llm,
        )

    state = SQLEngine().run(
        question=message,
        db=db,
        metadata=metadata,
        artifact_dir=artifact_dir,
        llm=llm,
    )
    response = state_to_chat_response(
        state=state,
        project_id=project.project_id,
        question=message,
        preview_limit=preview_limit,
    )
    response.messages.extend(
        [
            ChatMessage(project_id=project.project_id, role=ChatRole.USER, content=message, run_id=response.run.run_id),
            ChatMessage(
                project_id=project.project_id,
                role=ChatRole.ASSISTANT,
                content=response.run.report or response.run.error or "No response generated.",
                run_id=response.run.run_id,
            ),
        ]
    )
    return response

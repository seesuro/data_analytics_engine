from fastapi import APIRouter, HTTPException, Request, status

from contracts import ChatRequest, ChatResponse
from engine.chat_service import run_project_chat
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

    return run_project_chat(
        store=store,
        project=project,
        message=payload.message,
        preview_limit=payload.preview_limit,
        llm=request.app.state.llm,
    )

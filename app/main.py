from fastapi import FastAPI

from app.routes.chat import router as chat_router
from app.routes.datasets import router as datasets_router
from app.routes.projects import router as projects_router
from storage.project_store import ProjectStore


def create_app(project_store: ProjectStore | None = None) -> FastAPI:
    app = FastAPI(title="Data Analytics Engine")
    app.state.project_store = project_store or ProjectStore()
    app.include_router(chat_router)
    app.include_router(projects_router)
    app.include_router(datasets_router)
    return app


app = create_app()

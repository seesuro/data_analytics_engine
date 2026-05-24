import html
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse

from engine.analytics_engine import AnalyticsEngine
from engine.eda_engine import EDAEngine
from engine.run_mapper import state_to_chat_response
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore
from contracts import ChatMessage, ChatRole


router = APIRouter(tags=["ui"])


def get_project_store(request: Request) -> ProjectStore:
    return request.app.state.project_store


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    store = get_project_store(request)
    projects = store.list_projects()
    selected_project = projects[0] if projects else None
    workspace = _render_workspace(request, selected_project.project_slug) if selected_project else _empty_workspace()
    return HTMLResponse(_page(projects=_project_list(projects), workspace=workspace))


@router.get("/ui/projects/{project_id_or_slug}/workspace", response_class=HTMLResponse)
def project_workspace(project_id_or_slug: str, request: Request) -> HTMLResponse:
    return HTMLResponse(_render_workspace(request, project_id_or_slug))


@router.post("/ui/projects", response_class=HTMLResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: Request,
    project_name: Annotated[str, Form()],
    project_slug: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    store = get_project_store(request)
    try:
        project = store.create_project(project_name=project_name, project_slug=project_slug or None)
    except ValueError as exc:
        return HTMLResponse(_notice(str(exc), kind="error"), status_code=status.HTTP_400_BAD_REQUEST)

    body = _render_workspace(request, project.project_slug) + _project_list_oob(store.list_projects())
    return HTMLResponse(body, status_code=status.HTTP_201_CREATED)


@router.post("/ui/projects/{project_id_or_slug}/datasets", response_class=HTMLResponse)
def upload_dataset(
    project_id_or_slug: str,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> HTMLResponse:
    store = get_project_store(request)
    try:
        store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    with TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / file.filename
        with source_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        dataset = ProjectIngestionService(store).ingest_file(project_id_or_slug, source_path)

    return HTMLResponse(_render_workspace(request, project_id_or_slug, _dataset_notice(dataset)))


@router.post("/ui/projects/{project_id_or_slug}/chat", response_class=HTMLResponse)
def chat_with_project(
    project_id_or_slug: str,
    request: Request,
    message: Annotated[str, Form()],
) -> HTMLResponse:
    store = get_project_store(request)
    try:
        project = store.get_project(project_id_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        metadata = registry.metadata()
        eda_engine = EDAEngine()
        if eda_engine.can_handle(message, metadata):
            response = eda_engine.run(
                message=message,
                project_id=project.project_id,
                db=db,
                metadata=metadata,
                llm=request.app.state.llm,
            )
        else:
            state = AnalyticsEngine().run(
                question=message,
                db=db,
                metadata=metadata,
                artifact_dir=store.artifacts_dir(project),
                llm=request.app.state.llm,
            )
            response = state_to_chat_response(
                state=state,
                project_id=project.project_id,
                question=message,
                preview_limit=25,
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
        registry.register_run(response.run)
        registry.register_chat_messages(response.messages)
    finally:
        db.close()

    return HTMLResponse(_run_card(project.project_slug, response.run))


def _page(projects: str, workspace: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Data Analytics Engine</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; background: #f6f7fb; color: #172033; }}
    main {{ display: grid; grid-template-columns: 320px 1fr; min-height: 100vh; }}
    aside {{ background: #101827; color: white; padding: 24px; }}
    section {{ padding: 32px; }}
    input, button {{ border-radius: 10px; border: 1px solid #d7dce8; padding: 10px 12px; font: inherit; }}
    input {{ width: 100%; box-sizing: border-box; margin: 6px 0 12px; }}
    button {{ background: #3157ff; border-color: #3157ff; color: white; cursor: pointer; }}
    .card {{ background: white; border: 1px solid #e4e8f2; border-radius: 18px; padding: 20px; margin-bottom: 16px; box-shadow: 0 12px 32px rgba(31, 42, 68, .08); }}
    .project {{ display: block; color: white; text-decoration: none; padding: 10px 12px; border-radius: 10px; margin: 4px 0; background: rgba(255,255,255,.08); }}
    .muted {{ color: #677084; }}
    .notice {{ padding: 12px 14px; border-radius: 12px; margin-bottom: 16px; background: #edf7ee; color: #1b6531; }}
    .notice.error {{ background: #fff0f0; color: #9d2424; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; border-bottom: 1px solid #edf0f6; padding: 8px; }}
    img {{ max-width: 100%; border-radius: 14px; border: 1px solid #e4e8f2; }}
  </style>
</head>
<body>
  <main>
    <aside>
      <h1>Analytics Engine</h1>
      <p class="muted">Single-machine agentic analytics workspace.</p>
      <div class="card">
        <h2>Create Project</h2>
        <form hx-post="/ui/projects" hx-target="#workspace" hx-swap="innerHTML">
          <label>Project name</label>
          <input name="project_name" required placeholder="Retail Demo">
          <label>Slug optional</label>
          <input name="project_slug" placeholder="retail-demo">
          <button type="submit">Create</button>
        </form>
      </div>
      <h2>Projects</h2>
      <div id="project-list">{projects}</div>
    </aside>
    <section id="workspace">{workspace}</section>
  </main>
</body>
</html>"""


def _project_list(projects) -> str:
    if not projects:
        return '<p class="muted">No projects yet. Create one to begin.</p>'
    return "".join(
        f'<a class="project" href="#" hx-get="/ui/projects/{_e(project.project_slug)}/workspace" '
        f'hx-target="#workspace" hx-swap="innerHTML">{_e(project.project_name)}</a>'
        for project in projects
    )


def _project_list_oob(projects) -> str:
    return f'<div id="project-list" hx-swap-oob="innerHTML">{_project_list(projects)}</div>'


def _empty_workspace() -> str:
    return """
<div class="card">
  <h2>Start with a project</h2>
  <p class="muted">Create a project, upload a CSV/XLSX file, then ask a question.</p>
</div>
"""


def _render_workspace(request: Request, project_id_or_slug: str, notice: str = "") -> str:
    store = get_project_store(request)
    project = store.get_project(project_id_or_slug)
    metadata, runs = _project_registry_snapshots(store, project)
    return f"""
{notice}
<div class="card">
  <h2>{_e(project.project_name)}</h2>
  <p class="muted">Project slug: <code>{_e(project.project_slug)}</code></p>
</div>
<div class="card">
  <h3>Upload Dataset</h3>
  <form hx-post="/ui/projects/{_e(project.project_slug)}/datasets" hx-target="#workspace" hx-swap="innerHTML" enctype="multipart/form-data">
    <input type="file" name="file" accept=".csv,.xlsx" required>
    <button type="submit">Upload</button>
  </form>
</div>
<div class="card">
  <h3>Available Tables</h3>
  {_tables(metadata)}
</div>
<div class="card">
  <h3>Ask a Question</h3>
  <form hx-post="/ui/projects/{_e(project.project_slug)}/chat" hx-target="#chat-results" hx-swap="afterbegin">
    <input name="message" required placeholder="What is total revenue by region?">
    <button type="submit">Run Analysis</button>
  </form>
</div>
<div id="chat-results">
  {_run_history(project.project_slug, runs)}
</div>
"""


def _project_registry_snapshots(store: ProjectStore, project):
    db_path = store.project_db_path(project)
    if not db_path.exists():
        return {"tables": {}}, []

    db = DBManager(str(db_path))
    try:
        registry = DuckDBRegistry(db)
        return registry.metadata(), registry.list_runs().to_dict(orient="records")
    finally:
        db.close()


def _tables(metadata: dict) -> str:
    tables = metadata.get("tables", {})
    if not tables:
        return '<p class="muted">No uploaded tables yet.</p>'

    rows = []
    for table_name, table in tables.items():
        columns = ", ".join(table.get("columns", {}).keys())
        rows.append(f"<tr><td>{_e(table_name)}</td><td>{_e(str(table.get('row_count', '')))}</td><td>{_e(columns)}</td></tr>")
    return f"<table><thead><tr><th>Table</th><th>Rows</th><th>Columns</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _run_history(project_slug: str, runs: list[dict]) -> str:
    if not runs:
        return '<div class="card"><p class="muted">No runs yet.</p></div>'
    return "".join(
        f'<div class="card"><h3>{_e(run["question"])}</h3>'
        f'<p class="muted">Status: {_e(run["status"])}</p>'
        f'{_tool_badge(run)}'
        f'<a href="/projects/{_e(project_slug)}/runs/{_e(run["run_id"])}">Open run JSON</a></div>'
        for run in reversed(runs[-5:])
    )


def _run_card(project_slug: str, run) -> str:
    preview = _preview_table(run.result_preview)
    artifacts = "".join(
        f'<img src="/projects/{_e(project_slug)}/artifacts/{_e(artifact.path.name)}" alt="{_e(artifact.artifact_type)}">'
        for artifact in run.artifacts
    )
    return f"""
<div class="card">
  <h3>{_e(run.question)}</h3>
  {_tool_badge(run.model_dump(mode="json"))}
  <p>{_e(run.report or run.error or "No report generated.")}</p>
  {_sql(run)}
  {_tool_result_table(run.tool_result)}
  {preview}
  {artifacts}
</div>
"""


def _preview_table(preview) -> str:
    if preview is None or not preview.rows:
        return ""
    headers = "".join(f"<th>{_e(column)}</th>" for column in preview.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_e(str(row.get(column, '')))}</td>" for column in preview.columns) + "</tr>"
        for row in preview.rows
    )
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"


def _sql(run) -> str:
    if not run.sql_run:
        return ""
    return f"<p class=\"muted\"><code>{_e(run.sql_run.sql)}</code></p>"


def _tool_badge(run: dict) -> str:
    tool_call = run.get("tool_call")
    if isinstance(tool_call, str):
        return ""
    if not tool_call:
        return ""
    return f'<p class="muted">Tool: <code>{_e(tool_call.get("tool_name", ""))}</code></p>'


def _tool_result_table(tool_result) -> str:
    if not tool_result:
        return ""
    result = tool_result.result
    if "columns" in result and isinstance(result["columns"], list):
        rows = result["columns"]
        if not rows:
            return '<p class="muted">Tool returned no column-level rows.</p>'
        keys = list(rows[0].keys())
        headers = "".join(f"<th>{_e(key)}</th>" for key in keys)
        body = "".join(
            "<tr>" + "".join(f"<td>{_e(row.get(key, ''))}</td>" for key in keys) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"
    if "correlations" in result:
        rows = result["correlations"]
        if not rows:
            return '<p class="muted">No correlations available.</p>'
        keys = ["left", "right", "correlation"]
        headers = "".join(f"<th>{_e(key)}</th>" for key in keys)
        body = "".join(
            "<tr>" + "".join(f"<td>{_e(row.get(key, ''))}</td>" for key in keys) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"
    return ""


def _dataset_notice(dataset) -> str:
    if dataset.error:
        return _notice(f"Upload finished with error: {dataset.error}", kind="error")
    return _notice(f"Uploaded {dataset.source_filename} as table {dataset.table_name} with {dataset.row_count} rows.")


def _notice(message: str, kind: str = "success") -> str:
    class_name = "notice error" if kind == "error" else "notice"
    return f'<div class="{class_name}">{_e(message)}</div>'


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)

# Data Analytics Engine

An LLM-driven analytics engine that ingests tabular data into DuckDB, builds metadata, and runs a LangGraph agent workflow to:

- Plan an analysis from a natural language question.
- Generate SQL using table and column metadata.
- Execute SQL against DuckDB.
- Visualize results and produce a natural language report.

## Current Architecture Direction

The project is moving toward a single-machine web application that can scale later through clear contracts and swappable adapters.

- Runtime: Python 3.13 via `uv`.
- Data engine: DuckDB, with one database per project.
- Project layout: `var/projects/<project_id>/db.duckdb`, `raw/`, and `artifacts/`.
- Identity model: UUIDs for stable internal IDs, plus human-readable project slugs and names.
- Contracts: Pydantic models in `contracts/` define project, dataset, run, chat, preview, and artifact shapes.
- Quality gate: `uv run pytest` runs tests with coverage and fails below 90%.

Runtime project data under `var/` is intentionally ignored by git.

## Project Structure

- `agents/`
  - `intent_router.py`: routes meta/schema questions or analytical questions.
  - `planner_agent.py`: turns a user query into an analysis plan.
  - `analysis_agent.py`: converts a plan and metadata into one SQL query.
  - `sql_agent.py`: executes SQL against DuckDB.
  - `visualization_agent.py`: produces a simple visualization from results.
  - `reporting_agent.py`: summarizes results with the configured LLM.
- `config/`
  - `settings.py`: local paths such as `DB_PATH`, `METADATA_PATH`, and `PROJECTS_ROOT`.
- `contracts/`
  - `models.py`: Pydantic contracts for projects, datasets, runs, chat responses, SQL runs, previews, and artifacts.
- `graph/`
  - `analytics_graph.py`: LangGraph workflow wiring.
- `ingestion/`
  - `data_ingestor.py`: loads CSV/XLSX files into DuckDB and builds metadata.
  - `project_ingestion.py`: saves raw files into a project folder and ingests them into that project's DuckDB database.
- `storage/`
  - `db_manager.py`: thin DuckDB wrapper for table creation and queries.
  - `project_store.py`: manages project creation, UUID/slug lookup, project directories, and per-project write locks.
- `tests/`
  - Unit and smoke tests run by `uv run pytest`.

## Project-Aware Storage

Projects are isolated on disk:

```text
var/
  projects/
    index.json
    <project_id>/
      db.duckdb
      raw/
      artifacts/
```

`ProjectStore` creates and looks up projects. `ProjectIngestionService` copies the uploaded source file into `raw/`, computes a content hash, and ingests the table into that project's `db.duckdb`.

## End-to-End Workflow

The current LangGraph flow is:

```text
intent_router -> (planner | viz)
planner -> analysis -> sql -> viz -> report
```

For analytical questions, the engine:

1. Plans the analysis.
2. Generates SQL from the plan and metadata.
3. Executes the SQL through `DBManager`.
4. Produces a visualization.
5. Produces a report.

For schema/meta questions, the router can call database methods directly and skip planning.

## Running Locally

Prerequisites:

- Python 3.13.
- `uv`.

Install dependencies:

```bash
uv sync
```

Run tests and coverage:

```bash
uv run pytest
```

The test suite fails if total coverage is below 90%.

## Legacy Examples

The examples under `examples/` still show the earlier direct-DuckDB flow. They will be updated as the project-aware ingestion and future FastAPI/HTMX interface are built out.

## Design Notes

- Keep FastAPI and UI code outside the engine.
- Keep agents testable with dependency injection.
- Keep storage behind small adapters, starting with DuckDB.
- Return previews and artifact references to the UI instead of full dataframes.

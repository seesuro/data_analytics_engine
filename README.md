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
- Intent routing uses a typed `IntentDecision` contract parsed from LLM JSON output.
- SQL generation and SQL repair use a typed `SqlCandidate` contract parsed from LLM JSON output, with raw-SQL fallback for older prompts/tests.
- Agent runtime dependencies are grouped in an `AnalyticsRuntime` object so the graph receives one explicit context for DB, metadata, LLM, and artifacts.
- Project chat messages are persisted in DuckDB, and EDA requests can use deterministic Python tools before LLM explanation.
- Cleaning flows are modeled as auditable draft workflows before cleaned tables are saved, with active draft action history visible in the workspace.
- While a cleaning draft is active, EDA checks without an explicit table name target the draft table by default.
- Local LLM default: `qwen2.5` through Ollama.
- Quality gate: `uv run pytest` runs tests with coverage and fails below 90%.

Runtime project data under `var/` is intentionally ignored by git.

## Project Structure

- `agents/`
  - `intent_router.py`: routes meta/schema questions or analytical questions.
  - `planner_agent.py`: turns a user query into an analysis plan.
  - `analysis_agent.py`: converts a plan and metadata into a typed SQL candidate.
  - `sql_agent.py`: executes SQL against DuckDB.
  - `visualization_agent.py`: produces a chart artifact from results when an artifact directory is provided.
  - `reporting_agent.py`: summarizes results with the configured LLM.
- `app/`
  - `routes/chat.py`: in-process chat/run endpoint backed by `SQLEngine` and `EDAEngine`.
  - `main.py`: FastAPI app factory.
  - `routes/datasets.py`: dataset upload endpoint backed by project-aware ingestion.
  - `routes/projects.py`: project create, list, and lookup endpoints.
  - `routes/runs.py`: run listing/detail endpoints and project artifact file serving.
  - `routes/ui.py`: minimal HTMX web interface for project creation, dataset upload, chat, results, artifacts, and run history.
- `config/`
  - `settings.py`: local paths such as `DB_PATH`, `METADATA_PATH`, and `PROJECTS_ROOT`.
- `contracts/`
  - `models.py`: Pydantic contracts for projects, datasets, runs, chat responses, SQL runs, previews, artifacts, cleaning flows, and cleaning actions.
- `engine/`
  - `cleaning_engine.py`: routes deterministic cleaning chat commands to draft-table workflow tools.
  - `sql_engine.py`: caller-facing wrapper around the SQL-backed LangGraph workflow.
  - `eda_engine.py`: routes EDA-style requests to deterministic tools and optional LLM explanation.
  - `run_mapper.py`: converts graph state into `ChatResponse` and run records.
  - `runtime.py`: runtime dependency context for DB, metadata, LLM, artifact directory, and created artifacts.
  - `sql_candidate.py`: parses structured or raw LLM SQL output into a `SqlCandidate`.
  - `sql_policy.py`: SQL guardrails for SELECT-only, single-statement queries with row-limit capping.
  - `table_context.py`: resolves the active working table so EDA can operate on cleaning drafts.
- `graph/`
  - `analytics_graph.py`: LangGraph workflow wiring.
- `ingestion/`
  - `data_ingestor.py`: loads CSV/XLSX files into DuckDB and builds metadata.
  - `project_ingestion.py`: saves raw files into a project folder and ingests them into that project's DuckDB database.
- `storage/`
  - `db_manager.py`: thin DuckDB wrapper for table creation and queries.
  - `duckdb_registry.py`: creates and writes project-local registry tables for datasets, tables, runs, chat messages, cleaning flows, and cleaning actions.
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

Each project DuckDB file also owns its registry state:

- `__datasets`: uploaded file metadata, content hashes, status, raw path, and ingestion errors.
- `__tables`: table name, schema JSON, row count, and source dataset.
- `__runs`: future analysis run records, SQL payloads, result previews, reports, and errors.
- `__run_events`: durable workflow events emitted by SQL, EDA, and cleaning runs.
- `__chat_messages`: persisted project chat turns tied to runs when available.
- `__cleaning_flows`: draft/committed/aborted cleaning workflow records.
- `__cleaning_actions`: ordered cleaning action audit records with arguments and before/after summaries.

`DuckDBRegistry.metadata()` reconstructs the schema metadata needed by the analysis agent from `__tables`.

## End-to-End Workflow

The current LangGraph flow is:

```text
intent_router -> (planner | viz)
planner -> analysis -> sql -> (sql_repair -> sql | viz) -> report
```

For analytical questions, the engine:

1. Plans the analysis.
2. Generates a typed SQL candidate from the plan and metadata.
3. Applies SQL policy checks before execution.
4. Executes the SQL through `DBManager`.
5. Repairs failed SQL once using the DuckDB error and schema metadata.
6. Produces a chart artifact when an artifact directory is available.
7. Produces a report.

For project-aware ingestion, metadata is written to DuckDB registry tables. The older `metadata.json` flow remains for legacy examples but should not be the long-term source of truth.

For schema/meta questions, the router can call database methods directly and skip planning.

`SQLEngine.run()` is the preferred code entry point for SQL-backed analytical questions. It accepts a user question, a database adapter, metadata, an optional artifact directory, and an optional injected LLM. These dependencies are packed into `AnalyticsRuntime`, then the graph returns the final state.

EDA-style requests such as missing-value checks, table profiles, numeric summaries, and correlations are routed through deterministic tools in `tools/eda_tools.py`. The tool computes the result, then the LLM can explain the output; this keeps computation grounded in Python/DuckDB instead of arbitrary generated code.

Cleaning is designed as a reviewable workflow: raw tables remain immutable, draft tables hold experiments, every action is logged, and a cleaned table is saved only when the user chooses to keep it.

When a draft cleaning flow is active, EDA requests such as `show missing values`, `profile table`, or `show correlations` default to the draft table. Users can still name a raw table explicitly when they want to inspect the original source.

The workspace shows the active draft and its cleaning action history, including action type, status, and arguments. Run cards and run history also link to the workflow trace endpoint. This is the first review checkpoint before richer approval flows are added.

Every chat execution also persists run events in `__run_events`. This creates a durable workflow trace separate from chat text, which will later support approvals, replay, and debugging.

The first cleaning-flow tools create and manage the draft lifecycle:

- `start_cleaning_flow`: copies a source table into a draft table and records the start action.
- `preview_cleaning_flow`: returns source/draft summaries plus action history.
- `drop_duplicate_rows`: removes duplicate records from the draft table and logs before/after row counts.
- `rename_column`: renames a column in the draft table and logs before/after schema summaries.
- `impute_numeric`: fills missing numeric values using `mean`, `median`, or `constant`.
- `impute_categorical`: fills missing categorical values using `mode` or `constant`.
- `save_cleaned_table`: copies the draft into the next cleaned table version and marks the flow committed.
- `discard_cleaning_flow`: marks the flow aborted and drops the draft table by default.

Cleaning commands are currently deterministic chat commands, for example:

- `How should I handle nulls in sales?`
- `start cleaning sales`
- `drop duplicates by order_id`
- `rename revenue to net_revenue`
- `impute numeric revenue median`
- `impute categorical region constant Unknown`
- `save cleaned table as sales_cleaned_review`
- `discard cleaning draft`

## Running Locally

Prerequisites:

- Python 3.13.
- `uv`.

Install dependencies:

```bash
uv sync
```

Run the API locally:

```bash
uv run uvicorn app.main:app --reload
```

Open the local web UI at:

```text
http://127.0.0.1:8000/
```

The default local LLM is `qwen2.5` because it is a good fit for instruction following and SQL generation among the currently available Ollama models on the development machine.

Current API endpoints:

- `GET /`
- `GET /ui/projects/{project_id_or_slug}/workspace`
- `POST /ui/projects`
- `POST /ui/projects/{project_id_or_slug}/datasets`
- `POST /ui/projects/{project_id_or_slug}/chat`
- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id_or_slug}`
- `POST /projects/{project_id_or_slug}/datasets`
- `POST /chat`
- `GET /projects/{project_id_or_slug}/messages`
- `GET /projects/{project_id_or_slug}/runs`
- `GET /projects/{project_id_or_slug}/runs/{run_id}`
- `GET /projects/{project_id_or_slug}/runs/{run_id}/trace`
- `GET /projects/{project_id_or_slug}/artifacts/{filename}`

Run tests and coverage:

```bash
uv run pytest
```

The test suite fails if total coverage is below 90%.

The golden-flow test covers the current core product path: create a project, ingest a CSV, read DuckDB registry metadata, run the analytics engine with stubbed LLM responses, execute SQL, save a chart artifact, and return a report.

## Examples

The examples under `examples/` use the current project-aware architecture:

```bash
uv run python examples/example_ingestion.py
uv run python examples/run_demo.py
```

`example_ingestion.py` creates a project, ingests `data/sales.csv`, and prints registry metadata. `run_demo.py` creates a project, ingests the same file, runs the analytics engine with a deterministic stub LLM, registers the run, and prints SQL, preview rows, report, and artifact paths.

Generated example projects are stored under `var/example_projects/`, which is ignored by git.

## Design Notes

- Keep FastAPI and UI code outside the engine.
- Keep agents testable with dependency injection.
- Keep runtime-only dependencies in `AnalyticsRuntime` instead of scattering DB, LLM, and artifact paths across graph state.
- Keep storage behind small adapters, starting with DuckDB.
- Keep generated SQL constrained to SELECT-only, single-statement queries.
- Prefer deterministic Python/DuckDB tools for EDA and cleaning operations; use the LLM for tool selection, explanation, and next-step suggestions.
- Return previews and artifact references to the UI instead of full dataframes.

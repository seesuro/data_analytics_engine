# Work Items

This file tracks the product build without timeboxed sprints. Keep items small enough that each completed item can be tested and committed cleanly.

## Epic A - Contracts

- [x] Define project, dataset, run, chat, result preview, and artifact contracts.
- [ ] Use contracts at engine and API boundaries.
- [x] Add tests for contract defaults, validation, and serialization.

## Epic B - Project Storage

- [x] Implement `ProjectStore` for create, list, and lookup by UUID or slug.
- [x] Use `var/projects/<project_id>/db.duckdb` for each project.
- [x] Prepare raw upload directory under `var/projects/<project_id>/raw/`.
- [x] Prepare artifacts directory under `var/projects/<project_id>/artifacts/`.
- [x] Save raw uploads under `var/projects/<project_id>/raw/`.
- [x] Add per-project write locking for ingestion.

## Epic C - DuckDB Registry

- [x] Create project-local registry tables: `__datasets`, `__tables`, and `__runs`.
- [x] Replace generated `metadata.json` with metadata read from DuckDB for project-aware ingestion.
- [x] Add tests for registry initialization and metadata reconstruction.

## Epic D - Engine Refactor

- [ ] Inject LLM, datastore, and artifact dependencies directly into agent nodes.
- [x] Add a caller-facing engine wrapper for injected DB, metadata, and artifact paths.
- [x] Make visualization create artifacts or chart specs instead of calling `plt.show()`.
- [x] Add SQL policy checks: SELECT-only, single statement, and row limits.
- [ ] Add deterministic golden-flow tests with a stub LLM and DuckDB fixture.

## Epic E - FastAPI Backend

- [ ] Add project create/list endpoints.
- [ ] Add dataset upload endpoint.
- [ ] Add chat/run endpoint using the in-process engine.
- [ ] Add run result and artifact fetch endpoints.

## Epic F - HTMX UI

- [ ] Add project picker and project creation view.
- [ ] Add upload form.
- [ ] Add chat and run result view.
- [ ] Add basic run history.

## Epic G - Quality Gates

- [x] Configure `uv run pytest` with coverage reporting.
- [x] Fail tests when total coverage is below 90%.
- [ ] Add end-to-end golden tests for upload to answer flow.

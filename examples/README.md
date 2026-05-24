# Examples

These examples use the current project-aware architecture:

- `ProjectStore` creates an isolated project under `var/example_projects/`.
- `ProjectIngestionService` copies the raw file into the project and loads it into that project's DuckDB database.
- `DuckDBRegistry` stores dataset/table/run metadata inside the project database.
- `AnalyticsEngine` runs the LangGraph workflow with injected DB, metadata, artifact directory, and LLM.

Run from the repository root:

```bash
uv run python examples/example_ingestion.py
uv run python examples/run_demo.py
```

`run_demo.py` uses a deterministic stub LLM so it does not require Ollama or an external API key.

# Data Analytics Engine

An LLM‑driven analytics engine that ingests tabular data into DuckDB, builds metadata, and runs a LangGraph agent workflow to:

- Plan an analysis from a natural language question
- Generate deterministic SQL using table/column metadata
- Execute SQL against DuckDB
- Visualize results and produce a natural language report

---


## Project Structure

- `agents/`
	- `intent_router.py` – routes the user query: if it's a meta/schema question (e.g., "list tables", "describe table X"), calls the appropriate `DBManager` method and routes directly to visualization/reporting; otherwise, routes to the planner for LLM-driven analysis.
	- `planner_agent.py` – turns a `user_query` into a step‑by‑step analysis plan using the configured LLM.
	- `analysis_agent.py` – converts the plan and metadata into a **single deterministic SQL query** (no execution here).
	- `sql_agent.py` – executes `state["sql_query"]` against DuckDB via `DBManager` and stores the DataFrame in `state["result"]`.
	- `visualization_agent.py` – takes `state["result"]` and plots a simple bar chart via `tools.plotting_tools.plot_bar`.
	- `reporting_agent.py` – summarizes the tabular result into a natural language report with the LLM.

- `config/`
	- `settings.py` – paths for the DuckDB file (`DB_PATH`) and metadata JSON (`METADATA_PATH`).

- `examples/`
	- `run_demo.py` – minimal end‑to‑end demo wiring `DBManager`, `DataIngestor`, and the analytics graph.
	- `example_ingestion.py` – example that ingests a CSV, persists metadata, builds the graph, and runs a single question.

- `graph/`
	- `analytics_graph.py` – defines the `StateGraph` wiring: `planner -> analysis -> sql -> viz -> report` on top of `AnalyticsState`.

- `ingestion/`
	- `data_ingestor.py` – loads CSV/Excel files into DuckDB, normalizes column names, infers dtypes, and builds table metadata via `MetadataManager` (columns, primary key guess, row count). Metadata is written to `METADATA_PATH`.

- `llm/`
	- `llm_factory.py` – factory for initializing the chat model (OpenAI, Ollama, or local) via LangChain’s `init_chat_model`.

- `state/`
	- `analytics_state.py` – `TypedDict` defining the shared graph state: `user_query`, `plan`, `sql_query`, `result`, plus injected `db` and `metadata`.

- `storage/`
	- `db_manager.py` – thin DuckDB wrapper for creating tables from pandas DataFrames and running SQL queries.

- `tools/`
	- `pandas_tools.py` – helper utilities around pandas (if needed by agents/tools).
	- `plotting_tools.py` – simple Matplotlib‑based plotting helpers.

---

## End‑to‑End Workflow

### 1. Data ingestion & metadata

1. A DuckDB database is opened via `DBManager(DB_PATH)`.
2. `DataIngestor` reads one or more files (CSV/Excel), normalizes column names, converts dtypes, and writes them as DuckDB tables.
3. While ingesting, `MetadataManager` registers each table:
	 - Column names and dtypes
	 - A best‑effort primary key
	 - Row counts
4. Metadata is persisted to `METADATA_PATH` (JSON). This metadata is later injected into the LLM prompt for deterministic SQL generation.

### 2. State & graph initialization

The analytics graph operates on `AnalyticsState`, which carries:

- `user_query`: Natural language question (e.g., "What is the total revenue by region?").
- `plan`: LLM‑generated analysis plan.
- `sql_query`: SQL text produced by the analysis agent.
- `result`: pandas DataFrame with query results (set by the SQL agent).
- `db`: The active `DBManager` instance (dependency‑injected).
- `metadata`: The loaded metadata dictionary from ingestion.


The graph defined in `graph/analytics_graph.py` is:

```text
intent_router -> (planner | viz)
planner -> analysis -> sql -> viz -> report
```

The `intent_router` inspects the user query and:
- If the query is for schema/meta info (like "list tables" or "describe table X"), it calls the appropriate `DBManager` method and routes directly to visualization/reporting.
- For all other queries, it routes to the planner and the normal LLM-driven workflow.


### 3. Agent responsibilities

1. **Intent router** (`intent_router`)
	- Input: `state["user_query"]`.
	- Behavior: Detects if the query is a schema/meta request (e.g., "list tables", "describe table X").
	- If meta: Calls the appropriate `DBManager` method, sets `state["result"]`, and routes directly to visualization/reporting.
	- If not meta: Sets `state["intent"] = "analysis"` and routes to the planner.

2. **Planner agent** (`planner_agent`)
	- Input: `state["user_query"]`.
	- Behavior: Asks the LLM to create a step‑by‑step analysis plan.
	- Output: Writes the plan into `state["plan"]`.

3. **Analysis agent** (`analysis_agent`)
	- Input: `state["plan"]` + `state["metadata"]`.
	- Prompt:
	  - Provides metadata (tables/columns) to the LLM.
	  - Instructs the model to output **only a single SQL query**, with no explanations or markdown.
	- Post‑processing:
	  - Strips any stray markdown code fences from the response.
	- Output: Stores the final SQL string in `state["sql_query"]`. **Does not execute SQL**.

4. **SQL agent** (`sql_agent`)
	- Input: `state["sql_query"]` + `state["db"]`.
	- Behavior: Executes the SQL against DuckDB via `DBManager.run_query`.
	- Output:
	  - On success: `state["result"] = DataFrame`, `state["sql_error"] = None`.
	  - On failure: `state["result"] = None`, `state["sql_error"] = error message`.

5. **Visualization agent** (`visualization_agent`)
	- Input: `state["result"]`.
	- Behavior: If a result DataFrame with at least two columns exists, creates a simple bar chart using the first two columns.

6. **Reporting agent** (`reporting_agent`)
	- Input: `state["result"]`.
	- Behavior: Converts the DataFrame (if present) into a markdown table string and asks the LLM to summarize it.
	- Output: Writes the textual summary to `state["report"]`.

---

## Running the Examples

### Prerequisites

1. **Python**: 3.14+.
2. **Virtual environment** (recommended):
	 - `python -m venv venv`
	 - `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix).
3. **Dependencies** via [uv](https://github.com/astral-sh/uv) or pip:
	 - `uv sync --active`  
		 or
	 - `pip install .`

### 1. End‑to‑end demo

From the project root:

```bash
python -m examples.run_demo
```

This will:

- Open the DuckDB database from `DB_PATH`.
- Ingest `data/sample.csv` via `DataIngestor`.
- Build the analytics graph.
- Run the default `user_query` through all agents.
- Print the final state, including any generated report.

### 2. Ingestion + question example

`examples/example_ingestion.py` shows a more explicit flow:

1. Create `DBManager("data/analytics.db")`.
2. Ingest `data/sales.csv` and save metadata.
3. Load metadata JSON from `METADATA_PATH`.
4. Build the graph with `build_graph()`.
5. Provide an initial state:

	 ```python
	 initial_state = {
			 "user_query": "What is the total revenue by region?",
			 "db": db_manager,
			 "metadata": metadata,
	 }
	 ```

6. Invoke the graph and inspect the final state:

	 ```python
	 result = graph.invoke(initial_state)
	 print(result)
	 ```

---


## Design Highlights

- **Intent-based routing**: The `intent_router` agent enables fast, deterministic answers for schema/meta queries (like listing tables or describing a table) by calling `DBManager` methods directly, while routing analytical/natural language questions through the LLM-driven pipeline.
- **Dependency injection via state**: The DuckDB connection (`db`) and schema metadata (`metadata`) are passed through `AnalyticsState`, keeping agents stateless and easy to test.
- **Separation of concerns**:
  - `analysis_agent` focuses solely on SQL generation.
  - `sql_agent` owns SQL execution and error handling.
  - Visualization and reporting are isolated into their own agents.
- **Deterministic SQL**:
  - Prompts enforce SQL‑only responses.
  - Metadata grounds the LLM in the actual schema, improving correctness.

---

## Notes

- See `pyproject.toml` for project metadata and dependencies.
- All core logic is organized by function (agents, ingestion, storage, etc.).
- Example data files should be placed under `data/` (e.g., `data/sample.csv`, `data/sales.csv`).
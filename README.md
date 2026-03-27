# Data Analytics Engine

## Project Structure

- agents/: Modular agent implementations (planner, analysis, visualization, reporting)
- config/: Configuration files (e.g., settings.py)
- examples/: Example scripts and demo runners
- graph/: Analytics graph construction and logic
- ingestion/: Data ingestion logic (e.g., DataIngestor)
- llm/: LLM factory and related logic
- state/: State management (e.g., AnalyticsState)
- storage/: Database management (e.g., DBManager)
- tools/: Utility modules (pandas_tools, plotting_tools)
- pyproject.toml: Project metadata and dependencies
- uv.lock: Locked dependency versions
- .gitignore: Git ignore rules

## Getting Started

1. Create and activate a Python 3.14+ virtual environment (venv or conda).
2. Install dependencies using [uv](https://github.com/astral-sh/uv) or pip:
	- `uv sync --active` (recommended)
	- or `pip install .`
3. Run the example demo:
	- `python -m examples.run_demo`

## Notes
- See pyproject.toml for project metadata and dependencies.
- All core logic is organized by function (agents, ingestion, storage, etc.).
- Example data and notebooks are not included by default.
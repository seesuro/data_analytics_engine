import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.run_mapper import state_to_chat_response
from engine.sql_engine import SQLEngine
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


class StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(content=content)


def main() -> None:
    store = ProjectStore(ROOT / "var" / "example_projects")
    project = store.create_project(
        project_name="Example Analytics Demo",
        project_slug=f"example-analytics-{uuid4().hex[:8]}",
    )
    ProjectIngestionService(store).ingest_file(project.project_slug, ROOT / "data" / "sales.csv")

    db = DBManager(str(store.project_db_path(project)))
    try:
        registry = DuckDBRegistry(db)
        question = "What is total revenue by region?"
        llm = StubLLM(
            [
                '{"intent": "analysis", "table_name": null}',
                "Aggregate total revenue by region from the sales table.",
                '{"sql": "SELECT region, SUM(revenue) AS total_revenue FROM sales GROUP BY region ORDER BY region", "rationale": "Revenue is grouped by region."}',
                "West has the highest revenue with 67,000, followed by East with 28,000, North with 27,000, and South with 5,500.",
            ]
        )

        state = SQLEngine().run(
            question=question,
            db=db,
            metadata=registry.metadata(),
            artifact_dir=store.artifacts_dir(project),
            llm=llm,
        )
        response = state_to_chat_response(
            state=state,
            project_id=project.project_id,
            question=question,
            preview_limit=10,
        )
        registry.register_run(response.run)
    finally:
        db.close()

    print("PROJECT")
    print(f"  slug: {project.project_slug}")
    print(f"  path: {project.path}")
    print()
    print("QUESTION")
    print(f"  {question}")
    print()
    print("SQL")
    print(f"  {response.run.sql_run.sql if response.run.sql_run else 'No SQL generated.'}")
    print()
    print("RESULT PREVIEW")
    for row in response.run.result_preview.rows if response.run.result_preview else []:
        print(f"  {row}")
    print()
    print("REPORT")
    print(f"  {response.run.report}")
    print()
    print("ARTIFACTS")
    for artifact in response.run.artifacts:
        print(f"  {artifact.path}")


if __name__ == "__main__":
    main()

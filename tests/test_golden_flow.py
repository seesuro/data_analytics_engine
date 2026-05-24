from types import SimpleNamespace

from engine.sql_engine import SQLEngine
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


class _StubLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0

    def invoke(self, _prompt: str):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(content=content)


def test_golden_upload_to_answer_flow(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")

    source = tmp_path / "sales.csv"
    source.write_text(
        "Order ID,Region,Revenue\n"
        "1,East,100\n"
        "2,West,200\n"
        "3,East,150\n",
        encoding="utf-8",
    )

    dataset = ProjectIngestionService(store).ingest_file(project.project_slug, source)
    assert dataset.table_name == "sales"

    db = DBManager(str(store.project_db_path(project)))
    try:
        metadata = DuckDBRegistry(db).metadata()

        llm = _StubLLM(
            [
                '{"intent": "analysis", "table_name": null}',
                "Aggregate revenue by region.",
                "SELECT region, SUM(revenue) AS total_revenue "
                "FROM sales GROUP BY region ORDER BY region",
                "East generated 250 and West generated 200.",
            ]
        )

        out = SQLEngine().run(
            "What is total revenue by region?",
            db=db,
            metadata=metadata,
            artifact_dir=store.artifacts_dir(project),
            llm=llm,
        )

        assert out["intent"] == "analysis"
        assert out["sql_error"] is None
        assert out["sql_query"].endswith("LIMIT 500")
        assert out["result"].to_dict(orient="records") == [
            {"region": "East", "total_revenue": 250.0},
            {"region": "West", "total_revenue": 200.0},
        ]
        assert out["report"] == "East generated 250 and West generated 200."
        assert len(out["artifacts"]) == 1
        assert out["artifacts"][0].path.exists()
    finally:
        db.close()

import pandas as pd

from engine.table_context import active_cleaning_flow, working_table_context
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from tools.cleaning_flow_tools import discard_cleaning_flow, start_cleaning_flow


def test_working_table_context_prefers_active_draft(tmp_path):
    db = DBManager(str(tmp_path / "context.duckdb"))
    try:
        db.create_table("sales", pd.DataFrame({"order_id": [1, 2], "revenue": [100.0, None]}))
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        dataset = __import__("contracts").Dataset(
            project_id=project_id,
            source_filename="sales.csv",
            content_hash="hash",
            raw_path=tmp_path / "sales.csv",
            status=__import__("contracts").DatasetStatus.READY,
            table_name="sales",
            row_count=2,
        )
        registry.register_dataset(dataset)

        flow = start_cleaning_flow(db, registry, project_id, "sales")
        context = working_table_context(db, registry, registry.metadata())

        assert active_cleaning_flow(registry).flow_id == flow.flow_id
        assert next(iter(context.metadata["tables"])) == flow.draft_table
        assert context.metadata["tables"][flow.draft_table]["working_table"] is True
        assert context.metadata["tables"][flow.draft_table]["source_table"] == "sales"
        assert context.metadata["tables"][flow.draft_table]["row_count"] == 2
        assert "sales" in context.metadata["tables"]
    finally:
        db.close()


def test_working_table_context_returns_raw_metadata_without_draft(tmp_path):
    db = DBManager(str(tmp_path / "context.duckdb"))
    try:
        db.create_table("sales", pd.DataFrame({"order_id": [1], "revenue": [100]}))
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        dataset = __import__("contracts").Dataset(
            project_id=project_id,
            source_filename="sales.csv",
            content_hash="hash",
            raw_path=tmp_path / "sales.csv",
            status=__import__("contracts").DatasetStatus.READY,
            table_name="sales",
            row_count=1,
        )
        registry.register_dataset(dataset)
        flow = start_cleaning_flow(db, registry, project_id, "sales")
        discard_cleaning_flow(db, registry, flow.flow_id)
        metadata = registry.metadata()

        context = working_table_context(db, registry, metadata)

        assert context.active_flow is None
        assert context.metadata == metadata
    finally:
        db.close()

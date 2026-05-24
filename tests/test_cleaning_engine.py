from uuid import uuid4

import pandas as pd

from engine.cleaning_engine import CleaningEngine
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry


def _db_with_sales(tmp_path):
    db = DBManager(str(tmp_path / "cleaning_engine.duckdb"))
    db.create_table(
        "sales",
        pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3],
                "region": ["East", "East", "West", None],
                "revenue": [100.0, 100.0, None, 300.0],
            }
        ),
    )
    metadata = {
        "tables": {
            "sales": {
                "columns": {"order_id": "BIGINT", "region": "VARCHAR", "revenue": "DOUBLE"},
                "row_count": 4,
            }
        }
    }
    return db, metadata


def test_cleaning_engine_starts_and_mutates_active_draft(tmp_path):
    db, metadata = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = uuid4()
        engine = CleaningEngine()

        started = engine.run("start cleaning sales", project_id, db, registry, metadata)
        deduped = engine.run("drop duplicates by order_id", project_id, db, registry, metadata)
        imputed = engine.run("impute numeric revenue median", project_id, db, registry, metadata)

        flow = registry.list_cleaning_flows()[0]
        actions = registry.list_cleaning_actions(flow.flow_id)
        draft_count = db.run_query(f'SELECT COUNT(*) AS row_count FROM "{flow.draft_table}"').loc[0, "row_count"]
        draft_missing = db.run_query(
            f'SELECT SUM(CASE WHEN "revenue" IS NULL THEN 1 ELSE 0 END) AS missing_count FROM "{flow.draft_table}"'
        ).loc[0, "missing_count"]

        assert started.run.status == "succeeded"
        assert deduped.run.status == "succeeded"
        assert imputed.run.status == "succeeded"
        assert draft_count == 3
        assert draft_missing == 0
        assert [action.action_type.value for action in actions] == ["start_flow", "drop_duplicates", "impute_numeric"]
    finally:
        db.close()


def test_cleaning_engine_saves_and_discards_with_reports(tmp_path):
    db, metadata = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = uuid4()
        engine = CleaningEngine()

        engine.run("start cleaning sales", project_id, db, registry, metadata)
        saved = engine.run("save cleaned table as sales_cleaned_review", project_id, db, registry, metadata)

        assert saved.run.status == "succeeded"
        assert saved.run.report == "Saved cleaned table as sales_cleaned_review."
        assert "sales_cleaned_review" in {row[0] for row in db.list_tables()}
    finally:
        db.close()


def test_cleaning_engine_returns_failed_run_without_active_draft(tmp_path):
    db, metadata = _db_with_sales(tmp_path)
    try:
        response = CleaningEngine().run("drop duplicates by order_id", uuid4(), db, DuckDBRegistry(db), metadata)

        assert response.run.status == "failed"
        assert "No active draft cleaning flow" in response.run.error
        assert response.messages[1].role == "assistant"
    finally:
        db.close()

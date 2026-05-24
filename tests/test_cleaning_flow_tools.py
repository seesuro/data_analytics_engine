import pandas as pd
import pytest

from contracts import CleaningActionType, CleaningFlowStatus
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from tools.cleaning_flow_tools import (
    discard_cleaning_flow,
    preview_cleaning_flow,
    save_cleaned_table,
    start_cleaning_flow,
)


def _db_with_sales(tmp_path):
    db = DBManager(str(tmp_path / "cleaning.duckdb"))
    db.create_table("sales", pd.DataFrame({"order_id": [1, 2], "revenue": [100, 200]}))
    return db


def test_start_cleaning_flow_creates_draft_and_audit_action(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()

        flow = start_cleaning_flow(db, registry, project_id, "sales")
        preview = preview_cleaning_flow(db, registry, flow.flow_id)

        assert flow.status == CleaningFlowStatus.DRAFT
        assert flow.draft_table.startswith("sales_draft_")
        assert flow.draft_table in {row[0] for row in db.list_tables()}
        assert preview["source_summary"]["row_count"] == 2
        assert preview["draft_summary"]["row_count"] == 2
        assert preview["actions"][0]["action_type"] == CleaningActionType.START_FLOW.value
    finally:
        db.close()


def test_save_cleaned_table_commits_flow_and_keeps_draft(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        committed = save_cleaned_table(db, registry, flow.flow_id)
        actions = registry.list_cleaning_actions(flow.flow_id)

        assert committed.status == CleaningFlowStatus.COMMITTED
        assert committed.output_table == "sales_cleaned_v1"
        assert committed.output_table in {row[0] for row in db.list_tables()}
        assert actions[-1].action_type == CleaningActionType.SAVE_CLEANED_TABLE
        assert actions[-1].after_summary["row_count"] == 2
    finally:
        db.close()


def test_save_cleaned_table_uses_next_version(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        db.conn.execute('CREATE TABLE "sales_cleaned_v1" AS SELECT * FROM "sales"')
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        committed = save_cleaned_table(db, registry, flow.flow_id)

        assert committed.output_table == "sales_cleaned_v2"
    finally:
        db.close()


def test_discard_cleaning_flow_aborts_and_drops_draft(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        aborted = discard_cleaning_flow(db, registry, flow.flow_id)
        actions = registry.list_cleaning_actions(flow.flow_id)

        assert aborted.status == CleaningFlowStatus.ABORTED
        assert flow.draft_table not in {row[0] for row in db.list_tables()}
        assert actions[-1].action_type == CleaningActionType.DISCARD_DRAFT
        assert actions[-1].after_summary == {"draft_table_exists": False}
    finally:
        db.close()


def test_cleaning_flow_tools_reject_invalid_state_and_tables(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()

        with pytest.raises(ValueError, match="Table not found"):
            start_cleaning_flow(db, registry, project_id, "missing")

        flow = start_cleaning_flow(db, registry, project_id, "sales")
        discard_cleaning_flow(db, registry, flow.flow_id)

        with pytest.raises(ValueError, match="not draft"):
            save_cleaned_table(db, registry, flow.flow_id)
    finally:
        db.close()

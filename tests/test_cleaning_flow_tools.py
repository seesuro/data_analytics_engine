import pandas as pd
import pytest

from contracts import CleaningActionType, CleaningFlowStatus
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from tools.cleaning_flow_tools import (
    discard_cleaning_flow,
    drop_duplicate_rows,
    impute_categorical,
    impute_numeric,
    preview_cleaning_flow,
    rename_column,
    save_cleaned_table,
    start_cleaning_flow,
)


def _db_with_sales(tmp_path):
    db = DBManager(str(tmp_path / "cleaning.duckdb"))
    db.create_table("sales", pd.DataFrame({"order_id": [1, 1, 2], "revenue": [100, 100, 200]}))
    return db


def _db_with_missing_values(tmp_path):
    db = DBManager(str(tmp_path / "missing.duckdb"))
    db.create_table(
        "sales",
        pd.DataFrame(
            {
                "order_id": [1, 2, 3, 4],
                "region": ["East", "East", "West", None],
                "revenue": [100.0, None, 300.0, None],
            }
        ),
    )
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
        assert preview["source_summary"]["row_count"] == 3
        assert preview["draft_summary"]["row_count"] == 3
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
        assert actions[-1].after_summary["row_count"] == 3
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


def test_drop_duplicate_rows_mutates_draft_and_logs_action(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        updated = drop_duplicate_rows(db, registry, flow.flow_id, subset=["order_id"])
        actions = registry.list_cleaning_actions(flow.flow_id)

        assert updated.status == CleaningFlowStatus.DRAFT
        assert db.run_query(f'SELECT COUNT(*) AS row_count FROM "{flow.draft_table}"').loc[0, "row_count"] == 2
        assert db.run_query('SELECT COUNT(*) AS row_count FROM "sales"').loc[0, "row_count"] == 3
        assert actions[-1].action_type == CleaningActionType.DROP_DUPLICATES
        assert actions[-1].arguments == {"subset": ["order_id"]}
        assert actions[-1].before_summary["row_count"] == 3
        assert actions[-1].after_summary["row_count"] == 2
    finally:
        db.close()


def test_rename_column_mutates_draft_and_logs_action(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        rename_column(db, registry, flow.flow_id, old_name="revenue", new_name="net_revenue")
        actions = registry.list_cleaning_actions(flow.flow_id)
        draft_columns = set(db.describe_table(flow.draft_table)["column_name"])
        source_columns = set(db.describe_table("sales")["column_name"])

        assert "net_revenue" in draft_columns
        assert "revenue" not in draft_columns
        assert "revenue" in source_columns
        assert actions[-1].action_type == CleaningActionType.RENAME_COLUMN
        assert actions[-1].arguments == {"old_name": "revenue", "new_name": "net_revenue"}
    finally:
        db.close()


def test_impute_numeric_with_median_mutates_draft_and_logs_missingness(tmp_path):
    db = _db_with_missing_values(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        impute_numeric(db, registry, flow.flow_id, column="revenue", strategy="median")
        actions = registry.list_cleaning_actions(flow.flow_id)

        draft_missing = db.run_query(
            f'SELECT SUM(CASE WHEN "revenue" IS NULL THEN 1 ELSE 0 END) AS missing_count FROM "{flow.draft_table}"'
        ).loc[0, "missing_count"]
        source_missing = db.run_query(
            'SELECT SUM(CASE WHEN "revenue" IS NULL THEN 1 ELSE 0 END) AS missing_count FROM "sales"'
        ).loc[0, "missing_count"]

        assert draft_missing == 0
        assert source_missing == 2
        assert actions[-1].action_type == CleaningActionType.IMPUTE_NUMERIC
        assert actions[-1].arguments == {"column": "revenue", "strategy": "median", "fill_value": 200.0}
        assert actions[-1].before_summary["missing_count"] == 2
        assert actions[-1].after_summary["missing_count"] == 0
    finally:
        db.close()


def test_impute_numeric_with_constant(tmp_path):
    db = _db_with_missing_values(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        impute_numeric(db, registry, flow.flow_id, column="revenue", strategy="constant", constant=0)

        values = db.run_query(f'SELECT "revenue" FROM "{flow.draft_table}" ORDER BY "order_id"')["revenue"].tolist()
        assert values == [100.0, 0.0, 300.0, 0.0]
    finally:
        db.close()


def test_impute_categorical_with_mode_and_constant(tmp_path):
    db = _db_with_missing_values(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        impute_categorical(db, registry, flow.flow_id, column="region", strategy="mode")
        actions = registry.list_cleaning_actions(flow.flow_id)

        values = db.run_query(f'SELECT "region" FROM "{flow.draft_table}" ORDER BY "order_id"')["region"].tolist()
        assert values == ["East", "East", "West", "East"]
        assert actions[-1].action_type == CleaningActionType.IMPUTE_CATEGORICAL
        assert actions[-1].arguments == {"column": "region", "strategy": "mode", "fill_value": "East"}

        second_flow = start_cleaning_flow(db, registry, project_id, "sales")
        impute_categorical(db, registry, second_flow.flow_id, column="region", strategy="constant", constant="Unknown")
        constant_values = db.run_query(f'SELECT "region" FROM "{second_flow.draft_table}" ORDER BY "order_id"')["region"].tolist()
        assert constant_values == ["East", "East", "West", "Unknown"]
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


def test_mutation_tools_validate_columns(tmp_path):
    db = _db_with_sales(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        with pytest.raises(ValueError, match="Column not found"):
            drop_duplicate_rows(db, registry, flow.flow_id, subset=["missing"])

        with pytest.raises(ValueError, match="Column already exists"):
            rename_column(db, registry, flow.flow_id, old_name="revenue", new_name="order_id")
    finally:
        db.close()


def test_imputation_tools_validate_strategy_and_column_types(tmp_path):
    db = _db_with_missing_values(tmp_path)
    try:
        registry = DuckDBRegistry(db)
        project_id = __import__("uuid").uuid4()
        flow = start_cleaning_flow(db, registry, project_id, "sales")

        with pytest.raises(ValueError, match="not numeric"):
            impute_numeric(db, registry, flow.flow_id, column="region", strategy="median")

        with pytest.raises(ValueError, match="not categorical"):
            impute_categorical(db, registry, flow.flow_id, column="revenue", strategy="mode")

        with pytest.raises(ValueError, match="Unsupported numeric"):
            impute_numeric(db, registry, flow.flow_id, column="revenue", strategy="random")

        with pytest.raises(ValueError, match="Categorical constant is required"):
            impute_categorical(db, registry, flow.flow_id, column="region", strategy="constant", constant="")
    finally:
        db.close()

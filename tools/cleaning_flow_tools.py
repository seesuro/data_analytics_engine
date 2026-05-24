import re
from datetime import UTC, datetime
from uuid import UUID

from contracts import CleaningAction, CleaningActionType, CleaningFlow, CleaningFlowStatus
from storage.duckdb_registry import DuckDBRegistry


def start_cleaning_flow(db, registry: DuckDBRegistry, project_id: UUID, source_table: str) -> CleaningFlow:
    _ensure_table_exists(db, source_table)
    draft_table = _draft_table_name(source_table)
    db.conn.execute(f"CREATE TABLE {_quote_identifier(draft_table)} AS SELECT * FROM {_quote_identifier(source_table)}")

    flow = CleaningFlow(
        project_id=project_id,
        source_table=source_table,
        draft_table=draft_table,
    )
    registry.register_cleaning_flow(flow)
    registry.register_cleaning_action(
        CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.START_FLOW,
            arguments={"source_table": source_table},
            before_summary=_table_summary(db, source_table),
            after_summary=_table_summary(db, draft_table),
        )
    )
    return flow


def preview_cleaning_flow(db, registry: DuckDBRegistry, flow_id: str | UUID) -> dict:
    flow = registry.get_cleaning_flow(flow_id)
    actions = registry.list_cleaning_actions(flow.flow_id)
    return {
        "flow_id": str(flow.flow_id),
        "status": flow.status.value,
        "source_table": flow.source_table,
        "draft_table": flow.draft_table,
        "output_table": flow.output_table,
        "source_summary": _table_summary(db, flow.source_table),
        "draft_summary": _table_summary(db, flow.draft_table) if _table_exists(db, flow.draft_table) else None,
        "actions": [
            {
                "action_id": str(action.action_id),
                "action_type": action.action_type.value,
                "status": action.status.value,
                "arguments": action.arguments,
                "before_summary": action.before_summary,
                "after_summary": action.after_summary,
                "error": action.error,
            }
            for action in actions
        ],
    }


def drop_duplicate_rows(db, registry: DuckDBRegistry, flow_id: str | UUID, subset: list[str] | None = None) -> CleaningFlow:
    flow = registry.get_cleaning_flow(flow_id)
    _ensure_draft_flow(flow)
    _ensure_table_exists(db, flow.draft_table)
    before_summary = _table_summary(db, flow.draft_table)
    subset = subset or list(before_summary["columns"])
    _ensure_columns_exist(before_summary["columns"], subset)

    temp_table = f"{flow.draft_table}_dedup_tmp"
    partition_by = ", ".join(_quote_identifier(column) for column in subset)
    order_by = ", ".join(_quote_identifier(column) for column in before_summary["columns"])
    db.conn.execute(
        f"""
        CREATE TABLE {_quote_identifier(temp_table)} AS
        SELECT * EXCLUDE (__row_number)
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY {partition_by} ORDER BY {order_by}) AS __row_number
            FROM {_quote_identifier(flow.draft_table)}
        )
        WHERE __row_number = 1
        """
    )
    db.conn.execute(f"DROP TABLE {_quote_identifier(flow.draft_table)}")
    db.conn.execute(f"ALTER TABLE {_quote_identifier(temp_table)} RENAME TO {_quote_identifier(flow.draft_table)}")

    updated_flow = _touch_flow(flow)
    registry.register_cleaning_flow(updated_flow)
    registry.register_cleaning_action(
        CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.DROP_DUPLICATES,
            arguments={"subset": subset},
            before_summary=before_summary,
            after_summary=_table_summary(db, flow.draft_table),
        )
    )
    return updated_flow


def rename_column(db, registry: DuckDBRegistry, flow_id: str | UUID, old_name: str, new_name: str) -> CleaningFlow:
    flow = registry.get_cleaning_flow(flow_id)
    _ensure_draft_flow(flow)
    _ensure_table_exists(db, flow.draft_table)
    before_summary = _table_summary(db, flow.draft_table)
    _ensure_columns_exist(before_summary["columns"], [old_name])
    _ensure_safe_new_column(before_summary["columns"], new_name)

    db.conn.execute(
        f"ALTER TABLE {_quote_identifier(flow.draft_table)} RENAME COLUMN {_quote_identifier(old_name)} TO {_quote_identifier(new_name)}"
    )

    updated_flow = _touch_flow(flow)
    registry.register_cleaning_flow(updated_flow)
    registry.register_cleaning_action(
        CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.RENAME_COLUMN,
            arguments={"old_name": old_name, "new_name": new_name},
            before_summary=before_summary,
            after_summary=_table_summary(db, flow.draft_table),
        )
    )
    return updated_flow


def save_cleaned_table(
    db,
    registry: DuckDBRegistry,
    flow_id: str | UUID,
    output_table: str | None = None,
) -> CleaningFlow:
    flow = registry.get_cleaning_flow(flow_id)
    _ensure_draft_flow(flow)
    _ensure_table_exists(db, flow.draft_table)

    cleaned_table = output_table or _next_cleaned_table_name(db, flow.source_table)
    db.conn.execute(f"CREATE TABLE {_quote_identifier(cleaned_table)} AS SELECT * FROM {_quote_identifier(flow.draft_table)}")

    now = datetime.now(UTC)
    updated_flow = flow.model_copy(
        update={
            "status": CleaningFlowStatus.COMMITTED,
            "output_table": cleaned_table,
            "updated_at": now,
            "completed_at": now,
        }
    )
    registry.register_cleaning_flow(updated_flow)
    registry.register_cleaning_action(
        CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.SAVE_CLEANED_TABLE,
            arguments={"output_table": cleaned_table},
            before_summary=_table_summary(db, flow.draft_table),
            after_summary=_table_summary(db, cleaned_table),
        )
    )
    return updated_flow


def discard_cleaning_flow(db, registry: DuckDBRegistry, flow_id: str | UUID, drop_draft: bool = True) -> CleaningFlow:
    flow = registry.get_cleaning_flow(flow_id)
    _ensure_draft_flow(flow)

    before_summary = _table_summary(db, flow.draft_table) if _table_exists(db, flow.draft_table) else {}
    if drop_draft and _table_exists(db, flow.draft_table):
        db.conn.execute(f"DROP TABLE {_quote_identifier(flow.draft_table)}")

    now = datetime.now(UTC)
    updated_flow = flow.model_copy(
        update={
            "status": CleaningFlowStatus.ABORTED,
            "updated_at": now,
            "completed_at": now,
        }
    )
    registry.register_cleaning_flow(updated_flow)
    registry.register_cleaning_action(
        CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.DISCARD_DRAFT,
            arguments={"drop_draft": drop_draft},
            before_summary=before_summary,
            after_summary={"draft_table_exists": _table_exists(db, flow.draft_table)},
        )
    )
    return updated_flow


def _touch_flow(flow: CleaningFlow) -> CleaningFlow:
    return flow.model_copy(update={"updated_at": datetime.now(UTC)})


def _ensure_draft_flow(flow: CleaningFlow) -> None:
    if flow.status != CleaningFlowStatus.DRAFT:
        raise ValueError(f"Cleaning flow is not draft: {flow.status}")


def _draft_table_name(source_table: str) -> str:
    return f"{source_table}_draft_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _next_cleaned_table_name(db, source_table: str) -> str:
    index = 1
    while True:
        candidate = f"{source_table}_cleaned_v{index}"
        if not _table_exists(db, candidate):
            return candidate
        index += 1


def _table_summary(db, table_name: str) -> dict:
    return {
        "table_name": table_name,
        "row_count": _row_count(db, table_name),
        "columns": _table_schema(db, table_name),
    }


def _ensure_columns_exist(columns: dict[str, str], requested_columns: list[str]) -> None:
    missing = [column for column in requested_columns if column not in columns]
    if missing:
        raise ValueError(f"Column not found: {', '.join(missing)}")


def _ensure_safe_new_column(columns: dict[str, str], new_name: str) -> None:
    _quote_identifier(new_name)
    if new_name in columns:
        raise ValueError(f"Column already exists: {new_name}")


def _row_count(db, table_name: str) -> int:
    return int(db.run_query(f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}").loc[0, "row_count"])


def _table_schema(db, table_name: str) -> dict[str, str]:
    described = db.describe_table(table_name)
    return {
        row["column_name"]: row["column_type"]
        for row in described[["column_name", "column_type"]].to_dict(orient="records")
    }


def _ensure_table_exists(db, table_name: str) -> None:
    if not _table_exists(db, table_name):
        raise ValueError(f"Table not found: {table_name}")


def _table_exists(db, table_name: str) -> bool:
    return table_name in {row[0] for row in db.list_tables()}


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Unsafe identifier: {identifier}")
    return f'"{identifier}"'

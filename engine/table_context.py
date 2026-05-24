import re
from dataclasses import dataclass
from typing import Any

from contracts import CleaningFlow, CleaningFlowStatus
from storage.duckdb_registry import DuckDBRegistry


@dataclass(frozen=True)
class WorkingTableContext:
    metadata: dict[str, Any]
    active_flow: CleaningFlow | None = None


def active_cleaning_flow(registry: DuckDBRegistry) -> CleaningFlow | None:
    draft_flows = [flow for flow in registry.list_cleaning_flows() if flow.status == CleaningFlowStatus.DRAFT]
    return draft_flows[-1] if draft_flows else None


def working_table_context(db: Any, registry: DuckDBRegistry, metadata: dict[str, Any]) -> WorkingTableContext:
    flow = active_cleaning_flow(registry)
    if flow is None or not _table_exists(db, flow.draft_table):
        return WorkingTableContext(metadata=metadata)

    tables = {
        flow.draft_table: {
            "columns": _table_schema(db, flow.draft_table),
            "row_count": _row_count(db, flow.draft_table),
            "source_table": flow.source_table,
            "working_table": True,
        }
    }
    tables.update(metadata.get("tables", {}))
    return WorkingTableContext(metadata={"tables": tables}, active_flow=flow)


def _table_exists(db: Any, table_name: str) -> bool:
    return table_name in {row[0] for row in db.list_tables()}


def _table_schema(db: Any, table_name: str) -> dict[str, str]:
    described = db.describe_table(_quote_identifier(table_name))
    return {
        row["column_name"]: row["column_type"]
        for row in described[["column_name", "column_type"]].to_dict(orient="records")
    }


def _row_count(db: Any, table_name: str) -> int:
    return int(db.run_query(f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}").loc[0, "row_count"])


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Unsafe identifier: {identifier}")
    return f'"{identifier}"'

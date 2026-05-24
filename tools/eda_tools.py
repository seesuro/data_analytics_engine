import re
from typing import Any

import pandas as pd

from contracts import ToolCall, ToolName, ToolResult


NUMERIC_TYPES = ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "TINYINT", "UBIGINT")


def execute_eda_tool(tool_call: ToolCall, db: Any, metadata: dict[str, Any]) -> ToolResult:
    table_name = _resolve_table(metadata, tool_call.arguments.get("table_name"))

    if tool_call.tool_name == ToolName.TABLE_PROFILE:
        result = table_profile(db, metadata, table_name)
    elif tool_call.tool_name == ToolName.MISSING_SUMMARY:
        result = missing_summary(db, metadata, table_name)
    elif tool_call.tool_name == ToolName.NUMERIC_SUMMARY:
        result = numeric_summary(db, metadata, table_name)
    elif tool_call.tool_name == ToolName.CORRELATION:
        result = correlation_summary(db, metadata, table_name)
    else:
        raise ValueError(f"Unsupported EDA tool: {tool_call.tool_name}")

    return ToolResult(tool_name=tool_call.tool_name, result=result)


def table_profile(db: Any, metadata: dict[str, Any], table_name: str) -> dict[str, Any]:
    table = _table(metadata, table_name)
    columns = [{"name": name, "type": column_type} for name, column_type in table.get("columns", {}).items()]
    return {
        "table_name": table_name,
        "row_count": int(table.get("row_count", _row_count(db, table_name))),
        "column_count": len(columns),
        "columns": columns,
    }


def missing_summary(db: Any, metadata: dict[str, Any], table_name: str) -> dict[str, Any]:
    table = _table(metadata, table_name)
    row_count = int(table.get("row_count", _row_count(db, table_name)))
    columns = list(table.get("columns", {}))
    expressions = [
        f"SUM(CASE WHEN {_quote_identifier(column)} IS NULL THEN 1 ELSE 0 END) AS {_quote_identifier(column)}"
        for column in columns
    ]
    if not expressions:
        return {"table_name": table_name, "row_count": row_count, "columns": []}

    summary = db.run_query(f"SELECT {', '.join(expressions)} FROM {_quote_identifier(table_name)}").iloc[0].to_dict()
    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": [
            {
                "column": column,
                "missing_count": int(summary.get(column, 0) or 0),
                "missing_pct": round((int(summary.get(column, 0) or 0) / row_count) * 100, 2) if row_count else 0.0,
            }
            for column in columns
        ],
    }


def numeric_summary(db: Any, metadata: dict[str, Any], table_name: str) -> dict[str, Any]:
    numeric_columns = _numeric_columns(metadata, table_name)
    summaries = []
    for column in numeric_columns:
        quoted = _quote_identifier(column)
        row = db.run_query(
            f"""
            SELECT
                COUNT({quoted}) AS count,
                AVG({quoted}) AS mean,
                MIN({quoted}) AS min,
                MAX({quoted}) AS max,
                STDDEV_SAMP({quoted}) AS std
            FROM {_quote_identifier(table_name)}
            """
        ).iloc[0].to_dict()
        summaries.append(
            {
                "column": column,
                "count": _number(row["count"]),
                "mean": _number(row["mean"]),
                "min": _number(row["min"]),
                "max": _number(row["max"]),
                "std": _number(row["std"]),
            }
        )
    return {"table_name": table_name, "columns": summaries}


def correlation_summary(db: Any, metadata: dict[str, Any], table_name: str) -> dict[str, Any]:
    numeric_columns = _numeric_columns(metadata, table_name)
    if len(numeric_columns) < 2:
        return {"table_name": table_name, "columns": numeric_columns, "correlations": []}

    select_list = ", ".join(_quote_identifier(column) for column in numeric_columns)
    data = db.run_query(f"SELECT {select_list} FROM {_quote_identifier(table_name)}")
    matrix = data.corr(numeric_only=True).fillna(0)
    correlations = []
    for left_index, left_column in enumerate(matrix.columns):
        for right_column in matrix.columns[left_index + 1 :]:
            correlations.append(
                {
                    "left": str(left_column),
                    "right": str(right_column),
                    "correlation": round(float(matrix.loc[left_column, right_column]), 4),
                }
            )
    correlations.sort(key=lambda item: abs(item["correlation"]), reverse=True)
    return {"table_name": table_name, "columns": list(map(str, matrix.columns)), "correlations": correlations}


def choose_eda_tool(message: str, metadata: dict[str, Any]) -> ToolCall | None:
    lowered = message.lower()
    if not any(keyword in lowered for keyword in ("profile", "missing", "null", "numeric", "describe", "correlation", "eda", "quality", "qc")):
        return None

    table_name = _mentioned_table(message, metadata) or _first_table(metadata)
    if table_name is None:
        return None

    if any(keyword in lowered for keyword in ("missing", "null", "quality", "qc")):
        tool_name = ToolName.MISSING_SUMMARY
    elif any(keyword in lowered for keyword in ("correlation", "correlate", "relationship")):
        tool_name = ToolName.CORRELATION
    elif any(keyword in lowered for keyword in ("numeric", "describe", "summary", "statistics", "stats")):
        tool_name = ToolName.NUMERIC_SUMMARY
    else:
        tool_name = ToolName.TABLE_PROFILE

    return ToolCall(tool_name=tool_name, arguments={"table_name": table_name})


def _resolve_table(metadata: dict[str, Any], table_name: str | None) -> str:
    resolved = table_name or _first_table(metadata)
    if resolved is None:
        raise ValueError("No tables are available for EDA.")
    _table(metadata, resolved)
    return resolved


def _table(metadata: dict[str, Any], table_name: str) -> dict[str, Any]:
    tables = metadata.get("tables", {})
    if table_name not in tables:
        raise ValueError(f"Unknown table: {table_name}")
    return tables[table_name]


def _first_table(metadata: dict[str, Any]) -> str | None:
    tables = metadata.get("tables", {})
    return next(iter(tables), None)


def _mentioned_table(message: str, metadata: dict[str, Any]) -> str | None:
    lowered = message.lower()
    for table_name in metadata.get("tables", {}):
        if table_name.lower() in lowered:
            return table_name
    return None


def _numeric_columns(metadata: dict[str, Any], table_name: str) -> list[str]:
    table = _table(metadata, table_name)
    return [
        column
        for column, column_type in table.get("columns", {}).items()
        if str(column_type).upper().startswith(NUMERIC_TYPES)
    ]


def _row_count(db: Any, table_name: str) -> int:
    return int(db.run_query(f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}").loc[0, "row_count"])


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Unsafe identifier: {identifier}")
    return f'"{identifier}"'


def _number(value: Any) -> int | float | None:
    if pd.isna(value):
        return None
    if isinstance(value, float):
        return round(value, 4)
    return int(value)

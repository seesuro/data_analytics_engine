import pandas as pd
import pytest

from contracts import ToolCall, ToolName
from storage.db_manager import DBManager
from tools.eda_tools import choose_eda_tool, correlation_summary, execute_eda_tool, missing_summary, numeric_summary, table_profile


def _metadata() -> dict:
    return {
        "tables": {
            "sales": {
                "columns": {"region": "VARCHAR", "revenue": "BIGINT", "quantity": "BIGINT"},
                "row_count": 3,
            }
        }
    }


def _db(tmp_path):
    db = DBManager(str(tmp_path / "eda.duckdb"))
    db.create_table(
        "sales",
        pd.DataFrame(
            {
                "region": ["East", "West", None],
                "revenue": [100, 200, 300],
                "quantity": [1, 2, 3],
            }
        ),
    )
    return db


def test_table_profile_and_missing_summary(tmp_path):
    db = _db(tmp_path)
    try:
        profile = table_profile(db, _metadata(), "sales")
        missing = missing_summary(db, _metadata(), "sales")

        assert profile["row_count"] == 3
        assert profile["column_count"] == 3
        assert missing["columns"][0] == {"column": "region", "missing_count": 1, "missing_pct": 33.33}
    finally:
        db.close()


def test_numeric_and_correlation_summary(tmp_path):
    db = _db(tmp_path)
    try:
        numeric = numeric_summary(db, _metadata(), "sales")
        correlation = correlation_summary(db, _metadata(), "sales")

        assert [column["column"] for column in numeric["columns"]] == ["revenue", "quantity"]
        assert numeric["columns"][0]["mean"] == 200.0
        assert correlation["correlations"][0]["left"] == "revenue"
        assert correlation["correlations"][0]["right"] == "quantity"
        assert correlation["correlations"][0]["correlation"] == 1.0
    finally:
        db.close()


def test_choose_and_execute_eda_tool(tmp_path):
    db = _db(tmp_path)
    try:
        tool_call = choose_eda_tool("show missing values in sales", _metadata())
        result = execute_eda_tool(tool_call, db, _metadata())

        assert tool_call.tool_name == ToolName.MISSING_SUMMARY
        assert result.tool_name == ToolName.MISSING_SUMMARY
        assert result.result["table_name"] == "sales"
    finally:
        db.close()


def test_execute_eda_tool_rejects_unknown_table(tmp_path):
    db = _db(tmp_path)
    try:
        with pytest.raises(ValueError, match="Unknown table"):
            execute_eda_tool(ToolCall(tool_name=ToolName.TABLE_PROFILE, arguments={"table_name": "missing"}), db, _metadata())
    finally:
        db.close()

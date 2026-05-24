from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from engine.eda_engine import EDAEngine
from storage.db_manager import DBManager


class _StubLLM:
    def invoke(self, _prompt: str):
        return SimpleNamespace(content="No missing values were found. Next, check numeric summaries.")


def test_eda_engine_returns_tool_run_and_persistent_messages(tmp_path):
    db = DBManager(str(tmp_path / "eda.duckdb"))
    try:
        db.create_table("sales", pd.DataFrame({"region": ["East"], "revenue": [100]}))
        metadata = {"tables": {"sales": {"columns": {"region": "VARCHAR", "revenue": "BIGINT"}, "row_count": 1}}}

        response = EDAEngine().run(
            message="show missing values",
            project_id=uuid4(),
            db=db,
            metadata=metadata,
            llm=_StubLLM(),
        )

        assert response.run.tool_call.tool_name == "missing_summary"
        assert response.run.tool_result.result["table_name"] == "sales"
        assert response.run.report == "No missing values were found. Next, check numeric summaries."
        assert [message.role for message in response.messages] == ["user", "assistant"]
    finally:
        db.close()

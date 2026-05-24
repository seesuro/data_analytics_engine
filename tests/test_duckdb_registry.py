import json
from uuid import uuid4

import pandas as pd

from contracts import (
    ChatMessage,
    ChatRole,
    CleaningAction,
    CleaningActionStatus,
    CleaningActionType,
    CleaningFlow,
    CleaningFlowStatus,
    Dataset,
    DatasetStatus,
    ResultPreview,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    SqlRun,
    ToolCall,
    ToolName,
    ToolResult,
)
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry


def test_registry_initializes_tables(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        registry = DuckDBRegistry(db)
        registry.initialize()

        tables = {row[0] for row in db.list_tables()}
        assert {"__datasets", "__tables", "__runs", "__run_events", "__chat_messages", "__cleaning_flows", "__cleaning_actions"}.issubset(tables)
    finally:
        db.close()


def test_registry_registers_dataset_and_reconstructs_metadata(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        db.create_table("sales", pd.DataFrame({"region": ["East"], "revenue": [100]}))
        dataset = Dataset(
            project_id=uuid4(),
            source_filename="sales.csv",
            content_hash="abc123",
            raw_path=tmp_path / "raw" / "sales.csv",
            status=DatasetStatus.READY,
            table_name="sales",
            row_count=1,
        )

        registry = DuckDBRegistry(db)
        registry.register_dataset(dataset)

        datasets = registry.list_datasets()
        assert datasets.loc[0, "dataset_id"] == str(dataset.dataset_id)
        assert datasets.loc[0, "status"] == "ready"

        metadata = registry.metadata()
        assert metadata["tables"]["sales"]["row_count"] == 1
        assert set(metadata["tables"]["sales"]["columns"]) == {"region", "revenue"}
    finally:
        db.close()


def test_registry_registers_failed_dataset_without_table(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        dataset = Dataset(
            project_id=uuid4(),
            source_filename="broken.txt",
            content_hash="abc123",
            raw_path=tmp_path / "raw" / "broken.txt",
            status=DatasetStatus.FAILED,
            error="Unsupported file",
        )

        registry = DuckDBRegistry(db)
        registry.register_dataset(dataset)

        datasets = registry.list_datasets()
        tables = registry.list_registered_tables()

        assert datasets.loc[0, "status"] == "failed"
        assert datasets.loc[0, "error"] == "Unsupported file"
        assert tables.empty
    finally:
        db.close()


def test_registry_registers_run(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        project_id = uuid4()
        run = Run(
            project_id=project_id,
            question="total revenue",
            status=RunStatus.SUCCEEDED,
            sql_run=SqlRun(sql="SELECT 1", row_count=1),
            result_preview=ResultPreview(columns=["one"], rows=[{"one": 1}], row_count=1),
            tool_call=ToolCall(tool_name=ToolName.TABLE_PROFILE, arguments={"table_name": "sales"}),
            tool_result=ToolResult(tool_name=ToolName.TABLE_PROFILE, result={"row_count": 1}),
            report="Done.",
        )

        registry = DuckDBRegistry(db)
        registry.register_run(run)

        runs = registry.list_runs()
        assert runs.loc[0, "run_id"] == str(run.run_id)
        assert runs.loc[0, "status"] == "succeeded"
        assert json.loads(runs.loc[0, "sql_json"])["sql"] == "SELECT 1"
        assert json.loads(runs.loc[0, "result_preview_json"])["columns"] == ["one"]
        assert json.loads(runs.loc[0, "tool_call_json"])["tool_name"] == "table_profile"
        assert registry.get_run(run.run_id).tool_result.result == {"row_count": 1}
    finally:
        db.close()


def test_registry_registers_run_events(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        run = Run(project_id=uuid4(), question="show missing values", status=RunStatus.SUCCEEDED)
        event = RunEvent(
            run_id=run.run_id,
            event_type=RunEventType.COMPLETED,
            message="EDA tool completed.",
            payload={"tool_name": "missing_summary"},
        )

        registry = DuckDBRegistry(db)
        registry.register_run(run)
        registry.register_run_event(event)

        events = registry.list_run_events(run.run_id)
        assert len(events) == 1
        assert events[0].event_id == event.event_id
        assert events[0].run_id == run.run_id
        assert events[0].event_type == RunEventType.COMPLETED
        assert events[0].payload == {"tool_name": "missing_summary"}
    finally:
        db.close()


def test_registry_registers_chat_messages(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        project_id = uuid4()
        message = ChatMessage(
            project_id=project_id,
            role=ChatRole.USER,
            content="show missing values",
            payload={"source": "test"},
        )

        registry = DuckDBRegistry(db)
        registry.register_chat_message(message)

        messages = registry.list_chat_messages()
        assert len(messages) == 1
        assert messages[0].project_id == project_id
        assert messages[0].role == ChatRole.USER
        assert messages[0].content == "show missing values"
        assert messages[0].payload == {"source": "test"}
    finally:
        db.close()


def test_registry_registers_cleaning_flow_and_actions(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        project_id = uuid4()
        flow = CleaningFlow(
            project_id=project_id,
            source_table="sales",
            draft_table="sales_draft_abcd",
        )
        action = CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.START_FLOW,
            arguments={"source_table": "sales"},
            before_summary={"source_table": "sales"},
            after_summary={"draft_table": "sales_draft_abcd"},
        )

        registry = DuckDBRegistry(db)
        registry.register_cleaning_flow(flow)
        registry.register_cleaning_action(action)

        flows = registry.list_cleaning_flows()
        actions = registry.list_cleaning_actions(flow.flow_id)

        assert len(flows) == 1
        assert flows[0].flow_id == flow.flow_id
        assert flows[0].status == CleaningFlowStatus.DRAFT
        assert registry.get_cleaning_flow(flow.flow_id).draft_table == "sales_draft_abcd"
        assert len(actions) == 1
        assert actions[0].action_type == CleaningActionType.START_FLOW
        assert actions[0].after_summary == {"draft_table": "sales_draft_abcd"}
    finally:
        db.close()


def test_registry_registers_failed_cleaning_action(tmp_path):
    db = DBManager(str(tmp_path / "registry.duckdb"))
    try:
        flow = CleaningFlow(project_id=uuid4(), source_table="sales", draft_table="sales_draft_abcd")
        action = CleaningAction(
            flow_id=flow.flow_id,
            action_type=CleaningActionType.IMPUTE_NUMERIC,
            status=CleaningActionStatus.FAILED,
            arguments={"column": "revenue", "strategy": "median"},
            error="Column not found.",
        )

        registry = DuckDBRegistry(db)
        registry.register_cleaning_flow(flow)
        registry.register_cleaning_action(action)

        actions = registry.list_cleaning_actions()
        assert actions[0].status == CleaningActionStatus.FAILED
        assert actions[0].error == "Column not found."
    finally:
        db.close()

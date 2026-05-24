import json
from uuid import UUID

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
    ResultPreview,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    SqlRun,
    ToolCall,
    ToolResult,
)
from storage.db_manager import DBManager


class DuckDBRegistry:
    def __init__(self, db: DBManager):
        self.db = db

    def initialize(self) -> None:
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __datasets (
                dataset_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                source_filename VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL,
                raw_path VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                uploaded_at TIMESTAMP NOT NULL,
                table_name VARCHAR,
                row_count BIGINT,
                error VARCHAR
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __tables (
                dataset_id VARCHAR NOT NULL,
                table_name VARCHAR PRIMARY KEY,
                schema_json VARCHAR NOT NULL,
                row_count BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __runs (
                run_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                question VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                sql_json VARCHAR,
                result_preview_json VARCHAR,
                tool_call_json VARCHAR,
                tool_result_json VARCHAR,
                report VARCHAR,
                error VARCHAR,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP
            )
            """
        )
        self._ensure_column("__runs", "tool_call_json", "VARCHAR")
        self._ensure_column("__runs", "tool_result_json", "VARCHAR")
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __run_events (
                event_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                message VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                payload_json VARCHAR NOT NULL
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __chat_messages (
                message_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                content VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                run_id VARCHAR,
                payload_json VARCHAR
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __cleaning_flows (
                flow_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                source_table VARCHAR NOT NULL,
                draft_table VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                output_table VARCHAR,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __cleaning_actions (
                action_id VARCHAR PRIMARY KEY,
                flow_id VARCHAR NOT NULL,
                action_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                arguments_json VARCHAR NOT NULL,
                before_summary_json VARCHAR NOT NULL,
                after_summary_json VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                error VARCHAR
            )
            """
        )

    def register_dataset(self, dataset: Dataset, schema: dict[str, str] | None = None) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __datasets (
                dataset_id,
                project_id,
                source_filename,
                content_hash,
                raw_path,
                status,
                uploaded_at,
                table_name,
                row_count,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(dataset.dataset_id),
                str(dataset.project_id),
                dataset.source_filename,
                dataset.content_hash,
                str(dataset.raw_path),
                dataset.status.value,
                dataset.uploaded_at,
                dataset.table_name,
                dataset.row_count,
                dataset.error,
            ],
        )

        if dataset.table_name and dataset.row_count is not None:
            table_schema = schema or self.table_schema(dataset.table_name)
            self.db.conn.execute(
                """
                INSERT OR REPLACE INTO __tables (
                    dataset_id,
                    table_name,
                    schema_json,
                    row_count
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    str(dataset.dataset_id),
                    dataset.table_name,
                    json.dumps(table_schema, sort_keys=True),
                    dataset.row_count,
                ],
            )

    def register_run(self, run: Run) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __runs (
                run_id,
                project_id,
                question,
                status,
                sql_json,
                result_preview_json,
                tool_call_json,
                tool_result_json,
                report,
                error,
                created_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(run.run_id),
                str(run.project_id),
                run.question,
                run.status.value,
                run.sql_run.model_dump_json() if run.sql_run else None,
                run.result_preview.model_dump_json() if run.result_preview else None,
                run.tool_call.model_dump_json() if run.tool_call else None,
                run.tool_result.model_dump_json() if run.tool_result else None,
                run.report,
                run.error,
                run.created_at,
                run.completed_at,
            ],
        )

    def register_run_event(self, event: RunEvent) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __run_events (
                event_id,
                run_id,
                event_type,
                message,
                created_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(event.event_id),
                str(event.run_id),
                event.event_type.value,
                event.message,
                event.created_at,
                json.dumps(event.payload, sort_keys=True),
            ],
        )

    def register_run_events(self, events: list[RunEvent]) -> None:
        for event in events:
            self.register_run_event(event)

    def register_chat_message(self, message: ChatMessage) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __chat_messages (
                message_id,
                project_id,
                role,
                content,
                created_at,
                run_id,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(message.message_id),
                str(message.project_id),
                message.role.value,
                message.content,
                message.created_at,
                str(message.run_id) if message.run_id else None,
                json.dumps(message.payload, sort_keys=True),
            ],
        )

    def register_chat_messages(self, messages: list[ChatMessage]) -> None:
        for message in messages:
            self.register_chat_message(message)

    def list_chat_messages(self) -> list[ChatMessage]:
        self.initialize()
        rows = self.db.run_query("SELECT * FROM __chat_messages ORDER BY created_at").to_dict(orient="records")
        return [self._row_to_chat_message(row) for row in rows]

    def register_cleaning_flow(self, flow: CleaningFlow) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __cleaning_flows (
                flow_id,
                project_id,
                source_table,
                draft_table,
                status,
                output_table,
                created_at,
                updated_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(flow.flow_id),
                str(flow.project_id),
                flow.source_table,
                flow.draft_table,
                flow.status.value,
                flow.output_table,
                flow.created_at,
                flow.updated_at,
                flow.completed_at,
            ],
        )

    def list_cleaning_flows(self) -> list[CleaningFlow]:
        self.initialize()
        rows = self.db.run_query("SELECT * FROM __cleaning_flows ORDER BY created_at").to_dict(orient="records")
        return [self._row_to_cleaning_flow(row) for row in rows]

    def get_cleaning_flow(self, flow_id: str | UUID) -> CleaningFlow:
        self.initialize()
        rows = self.db.conn.execute("SELECT * FROM __cleaning_flows WHERE flow_id = ?", [str(flow_id)]).fetchdf()
        if rows.empty:
            raise KeyError(f"Cleaning flow not found: {flow_id}")
        return self._row_to_cleaning_flow(rows.iloc[0].to_dict())

    def register_cleaning_action(self, action: CleaningAction) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __cleaning_actions (
                action_id,
                flow_id,
                action_type,
                status,
                arguments_json,
                before_summary_json,
                after_summary_json,
                created_at,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(action.action_id),
                str(action.flow_id),
                action.action_type.value,
                action.status.value,
                json.dumps(action.arguments, sort_keys=True),
                json.dumps(action.before_summary, sort_keys=True),
                json.dumps(action.after_summary, sort_keys=True),
                action.created_at,
                action.error,
            ],
        )

    def list_cleaning_actions(self, flow_id: str | UUID | None = None) -> list[CleaningAction]:
        self.initialize()
        if flow_id is None:
            rows = self.db.run_query("SELECT * FROM __cleaning_actions ORDER BY created_at").to_dict(orient="records")
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM __cleaning_actions WHERE flow_id = ? ORDER BY created_at",
                [str(flow_id)],
            ).fetchdf().to_dict(orient="records")
        return [self._row_to_cleaning_action(row) for row in rows]

    def list_datasets(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __datasets ORDER BY uploaded_at")

    def list_registered_tables(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __tables ORDER BY created_at")

    def list_runs(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __runs ORDER BY created_at")

    def list_run_events(self, run_id: str | UUID | None = None) -> list[RunEvent]:
        self.initialize()
        if run_id is None:
            rows = self.db.run_query("SELECT * FROM __run_events ORDER BY created_at").to_dict(orient="records")
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM __run_events WHERE run_id = ? ORDER BY created_at",
                [str(run_id)],
            ).fetchdf().to_dict(orient="records")
        return [self._row_to_run_event(row) for row in rows]

    def get_run(self, run_id: str | UUID) -> Run:
        self.initialize()
        rows = self.db.conn.execute("SELECT * FROM __runs WHERE run_id = ?", [str(run_id)]).fetchdf()
        if rows.empty:
            raise KeyError(f"Run not found: {run_id}")
        return self._row_to_run(rows.iloc[0].to_dict())

    def metadata(self) -> dict:
        tables = {}
        for row in self.list_registered_tables().to_dict(orient="records"):
            tables[row["table_name"]] = {
                "columns": json.loads(row["schema_json"]),
                "row_count": row["row_count"],
            }
        return {"tables": tables}

    def table_schema(self, table_name: str) -> dict[str, str]:
        described = self.db.describe_table(table_name)
        return {
            row["column_name"]: row["column_type"]
            for row in described[["column_name", "column_type"]].to_dict(orient="records")
        }

    def _row_to_run(self, row: dict) -> Run:
        sql_json = row.get("sql_json")
        result_preview_json = row.get("result_preview_json")
        tool_call_json = row.get("tool_call_json")
        tool_result_json = row.get("tool_result_json")
        return Run(
            run_id=row["run_id"],
            project_id=row["project_id"],
            question=row["question"],
            status=RunStatus(row["status"]),
            sql_run=SqlRun.model_validate_json(sql_json) if sql_json else None,
            result_preview=ResultPreview.model_validate_json(result_preview_json) if result_preview_json else None,
            tool_call=ToolCall.model_validate_json(tool_call_json) if tool_call_json else None,
            tool_result=ToolResult.model_validate_json(tool_result_json) if tool_result_json else None,
            report=row.get("report"),
            error=row.get("error"),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
        )

    def _row_to_chat_message(self, row: dict) -> ChatMessage:
        payload_json = row.get("payload_json")
        return ChatMessage(
            message_id=row["message_id"],
            project_id=row["project_id"],
            role=ChatRole(row["role"]),
            content=row["content"],
            created_at=row["created_at"],
            run_id=row.get("run_id"),
            payload=json.loads(payload_json) if payload_json else {},
        )

    def _row_to_run_event(self, row: dict) -> RunEvent:
        payload_json = row.get("payload_json")
        return RunEvent(
            event_id=row["event_id"],
            run_id=row["run_id"],
            event_type=RunEventType(row["event_type"]),
            message=row["message"],
            created_at=row["created_at"],
            payload=json.loads(payload_json) if payload_json else {},
        )

    def _row_to_cleaning_flow(self, row: dict) -> CleaningFlow:
        return CleaningFlow(
            flow_id=row["flow_id"],
            project_id=row["project_id"],
            source_table=row["source_table"],
            draft_table=row["draft_table"],
            status=CleaningFlowStatus(row["status"]),
            output_table=row.get("output_table"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row.get("completed_at"),
        )

    def _row_to_cleaning_action(self, row: dict) -> CleaningAction:
        return CleaningAction(
            action_id=row["action_id"],
            flow_id=row["flow_id"],
            action_type=CleaningActionType(row["action_type"]),
            status=CleaningActionStatus(row["status"]),
            arguments=json.loads(row["arguments_json"]) if row.get("arguments_json") else {},
            before_summary=json.loads(row["before_summary_json"]) if row.get("before_summary_json") else {},
            after_summary=json.loads(row["after_summary_json"]) if row.get("after_summary_json") else {},
            created_at=row["created_at"],
            error=row.get("error"),
        )

    def _ensure_column(self, table_name: str, column_name: str, column_type: str) -> None:
        columns = {
            row["name"]
            for row in self.db.conn.execute(f"PRAGMA table_info('{table_name}')").fetchdf().to_dict(orient="records")
        }
        if column_name not in columns:
            self.db.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

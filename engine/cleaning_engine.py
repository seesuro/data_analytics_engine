import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from contracts import ChatMessage, ChatResponse, ChatRole, Run, RunEvent, RunEventType, RunStatus
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


class CleaningEngine:
    def can_handle(self, message: str, metadata: dict[str, Any]) -> bool:
        return _parse_command(message, metadata) is not None

    def run(
        self,
        message: str,
        project_id: UUID,
        db: Any,
        registry: DuckDBRegistry,
        metadata: dict[str, Any],
    ) -> ChatResponse:
        command = _parse_command(message, metadata)
        if command is None:
            raise ValueError("No matching cleaning command found.")

        try:
            result = _execute_command(command, db, registry, project_id)
            report = _report(command["name"], result)
            status = RunStatus.SUCCEEDED
            event_type = RunEventType.COMPLETED
            event_message = f"Cleaning command completed: {command['name']}"
        except ValueError as exc:
            result = {"error": str(exc), "command": command["name"]}
            report = f"Cleaning command failed: {exc}"
            status = RunStatus.FAILED
            event_type = RunEventType.FAILED
            event_message = str(exc)

        run = Run(
            project_id=project_id,
            question=message,
            status=status,
            completed_at=datetime.now(UTC),
            report=report,
            error=result.get("error"),
        )
        messages = [
            ChatMessage(project_id=project_id, role=ChatRole.USER, content=message, run_id=run.run_id),
            ChatMessage(
                project_id=project_id,
                role=ChatRole.ASSISTANT,
                content=report,
                run_id=run.run_id,
                payload={"cleaning": result},
            ),
        ]
        event = RunEvent(
            run_id=run.run_id,
            event_type=event_type,
            message=event_message,
            payload={"command": command, "result": result},
        )
        return ChatResponse(run=run, events=[event], messages=messages)


def _parse_command(message: str, metadata: dict[str, Any]) -> dict | None:
    lowered = message.lower()
    if "clean" not in lowered and not any(
        keyword in lowered for keyword in ("drop duplicate", "rename", "impute", "save cleaned", "discard draft", "preview draft")
    ):
        return None

    if "start" in lowered and "clean" in lowered:
        table_name = _mentioned_table(message, metadata) or _first_table(metadata)
        return {"name": "start", "table_name": table_name} if table_name else None

    if "preview" in lowered and ("clean" in lowered or "draft" in lowered):
        return {"name": "preview"}

    if "drop duplicate" in lowered:
        subset = _parse_subset(message)
        return {"name": "drop_duplicates", "subset": subset}

    rename_match = re.search(r"rename\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)", message, re.IGNORECASE)
    if rename_match:
        return {"name": "rename_column", "old_name": rename_match.group(1), "new_name": rename_match.group(2)}

    impute_match = re.search(
        r"impute\s+(numeric|categorical)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(mean|median|mode|constant)(?:\s+([^\s]+))?",
        message,
        re.IGNORECASE,
    )
    if impute_match:
        return {
            "name": f"impute_{impute_match.group(1).lower()}",
            "column": impute_match.group(2),
            "strategy": impute_match.group(3).lower(),
            "constant": impute_match.group(4),
        }

    save_match = re.search(r"save\s+cleaned(?:\s+table)?(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?", message, re.IGNORECASE)
    if save_match:
        return {"name": "save", "output_table": save_match.group(1)}

    if "discard" in lowered and ("clean" in lowered or "draft" in lowered):
        return {"name": "discard"}

    return None


def _execute_command(command: dict, db: Any, registry: DuckDBRegistry, project_id: UUID) -> dict:
    if command["name"] == "start":
        flow = start_cleaning_flow(db, registry, project_id, command["table_name"])
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "preview":
        return preview_cleaning_flow(db, registry, _active_flow(registry).flow_id)

    if command["name"] == "drop_duplicates":
        flow = drop_duplicate_rows(db, registry, _active_flow(registry).flow_id, subset=command["subset"])
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "rename_column":
        flow = rename_column(db, registry, _active_flow(registry).flow_id, command["old_name"], command["new_name"])
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "impute_numeric":
        constant = _numeric_constant(command["constant"]) if command["strategy"] == "constant" else None
        flow = impute_numeric(db, registry, _active_flow(registry).flow_id, command["column"], command["strategy"], constant)
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "impute_categorical":
        flow = impute_categorical(
            db,
            registry,
            _active_flow(registry).flow_id,
            command["column"],
            command["strategy"],
            command["constant"],
        )
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "save":
        flow = save_cleaned_table(db, registry, _active_flow(registry).flow_id, output_table=command["output_table"])
        return _flow_result(registry, flow.flow_id)

    if command["name"] == "discard":
        flow = discard_cleaning_flow(db, registry, _active_flow(registry).flow_id)
        return _flow_result(registry, flow.flow_id)

    raise ValueError(f"Unsupported cleaning command: {command['name']}")


def _active_flow(registry: DuckDBRegistry):
    draft_flows = [flow for flow in registry.list_cleaning_flows() if flow.status.value == "draft"]
    if not draft_flows:
        raise ValueError("No active draft cleaning flow found.")
    return draft_flows[-1]


def _flow_result(registry: DuckDBRegistry, flow_id: UUID) -> dict:
    flow = registry.get_cleaning_flow(flow_id)
    actions = registry.list_cleaning_actions(flow.flow_id)
    return {
        "flow_id": str(flow.flow_id),
        "status": flow.status.value,
        "source_table": flow.source_table,
        "draft_table": flow.draft_table,
        "output_table": flow.output_table,
        "latest_action": actions[-1].action_type.value if actions else None,
    }


def _report(command_name: str, result: dict) -> str:
    if command_name == "start":
        return f"Started a cleaning draft for {result['source_table']} as {result['draft_table']}."
    if command_name == "preview":
        return f"Cleaning draft {result['draft_table']} is {result['status']} with {len(result['actions'])} action(s)."
    if command_name == "save":
        return f"Saved cleaned table as {result['output_table']}."
    if command_name == "discard":
        return "Discarded the active cleaning draft."
    return f"Applied {result['latest_action']} to draft table {result['draft_table']}."


def _mentioned_table(message: str, metadata: dict[str, Any]) -> str | None:
    lowered = message.lower()
    for table_name in metadata.get("tables", {}):
        if table_name.lower() in lowered:
            return table_name
    return None


def _first_table(metadata: dict[str, Any]) -> str | None:
    return next(iter(metadata.get("tables", {})), None)


def _parse_subset(message: str) -> list[str] | None:
    match = re.search(r"(?:by|on)\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)", message, re.IGNORECASE)
    if not match:
        return None
    return [column.strip() for column in match.group(1).split(",")]


def _numeric_constant(value: str | None) -> int | float:
    if value is None:
        raise ValueError("Numeric constant is required for constant imputation.")
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed

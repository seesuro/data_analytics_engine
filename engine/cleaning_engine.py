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
from tools.eda_tools import NUMERIC_TYPES, missing_summary


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
        keyword in lowered
        for keyword in (
            "drop duplicate",
            "rename",
            "impute",
            "save cleaned",
            "discard draft",
            "preview draft",
            "handle null",
            "handle missing",
            "treat null",
            "treat missing",
            "fix null",
            "fix missing",
        )
    ):
        return None

    if _asks_for_missing_value_guidance(lowered):
        table_name = _mentioned_table(message, metadata) or _first_table(metadata)
        return {"name": "missing_value_guidance", "table_name": table_name} if table_name else None

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
    if command["name"] == "missing_value_guidance":
        return _missing_value_guidance(db, command["table_name"], registry)

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
    if command_name == "missing_value_guidance":
        return _missing_value_guidance_report(result)
    if command_name == "start":
        return f"Started a cleaning draft for {result['source_table']} as {result['draft_table']}."
    if command_name == "preview":
        return f"Cleaning draft {result['draft_table']} is {result['status']} with {len(result['actions'])} action(s)."
    if command_name == "save":
        return f"Saved cleaned table as {result['output_table']}."
    if command_name == "discard":
        return "Discarded the active cleaning draft."
    return f"Applied {result['latest_action']} to draft table {result['draft_table']}."


def _asks_for_missing_value_guidance(lowered: str) -> bool:
    guidance_terms = ("how", "what should", "suggest", "recommend", "handle", "treat", "fix", "deal with")
    missing_terms = ("null", "missing", "na", "nan")
    return any(term in lowered for term in guidance_terms) and any(term in lowered for term in missing_terms)


def _missing_value_guidance(db: Any, table_name: str, registry: DuckDBRegistry) -> dict:
    raw_metadata = registry.metadata()
    summary = missing_summary(db, raw_metadata, table_name)
    missing_columns = [column for column in summary["columns"] if column["missing_count"] > 0]
    recommendations = [
        _column_recommendation(raw_metadata, table_name, column)
        for column in missing_columns
    ]
    active_draft = next((flow for flow in reversed(registry.list_cleaning_flows()) if flow.status.value == "draft"), None)
    return {
        "table_name": table_name,
        "row_count": summary["row_count"],
        "missing_columns": missing_columns,
        "recommendations": recommendations,
        "active_draft_table": active_draft.draft_table if active_draft else None,
    }


def _column_recommendation(metadata: dict[str, Any], table_name: str, missing_column: dict[str, Any]) -> dict[str, Any]:
    column_name = missing_column["column"]
    column_type = str(metadata["tables"][table_name]["columns"][column_name])
    missing_pct = missing_column["missing_pct"]
    risk_level = "high" if missing_pct >= 40 else "medium" if missing_pct >= 10 else "low"
    if column_type.upper().startswith(NUMERIC_TYPES):
        action = f"impute numeric {column_name} median"
        if risk_level == "high":
            recommendation = f"review {column_name} before imputation"
            rationale = "This column has high missingness, so blind median imputation may distort analysis."
        else:
            recommendation = action
            rationale = "Numeric columns often start with median imputation because it is robust to outliers."
    else:
        action = f"impute categorical {column_name} mode"
        if risk_level == "high":
            recommendation = f"review {column_name} before imputation"
            rationale = "This column has high missingness, so blind mode imputation may erase important uncertainty."
        else:
            recommendation = action
            rationale = "Categorical/text columns often start with mode imputation or a business-specific constant."
    return {
        "column": column_name,
        "missing_count": missing_column["missing_count"],
        "missing_pct": missing_pct,
        "column_type": column_type,
        "risk_level": risk_level,
        "suggested_action": recommendation,
        "fallback_imputation_command": action,
        "rationale": rationale,
    }


def _missing_value_guidance_report(result: dict) -> str:
    if not result["missing_columns"]:
        return f"No missing values were found in {result['table_name']}; no null-handling action is needed right now."

    lines = [
        f"Found missing values in {len(result['missing_columns'])} column(s) of {result['table_name']}.",
        "Suggested next actions:",
    ]
    if any(recommendation["risk_level"] == "high" for recommendation in result["recommendations"]):
        lines.append("- High missingness warning: several columns have 40%+ missing values, so do not blindly impute them.")
    for recommendation in result["recommendations"][:5]:
        if recommendation["risk_level"] == "high":
            lines.append(
                f"- {recommendation['column']}: {recommendation['missing_count']} missing "
                f"({recommendation['missing_pct']}%, high risk). Review whether to keep, drop, flag, or then use "
                f"`{recommendation['fallback_imputation_command']}`."
            )
        else:
            lines.append(
                f"- {recommendation['column']}: {recommendation['missing_count']} missing "
                f"({recommendation['missing_pct']}%). Try `{recommendation['suggested_action']}`."
            )
    if result["active_draft_table"] is None:
        lines.append(f"Start a reviewable draft first with `start cleaning {result['table_name']}` before applying changes.")
    else:
        lines.append(f"These actions will apply to active draft `{result['active_draft_table']}` if you run them.")
    return "\n".join(lines)


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

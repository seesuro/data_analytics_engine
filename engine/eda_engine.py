import json
from datetime import UTC, datetime
from typing import Any

from contracts import ChatMessage, ChatResponse, ChatRole, Run, RunEvent, RunEventType, RunStatus
from tools.eda_tools import choose_eda_tool, execute_eda_tool


class EDAEngine:
    def can_handle(self, message: str, metadata: dict[str, Any]) -> bool:
        return choose_eda_tool(message, metadata) is not None

    def run(
        self,
        message: str,
        project_id,
        db: Any,
        metadata: dict[str, Any],
        llm: Any | None = None,
    ) -> ChatResponse:
        tool_call = choose_eda_tool(message, metadata)
        if tool_call is None:
            raise ValueError("No matching EDA tool found.")

        tool_result = execute_eda_tool(tool_call, db, metadata)
        report = _explain_tool_result(message, tool_result.result, llm)
        run = Run(
            project_id=project_id,
            question=message,
            status=RunStatus.SUCCEEDED,
            completed_at=datetime.now(UTC),
            tool_call=tool_call,
            tool_result=tool_result,
            report=report,
        )
        messages = [
            ChatMessage(project_id=project_id, role=ChatRole.USER, content=message, run_id=run.run_id),
            ChatMessage(
                project_id=project_id,
                role=ChatRole.ASSISTANT,
                content=report,
                run_id=run.run_id,
                payload={"tool_name": tool_call.tool_name.value},
            ),
        ]
        event = RunEvent(
            run_id=run.run_id,
            event_type=RunEventType.COMPLETED,
            message=f"EDA tool completed: {tool_call.tool_name.value}",
            payload={"tool_call": tool_call.model_dump(mode="json")},
        )
        return ChatResponse(run=run, events=[event], messages=messages)


def _explain_tool_result(message: str, result: dict[str, Any], llm: Any | None) -> str:
    fallback = _fallback_report(result)
    if llm is None:
        return fallback

    prompt = f"""
You are an EDA assistant explaining deterministic tool output.

User request:
{message}

Tool result JSON:
{json.dumps(result, indent=2, default=str)}

Write a concise explanation grounded only in the tool result.
Rules:
- Mention the most important finding first.
- Do not invent causes.
- Suggest at most one practical next EDA step.
"""
    response = llm.invoke(prompt)
    return response.content.strip() or fallback


def _fallback_report(result: dict[str, Any]) -> str:
    if "columns" in result and result["columns"] and "missing_count" in result["columns"][0]:
        missing = [column for column in result["columns"] if column["missing_count"] > 0]
        if missing:
            names = ", ".join(column["column"] for column in missing[:5])
            return f"Missing values were found in {len(missing)} column(s): {names}."
        return "No missing values were found in the profiled table."

    if "correlations" in result:
        correlations = result.get("correlations", [])
        if correlations:
            top = correlations[0]
            return f"The strongest numeric correlation is {top['left']} vs {top['right']} at {top['correlation']}."
        return "There are not enough numeric columns to calculate correlations."

    if "column_count" in result:
        return f"Table {result['table_name']} has {result['row_count']} rows and {result['column_count']} columns."

    if "columns" in result:
        return f"Numeric summary completed for {len(result['columns'])} column(s)."

    return "EDA tool completed."

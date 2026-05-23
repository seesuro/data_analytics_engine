from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pandas as pd

from contracts import ArtifactRef, ChatResponse, ResultPreview, Run, RunEvent, RunEventType, RunStatus, SqlRun
from state.analytics_state import AnalyticsState


def state_to_chat_response(
    state: AnalyticsState,
    project_id: UUID,
    question: str,
    preview_limit: int,
) -> ChatResponse:
    sql_error = state.get("sql_error")
    status = RunStatus.FAILED if sql_error else RunStatus.SUCCEEDED
    run = Run(
        project_id=project_id,
        question=question,
        status=status,
        completed_at=datetime.now(UTC),
        sql_run=_sql_run(state),
        result_preview=_result_preview(state.get("result"), preview_limit),
        report=state.get("report"),
        artifacts=_artifacts(state),
        error=sql_error,
    )
    return ChatResponse(run=run, events=[_event(run, status)])


def _sql_run(state: AnalyticsState) -> SqlRun | None:
    sql = state.get("sql_query")
    if not sql:
        return None
    result = state.get("result")
    row_count = len(result) if isinstance(result, pd.DataFrame) else None
    return SqlRun(sql=sql, row_count=row_count, error=state.get("sql_error"))


def _result_preview(result: Any, preview_limit: int) -> ResultPreview | None:
    if not isinstance(result, pd.DataFrame):
        return None
    preview = result.head(preview_limit)
    return ResultPreview(
        columns=[str(column) for column in result.columns],
        rows=preview.to_dict(orient="records"),
        row_count=len(result),
        truncated=len(result) > preview_limit,
    )


def _artifacts(state: AnalyticsState) -> list[ArtifactRef]:
    return [artifact for artifact in state.get("artifacts", []) if isinstance(artifact, ArtifactRef)]


def _event(run: Run, status: RunStatus) -> RunEvent:
    if status == RunStatus.SUCCEEDED:
        return RunEvent(run_id=run.run_id, event_type=RunEventType.COMPLETED, message="Run completed.")
    return RunEvent(run_id=run.run_id, event_type=RunEventType.FAILED, message=run.error or "Run failed.")

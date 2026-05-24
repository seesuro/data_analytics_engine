from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class DatasetStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunEventType(StrEnum):
    STARTED = "started"
    PLANNED = "planned"
    SQL_GENERATED = "sql_generated"
    SQL_EXECUTED = "sql_executed"
    CHART_CREATED = "chart_created"
    REPORTED = "reported"
    FAILED = "failed"
    COMPLETED = "completed"


class IntentType(StrEnum):
    LIST_TABLES = "list_tables"
    DESCRIBE_TABLE = "describe_table"
    ANALYSIS = "analysis"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Project(ContractModel):
    project_id: UUID = Field(default_factory=uuid4)
    project_slug: str
    project_name: str
    created_at: datetime = Field(default_factory=utc_now)
    path: Path

    @field_validator("project_slug")
    @classmethod
    def validate_project_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Project slug cannot be empty.")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(char not in allowed for char in normalized):
            raise ValueError("Project slug may only contain lowercase letters, numbers, and hyphens.")
        return normalized


class Dataset(ContractModel):
    dataset_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    source_filename: str
    content_hash: str
    raw_path: Path
    status: DatasetStatus = DatasetStatus.PENDING
    uploaded_at: datetime = Field(default_factory=utc_now)
    table_name: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    error: str | None = None


class SqlRun(ContractModel):
    sql: str
    row_count: int | None = Field(default=None, ge=0)
    error: str | None = None

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SQL cannot be empty.")
        return stripped


class SqlCandidate(ContractModel):
    sql: str
    rationale: str | None = None

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SQL cannot be empty.")
        return stripped


class ResultPreview(ContractModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int | None = Field(default=None, ge=0)
    truncated: bool = False


class ArtifactRef(ContractModel):
    artifact_id: UUID = Field(default_factory=uuid4)
    artifact_type: str
    path: Path
    mime_type: str | None = None


class Run(ContractModel):
    run_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    question: str
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    sql_run: SqlRun | None = None
    result_preview: ResultPreview | None = None
    report: str | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: str | None = None


class RunEvent(ContractModel):
    run_id: UUID
    event_type: RunEventType
    message: str
    created_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(ContractModel):
    project_id: UUID
    message: str
    preview_limit: int = Field(default=50, ge=1, le=500)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message cannot be empty.")
        return stripped


class ChatResponse(ContractModel):
    run: Run
    events: list[RunEvent] = Field(default_factory=list)


class IntentDecision(ContractModel):
    intent: IntentType
    table_name: str | None = None

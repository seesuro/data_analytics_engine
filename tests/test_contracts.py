from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from contracts import (
    ArtifactRef,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    CleaningAction,
    CleaningActionStatus,
    CleaningActionType,
    CleaningFlow,
    CleaningFlowStatus,
    Dataset,
    DatasetStatus,
    IntentDecision,
    IntentType,
    Project,
    ResultPreview,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    SqlCandidate,
    SqlRun,
    ToolCall,
    ToolName,
    ToolResult,
)


def test_project_normalizes_slug_and_generates_uuid(tmp_path):
    project = Project(project_slug=" Retail-Demo ", project_name="Retail Demo", path=tmp_path)

    assert isinstance(project.project_id, UUID)
    assert project.project_slug == "retail-demo"
    assert project.project_name == "Retail Demo"
    assert project.path == tmp_path


def test_project_rejects_invalid_slug(tmp_path):
    with pytest.raises(ValidationError):
        Project(project_slug="Retail Demo!", project_name="Retail Demo", path=tmp_path)


def test_dataset_defaults_and_status(tmp_path):
    project_id = uuid4()
    dataset = Dataset(
        project_id=project_id,
        source_filename="sales.csv",
        content_hash="abc123",
        raw_path=tmp_path / "raw" / "sales.csv",
    )

    assert dataset.project_id == project_id
    assert dataset.status == DatasetStatus.PENDING
    assert dataset.table_name is None
    assert dataset.row_count is None

    dataset.status = DatasetStatus.READY
    dataset.row_count = 10
    assert dataset.status == DatasetStatus.READY
    assert dataset.row_count == 10


def test_sql_run_strips_and_rejects_empty_sql():
    sql_run = SqlRun(sql="  SELECT 1  ", row_count=1)
    assert sql_run.sql == "SELECT 1"
    assert sql_run.row_count == 1

    with pytest.raises(ValidationError):
        SqlRun(sql="   ")


def test_sql_candidate_strips_sql_and_keeps_rationale():
    candidate = SqlCandidate(sql="  SELECT 1  ", rationale="constant projection")

    assert candidate.sql == "SELECT 1"
    assert candidate.rationale == "constant projection"

    with pytest.raises(ValidationError):
        SqlCandidate(sql="")


def test_tool_contracts_and_chat_message_validation():
    project_id = uuid4()
    tool_call = ToolCall(tool_name=ToolName.MISSING_SUMMARY, arguments={"table_name": "sales"})
    tool_result = ToolResult(tool_name=ToolName.MISSING_SUMMARY, result={"columns": []})
    message = ChatMessage(project_id=project_id, role=ChatRole.USER, content="  show missing values  ")

    assert tool_call.tool_name == ToolName.MISSING_SUMMARY
    assert tool_result.result == {"columns": []}
    assert message.content == "show missing values"

    with pytest.raises(ValidationError):
        ChatMessage(project_id=project_id, role=ChatRole.USER, content="")


def test_cleaning_flow_and_action_contracts():
    project_id = uuid4()
    flow = CleaningFlow(
        project_id=project_id,
        source_table="  sales  ",
        draft_table="sales_draft_abcd",
    )
    action = CleaningAction(
        flow_id=flow.flow_id,
        action_type=CleaningActionType.DROP_DUPLICATES,
        arguments={"subset": ["order_id"]},
        before_summary={"row_count": 10},
        after_summary={"row_count": 9},
    )

    assert flow.source_table == "sales"
    assert flow.status == CleaningFlowStatus.DRAFT
    assert action.status == CleaningActionStatus.SUCCEEDED
    assert action.arguments == {"subset": ["order_id"]}

    with pytest.raises(ValidationError):
        CleaningFlow(project_id=project_id, source_table="", draft_table="draft")


def test_chat_request_validates_message_and_preview_limit():
    project_id = uuid4()
    request = ChatRequest(project_id=project_id, message="  total revenue  ", preview_limit=25)

    assert request.project_id == project_id
    assert request.message == "total revenue"
    assert request.preview_limit == 25

    with pytest.raises(ValidationError):
        ChatRequest(project_id=project_id, message="")

    with pytest.raises(ValidationError):
        ChatRequest(project_id=project_id, message="hello", preview_limit=501)


def test_run_response_serializes_nested_contracts(tmp_path):
    project_id = uuid4()
    run = Run(
        project_id=project_id,
        question="total revenue",
        status=RunStatus.SUCCEEDED,
        sql_run=SqlRun(sql="SELECT region, SUM(revenue) FROM sales GROUP BY region", row_count=2),
        tool_call=ToolCall(tool_name=ToolName.TABLE_PROFILE, arguments={"table_name": "sales"}),
        tool_result=ToolResult(tool_name=ToolName.TABLE_PROFILE, result={"row_count": 1}),
        result_preview=ResultPreview(
            columns=["region", "revenue"],
            rows=[{"region": "East", "revenue": 100}],
            row_count=2,
            truncated=True,
        ),
        report="East generated 100 in revenue.",
        artifacts=[
            ArtifactRef(
                artifact_type="chart",
                path=Path(tmp_path / "artifacts" / "chart.png"),
                mime_type="image/png",
            )
        ],
    )
    event = RunEvent(run_id=run.run_id, event_type=RunEventType.COMPLETED, message="done")
    response = ChatResponse(run=run, events=[event])

    dumped = response.model_dump(mode="json")

    assert dumped["run"]["status"] == "succeeded"
    assert dumped["events"][0]["event_type"] == "completed"
    assert dumped["run"]["tool_call"]["tool_name"] == "table_profile"
    assert dumped["run"]["artifacts"][0]["mime_type"] == "image/png"


def test_contracts_forbid_extra_fields(tmp_path):
    with pytest.raises(ValidationError):
        Project(project_slug="demo", project_name="Demo", path=tmp_path, unknown=True)


def test_intent_decision_contract():
    decision = IntentDecision(intent=IntentType.DESCRIBE_TABLE, table_name="sales")

    assert decision.intent == IntentType.DESCRIBE_TABLE
    assert decision.table_name == "sales"

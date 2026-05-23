from uuid import uuid4

import pandas as pd

from engine.run_mapper import state_to_chat_response


def test_state_to_chat_response_builds_successful_run_with_preview():
    project_id = uuid4()
    state = {
        "sql_query": "SELECT * FROM sales LIMIT 500",
        "result": pd.DataFrame({"region": ["East", "West"], "revenue": [100, 200]}),
        "report": "Done.",
        "artifacts": [],
    }

    response = state_to_chat_response(state, project_id, "question", preview_limit=1)

    assert response.run.project_id == project_id
    assert response.run.status == "succeeded"
    assert response.run.sql_run.sql == "SELECT * FROM sales LIMIT 500"
    assert response.run.result_preview.columns == ["region", "revenue"]
    assert response.run.result_preview.rows == [{"region": "East", "revenue": 100}]
    assert response.run.result_preview.row_count == 2
    assert response.run.result_preview.truncated is True
    assert response.events[0].event_type == "completed"


def test_state_to_chat_response_builds_failed_run():
    project_id = uuid4()
    state = {"sql_query": "DROP TABLE sales", "result": None, "sql_error": "Only SELECT queries are allowed."}

    response = state_to_chat_response(state, project_id, "question", preview_limit=50)

    assert response.run.status == "failed"
    assert response.run.error == "Only SELECT queries are allowed."
    assert response.run.result_preview is None
    assert response.events[0].event_type == "failed"

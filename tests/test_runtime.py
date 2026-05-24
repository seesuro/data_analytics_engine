from pathlib import Path

from engine.runtime import AnalyticsRuntime, record_artifact, runtime_from_state


def test_runtime_from_state_returns_existing_runtime():
    runtime = AnalyticsRuntime(metadata={"tables": {}})
    state = {"runtime": runtime}

    assert runtime_from_state(state) is runtime
    assert state["artifacts"] is runtime.artifacts


def test_runtime_from_state_supports_legacy_state_keys(tmp_path):
    db = object()
    llm = object()
    state = {
        "db": db,
        "metadata": {"tables": {"sales": {}}},
        "artifact_dir": str(tmp_path),
        "llm": llm,
        "artifacts": [],
    }

    runtime = runtime_from_state(state)

    assert runtime.db is db
    assert runtime.metadata == {"tables": {"sales": {}}}
    assert runtime.artifact_dir == Path(tmp_path)
    assert runtime.llm is llm


def test_record_artifact_keeps_state_and_runtime_in_sync():
    state = {"runtime": AnalyticsRuntime()}
    artifact = object()

    record_artifact(state, artifact)

    assert state["artifacts"] == [artifact]
    assert state["runtime"].artifacts == [artifact]

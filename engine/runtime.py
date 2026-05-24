from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AnalyticsRuntime:
    db: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_dir: Path | None = None
    llm: Any | None = None
    artifacts: list[Any] = field(default_factory=list)


def runtime_from_state(state: dict[str, Any]) -> AnalyticsRuntime:
    runtime = state.get("runtime")
    if isinstance(runtime, AnalyticsRuntime):
        state["artifacts"] = runtime.artifacts
        return runtime

    runtime = AnalyticsRuntime(
        db=state.get("db"),
        metadata=state.get("metadata", {}),
        artifact_dir=_coerce_artifact_dir(state.get("artifact_dir")),
        llm=state.get("llm"),
        artifacts=state.setdefault("artifacts", []),
    )
    state["runtime"] = runtime
    return runtime


def record_artifact(state: dict[str, Any], artifact: Any) -> None:
    runtime = runtime_from_state(state)
    runtime.artifacts.append(artifact)
    state["artifacts"] = runtime.artifacts


def _coerce_artifact_dir(value: Any) -> Path | None:
    if value is None:
        return None
    return Path(value)

from pathlib import Path
from typing import Any

from graph.analytics_graph import build_graph
from state.analytics_state import AnalyticsState


class AnalyticsEngine:
    def __init__(self, graph: Any | None = None):
        self.graph = graph or build_graph()

    def run(
        self,
        question: str,
        db: Any,
        metadata: dict,
        artifact_dir: str | Path | None = None,
        llm: Any | None = None,
        max_sql_repair_attempts: int = 1,
    ) -> AnalyticsState:
        state: AnalyticsState = {
            "user_query": question,
            "db": db,
            "metadata": metadata,
            "artifacts": [],
            "sql_repair_attempts": 0,
            "max_sql_repair_attempts": max_sql_repair_attempts,
        }
        if artifact_dir is not None:
            state["artifact_dir"] = str(artifact_dir)
        if llm is not None:
            state["llm"] = llm

        return self.graph.invoke(state)

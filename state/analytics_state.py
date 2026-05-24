# Analytics state implementation
from typing import TypedDict, Any


class AnalyticsState(TypedDict, total=False):
    user_query: str
    plan: str
    sql_query: str
    sql_candidate: Any
    result: Any
    report: str
    intent: str
    intent_decision: Any
    sql_error: str
    sql_repair_attempts: int
    max_sql_repair_attempts: int
    artifact_dir: str
    artifacts: list[Any]
    llm: Any
    db: Any  # DBManager instance
    metadata: dict  # Metadata dictionary

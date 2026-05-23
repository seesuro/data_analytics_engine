# Analytics state implementation
from typing import TypedDict, Any


class AnalyticsState(TypedDict, total=False):
    user_query: str
    plan: str
    sql_query: str
    result: Any
    report: str
    intent: str
    sql_error: str
    artifact_dir: str
    artifacts: list[Any]
    llm: Any
    db: Any  # DBManager instance
    metadata: dict  # Metadata dictionary

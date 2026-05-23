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
    db: Any  # DBManager instance
    metadata: dict  # Metadata dictionary

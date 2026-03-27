# Analytics state implementation
from typing import TypedDict, Any


class AnalyticsState(TypedDict):
    user_query: str
    plan: str
    sql_query: str
    result: Any

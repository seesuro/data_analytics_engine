import re


class SqlPolicyError(ValueError):
    pass


def apply_sql_policy(sql: str, row_limit: int = 500) -> str:
    normalized = _strip_trailing_semicolon(sql.strip())
    if not normalized:
        raise SqlPolicyError("SQL query cannot be empty.")
    if _has_multiple_statements(normalized):
        raise SqlPolicyError("Only one SQL statement is allowed.")
    if not _is_select_query(normalized):
        raise SqlPolicyError("Only SELECT queries are allowed.")
    if _has_top_level_limit(normalized):
        return normalized
    return f"{normalized} LIMIT {row_limit}"


def _strip_trailing_semicolon(sql: str) -> str:
    return sql[:-1].strip() if sql.endswith(";") else sql


def _has_multiple_statements(sql: str) -> bool:
    return ";" in sql


def _is_select_query(sql: str) -> bool:
    return bool(re.match(r"^\s*(select|with)\b", sql, flags=re.IGNORECASE))


def _has_top_level_limit(sql: str) -> bool:
    depth = 0
    tokens = re.findall(r"\(|\)|\blimit\b", sql, flags=re.IGNORECASE)
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(depth - 1, 0)
        elif token.lower() == "limit" and depth == 0:
            return True
    return False

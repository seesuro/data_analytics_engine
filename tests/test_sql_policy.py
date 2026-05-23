import pytest

from engine.sql_policy import SqlPolicyError, apply_sql_policy


def test_sql_policy_adds_limit_to_select():
    assert apply_sql_policy("SELECT * FROM sales", row_limit=25) == "SELECT * FROM sales LIMIT 25"


def test_sql_policy_preserves_existing_top_level_limit():
    assert apply_sql_policy("SELECT * FROM sales LIMIT 10", row_limit=25) == "SELECT * FROM sales LIMIT 10"


def test_sql_policy_allows_cte_queries():
    query = "WITH totals AS (SELECT * FROM sales) SELECT * FROM totals"
    assert apply_sql_policy(query, row_limit=5).endswith("LIMIT 5")


def test_sql_policy_ignores_nested_limit_and_adds_outer_limit():
    query = "SELECT * FROM (SELECT * FROM sales LIMIT 10) AS s"
    assert apply_sql_policy(query, row_limit=5) == f"{query} LIMIT 5"


def test_sql_policy_strips_single_trailing_semicolon():
    assert apply_sql_policy("SELECT 1;", row_limit=5) == "SELECT 1 LIMIT 5"


@pytest.mark.parametrize(
    "query,error",
    [
        ("", "cannot be empty"),
        ("DELETE FROM sales", "Only SELECT queries"),
        ("SELECT 1; SELECT 2", "Only one SQL statement"),
    ],
)
def test_sql_policy_rejects_unsafe_queries(query, error):
    with pytest.raises(SqlPolicyError, match=error):
        apply_sql_policy(query)

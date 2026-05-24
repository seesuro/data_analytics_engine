import pytest

from engine.sql_candidate import parse_sql_candidate, strip_code_fences


def test_parse_sql_candidate_from_json():
    candidate = parse_sql_candidate('{"sql": "SELECT 1", "rationale": "constant"}')

    assert candidate.sql == "SELECT 1"
    assert candidate.rationale == "constant"


def test_parse_sql_candidate_from_fenced_json():
    candidate = parse_sql_candidate('```json\n{"sql": "SELECT region FROM sales", "rationale": null}\n```')

    assert candidate.sql == "SELECT region FROM sales"
    assert candidate.rationale is None


def test_parse_sql_candidate_from_raw_sql_fallback():
    candidate = parse_sql_candidate("```sql\nSELECT * FROM sales\n```")

    assert candidate.sql == "SELECT * FROM sales"


def test_parse_sql_candidate_rejects_invalid_json_contract():
    with pytest.raises(ValueError, match="non-empty sql"):
        parse_sql_candidate('{"query": "SELECT 1"}')


def test_strip_code_fences_handles_plain_text():
    assert strip_code_fences("SELECT 1") == "SELECT 1"

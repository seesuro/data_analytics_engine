import json

from pydantic import ValidationError

from contracts import SqlCandidate


def parse_sql_candidate(raw_output: str) -> SqlCandidate:
    cleaned = strip_code_fences(raw_output.strip())
    try:
        decoded = json.loads(cleaned)
    except json.JSONDecodeError:
        return SqlCandidate(sql=cleaned)

    if not isinstance(decoded, dict):
        raise ValueError("SQL candidate JSON output must be an object.")

    try:
        return SqlCandidate.model_validate(decoded)
    except ValidationError as exc:
        raise ValueError("SQL candidate JSON output must include a non-empty sql field.") from exc


def strip_code_fences(value: str) -> str:
    cleaned = value
    if cleaned.startswith("```"):
        first_line, _, rest = cleaned.partition("\n")
        if first_line.strip().lower() in {"```", "```json", "```sql"}:
            cleaned = rest.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()
    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()
    return cleaned

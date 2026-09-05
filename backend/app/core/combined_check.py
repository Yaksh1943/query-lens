"""
Combines ambiguity-checking and SQL generation into a single LLM
call. Both jobs need the same schema payload — sending it once instead
of twice cuts real, measured token cost on every non-cached question.
"""
import json
import re
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.core.prompts import build_combined_prompt
from app.db.schema import format_schema_for_prompt
from app.llm.provider import LLMProvider, LLMResponse

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass
class CombinedCheckResult:
    is_ambiguous: bool
    clarification_question: str | None
    sql: str | None
    reasoning: str
    raw_response: LLMResponse


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


def check_ambiguity_and_generate_sql(
    question: str,
    provider: LLMProvider,
    engine: Engine,
    table_names: list[str] | None = None,
) -> CombinedCheckResult:
    schema_text = format_schema_for_prompt(engine, table_names=table_names)
    prompt = build_combined_prompt(question, schema_text)

    response = provider.complete(prompt)
    cleaned = _strip_code_fences(response.text)

    try:
        parsed = json.loads(cleaned)
        sql = parsed.get("sql")
        if sql:
            sql = _strip_code_fences(sql)
        return CombinedCheckResult(
            is_ambiguous=bool(parsed.get("is_ambiguous", False)),
            clarification_question=parsed.get("clarification_question"),
            sql=sql,
            reasoning=parsed.get("reasoning", ""),
            raw_response=response,
        )
    except (json.JSONDecodeError, AttributeError):
        # Fail toward "not ambiguous, no SQL" rather than guessing —
        # query.py treats a missing sql as a clear generation failure,
        # visible in history, not silently swallowed.
        return CombinedCheckResult(
            is_ambiguous=False,
            clarification_question=None,
            sql=None,
            reasoning=f"Failed to parse combined response: {cleaned[:200]}",
            raw_response=response,
        )
"""
Orchestrates SQL generation and answer generation by combining
prompts.py (wording) + schema.py (context) + provider.py (LLM call).

No prompt text and no vendor SDK details live here — this file only
wires the pieces together, so each piece stays independently testable.
"""
import re
from dataclasses import dataclass

from app.core.prompts import build_answer_prompt, build_sql_prompt
from app.db.schema import format_schema_for_prompt
from app.llm.provider import LLMProvider, LLMResponse


@dataclass
class GeneratedSQL:
    sql: str
    raw_response: LLMResponse


@dataclass
class GeneratedAnswer:
    text: str
    raw_response: LLMResponse


_CODE_FENCE_RE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    """
    Defensive cleanup: even with explicit instructions not to, models
    sometimes wrap SQL in ```sql ... ``` fences. Strip them if present.
    """
    return _CODE_FENCE_RE.sub("", text).strip()


def generate_sql(question: str, provider: LLMProvider) -> GeneratedSQL:
    """Turns a natural-language question into a SQL query."""
    schema_text = format_schema_for_prompt()
    prompt = build_sql_prompt(question, schema_text)

    response = provider.complete(prompt)
    sql = _strip_code_fences(response.text)

    return GeneratedSQL(sql=sql, raw_response=response)


def generate_answer(
    question: str,
    sql: str,
    rows: list[dict],
    provider: LLMProvider,
) -> GeneratedAnswer:
    """Turns a question + the SQL that ran + result rows into a plain-English answer."""
    prompt = build_answer_prompt(question, sql, rows)
    response = provider.complete(prompt)
    return GeneratedAnswer(text=response.text, raw_response=response)
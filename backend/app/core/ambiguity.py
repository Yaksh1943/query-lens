"""
Detects whether a question is ambiguous — either underspecified or
mapping unclearly onto the schema — before any SQL is generated.

Takes an explicit engine (passed through to schema.py) rather than
assuming a single global database — see app.db.schema for the same
change and its rationale.

Pure orchestration, same pattern as sql_generation.py: no prompt text
and no vendor SDK details live here.
"""
import json
import re
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.core.prompts import build_ambiguity_prompt
from app.db.schema import format_schema_for_prompt
from app.llm.provider import LLMProvider, LLMResponse

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass
class AmbiguityResult:
    is_ambiguous: bool
    clarification_question: str | None
    reasoning: str
    raw_response: LLMResponse


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


def detect_ambiguity(question: str, provider: LLMProvider, engine: Engine) -> AmbiguityResult:
    """Asks the LLM whether the question is answerable unambiguously against the given database."""
    schema_text = format_schema_for_prompt(engine)
    prompt = build_ambiguity_prompt(question, schema_text)

    response = provider.complete(prompt)
    cleaned = _strip_code_fences(response.text)

    try:
        parsed = json.loads(cleaned)
        return AmbiguityResult(
            is_ambiguous=bool(parsed.get("is_ambiguous", False)),
            clarification_question=parsed.get("clarification_question"),
            reasoning=parsed.get("reasoning", ""),
            raw_response=response,
        )
    except (json.JSONDecodeError, AttributeError):
        # Fail safe: don't block the pipeline on a malformed LLM
        # response, but keep the raw text visible for debugging.
        return AmbiguityResult(
            is_ambiguous=False,
            clarification_question=None,
            reasoning=f"Failed to parse ambiguity response: {cleaned[:200]}",
            raw_response=response,
        )
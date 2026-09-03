"""
Decides whether a question needs two-stage schema retrieval, and if
so, performs stage 1 (selecting relevant tables) before the real
schema-formatting step includes only those tables' full detail.

Two-stage retrieval only pays off once a schema is large enough that
sending every table's full column detail would be expensive or
noisy. Below TABLE_COUNT_THRESHOLD, this adds a wasted LLM call for
no benefit — Chinook's 11 tables are cheap enough to send whole, so
this stage is skipped entirely for schemas that size or smaller.
"""
import json
import re
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.core.prompts import build_table_selection_prompt
from app.db.schema import format_table_list_for_prompt, get_table_summaries
from app.llm.provider import LLMProvider, LLMResponse

TABLE_COUNT_THRESHOLD = 20

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass
class TableSelectionResult:
    table_names: list[str] | None  # None means "schema small enough, use it all"
    used_selection: bool
    raw_response: LLMResponse | None


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


def select_relevant_tables(question: str, provider: LLMProvider, engine: Engine) -> TableSelectionResult:
    """
    Returns the tables relevant to a question, or a signal to use the
    full schema if it's small enough that filtering isn't worth the
    extra LLM call.
    """
    summaries = get_table_summaries(engine)

    if len(summaries) <= TABLE_COUNT_THRESHOLD:
        return TableSelectionResult(table_names=None, used_selection=False, raw_response=None)

    table_list_text = format_table_list_for_prompt(engine)
    prompt = build_table_selection_prompt(question, table_list_text)

    response = provider.complete(prompt)
    cleaned = _strip_code_fences(response.text)

    known_names = {s["name"] for s in summaries}

    try:
        selected = json.loads(cleaned)
        # Defensive: only trust names that actually exist in the schema.
        valid_selected = [name for name in selected if name in known_names]
        if not valid_selected:
            # Fail safe: an empty or garbage selection is worse than
            # using the full schema, not better.
            return TableSelectionResult(table_names=None, used_selection=False, raw_response=response)
        return TableSelectionResult(table_names=valid_selected, used_selection=True, raw_response=response)
    except (json.JSONDecodeError, TypeError):
        return TableSelectionResult(table_names=None, used_selection=False, raw_response=response)
"""
SQL Generation Agent: Generates PostgreSQL SELECT queries scoped to RAG retrieved tables & golden examples.
"""
import re
import time

from app.agents.state import AgentState
from app.core.prompts import build_rag_sql_prompt
from app.db.schema import format_schema_for_prompt
from app.llm.provider import LLMProvider
from app.observability.logger import get_logger

logger = get_logger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


class SQLAgent:
    """Specialist agent for precision SQL synthesis."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, state: AgentState) -> AgentState:
        if state.is_ambiguous or state.sql is not None:
            return state

        start = time.monotonic()
        schema_text = format_schema_for_prompt(
            state.engine,
            table_names=state.retrieved_tables if state.retrieved_tables else None,
        )

        prompt = build_rag_sql_prompt(
            question=state.question,
            schema_text=schema_text,
            golden_examples=state.golden_queries,
        )

        response = self.provider.complete(prompt)
        state.llm_responses.append(response)
        state.sql = _strip_code_fences(response.text)

        elapsed = (time.monotonic() - start) * 1000
        state.step_latencies["sql_generation_ms"] = elapsed
        logger.info("SQLAgent generated SQL in %.2fms | SQL: %s", elapsed, state.sql)
        return state

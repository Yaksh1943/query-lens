"""
Self-Healing & Reflection Agent.

Performs bounded self-correction loops when generated SQL encounters
AST validation failures or database runtime execution errors.
"""
import time

from app.agents.guard_agent import GuardAgent
from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.sql_generation import repair_sql
from app.llm.provider import LLMProvider
from app.observability.logger import get_logger

logger = get_logger(__name__)


class HealingAgent:
    """Specialist agent for error diagnosis, reflection, and SQL self-correction."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self.settings = get_settings()
        self.guard = GuardAgent()

    def run(self, state: AgentState) -> AgentState:
        if state.is_ambiguous or not self.settings.enable_self_healing or state.is_cache_hit:
            return state

        max_retries = self.settings.max_self_healing_retries

        while state.retry_count < max_retries:
            has_val_error = not state.is_valid_sql
            has_exec_error = state.execution_error is not None

            if not has_val_error and not has_exec_error:
                # Query is healthy and successfully executed
                break

            error_msg = "; ".join(state.validation_errors) if has_val_error else state.execution_error
            logger.info(
                "HealingAgent attempting reflection loop (%d/%d) on error: %s",
                state.retry_count + 1,
                max_retries,
                error_msg,
            )

            start = time.monotonic()
            state.retry_count += 1

            repaired = repair_sql(
                question=state.question,
                failed_sql=state.sql or "",
                error_message=error_msg or "Unknown error",
                provider=self.provider,
                engine=state.engine,
                table_names=state.retrieved_tables if state.retrieved_tables else None,
            )

            state.llm_responses.append(repaired.raw_response)
            state.repair_history.append({"attempt": str(state.retry_count), "error": error_msg or "", "sql": repaired.sql})
            state.sql = repaired.sql

            # Re-test with GuardAgent
            state = self.guard.run(state)

            elapsed = (time.monotonic() - start) * 1000
            state.step_latencies[f"healing_attempt_{state.retry_count}_ms"] = elapsed

            if state.is_valid_sql and state.execution_error is None:
                state.self_corrected = True
                logger.info("HealingAgent successfully repaired SQL on attempt %d!", state.retry_count)
                break

        return state

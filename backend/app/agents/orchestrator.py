"""
Production Agent Orchestrator.

Orchestrates specialized agents into a deterministic state machine:
Semantic Cache -> Intent/Ambiguity -> RAG Retrieval -> SQL Generation -> Guardrail -> Self-Healing -> Insight.
"""
import time

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.agents.guard_agent import GuardAgent
from app.agents.healing_agent import HealingAgent
from app.agents.insight_agent import InsightAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.sql_agent import SQLAgent
from app.agents.state import AgentState
from app.core.ambiguity import detect_ambiguity
from app.core.config import get_settings
from app.llm.provider import LLMProvider
from app.observability.logger import get_logger
from app.rag.semantic_cache import get_cached_semantic, save_to_semantic_cache

logger = get_logger(__name__)


class AgentOrchestrator:
    """Master workflow controller for the multi-agent Text-to-SQL & Analytics pipeline."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self.settings = get_settings()
        self.retrieval_agent = RetrievalAgent()
        self.sql_agent = SQLAgent(provider)
        self.guard_agent = GuardAgent()
        self.healing_agent = HealingAgent(provider)
        self.insight_agent = InsightAgent(provider)

    def execute_pipeline(
        self,
        question: str,
        connection_id: int | None,
        engine: Engine,
        db: Session,
        skip_ambiguity_check: bool = False,
    ) -> AgentState:
        total_start = time.monotonic()
        state = AgentState(
            question=question,
            connection_id=connection_id,
            engine=engine,
        )

        # ----------------------------------------------------
        # Stage 0: Semantic Vector Cache
        # ----------------------------------------------------
        cache_hit = get_cached_semantic(question, connection_id, db)
        if cache_hit is not None:
            state.is_cache_hit = True
            state.cache_similarity = cache_hit.similarity
            entry = cache_hit.entry

            if entry.is_ambiguous:
                state.is_ambiguous = True
                state.clarification_question = entry.clarification_question
                state.step_latencies["total_pipeline_ms"] = (time.monotonic() - total_start) * 1000
                logger.info("Semantic cache returned cached clarification question")
                return state

            if entry.sql:
                state.sql = entry.sql
                logger.info("Serving query from semantic cache (similarity=%.3f)", cache_hit.similarity)
                # Execute fresh (guarantees real-time data freshness)
                state = self.guard_agent.run(state)
                if state.is_valid_sql and state.execution_error is None:
                    state = self.insight_agent.run(state)
                    state.step_latencies["total_pipeline_ms"] = (time.monotonic() - total_start) * 1000
                    return state

        # ----------------------------------------------------
        # Stage 1: Intent & Ambiguity Verification
        # ----------------------------------------------------
        if not skip_ambiguity_check:
            amb_start = time.monotonic()
            amb_res = detect_ambiguity(question, self.provider, engine)
            state.llm_responses.append(amb_res.raw_response)
            state.step_latencies["ambiguity_check_ms"] = (time.monotonic() - amb_start) * 1000

            if amb_res.is_ambiguous:
                state.is_ambiguous = True
                state.clarification_question = amb_res.clarification_question
                save_to_semantic_cache(
                    question=question,
                    connection_id=connection_id,
                    db=db,
                    is_ambiguous=True,
                    clarification_question=amb_res.clarification_question,
                )
                state.step_latencies["total_pipeline_ms"] = (time.monotonic() - total_start) * 1000
                return state

        # ----------------------------------------------------
        # Stage 2: RAG Schema Linking & Few-Shot Retrieval
        # ----------------------------------------------------
        state = self.retrieval_agent.run(state)

        # ----------------------------------------------------
        # Stage 3: SQL Generation Specialist
        # ----------------------------------------------------
        state = self.sql_agent.run(state)

        # ----------------------------------------------------
        # Stage 4: Deterministic Guardrail (AST & DB Execution)
        # ----------------------------------------------------
        state = self.guard_agent.run(state)

        # ----------------------------------------------------
        # Stage 5: Self-Healing & Reflection (if errors exist)
        # ----------------------------------------------------
        if not state.is_valid_sql or state.execution_error is not None:
            state = self.healing_agent.run(state)

        # ----------------------------------------------------
        # Stage 6: Insight Synthesis & Auto-Chart Recommendation
        # ----------------------------------------------------
        if state.is_valid_sql and state.execution_error is None:
            state = self.insight_agent.run(state)
            # Save successful execution to semantic cache
            save_to_semantic_cache(
                question=question,
                connection_id=connection_id,
                db=db,
                sql=state.sql,
                is_ambiguous=False,
            )

        state.step_latencies["total_pipeline_ms"] = (time.monotonic() - total_start) * 1000
        logger.info(
            "Agent pipeline completed in %.1fms | valid=%s | self_corrected=%s | cache_hit=%s",
            state.step_latencies["total_pipeline_ms"],
            state.is_valid_sql,
            state.self_corrected,
            state.is_cache_hit,
        )
        return state

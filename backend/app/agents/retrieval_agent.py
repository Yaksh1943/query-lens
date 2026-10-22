"""
Retrieval Agent: Scopes database schema and extracts golden few-shot queries using Hybrid RAG.
"""
import time

from app.agents.state import AgentState
from app.core.config import get_settings
from app.db.schema import get_schema_snapshot
from app.observability.logger import get_logger
from app.rag.retriever import SchemaRetriever

logger = get_logger(__name__)


class RetrievalAgent:
    """Specialist agent for Schema Linking and Few-Shot Example Retrieval."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def run(self, state: AgentState) -> AgentState:
        start = time.monotonic()
        snapshot = get_schema_snapshot(state.engine)
        total_tables = len(snapshot)

        # For very small schemas (<= 12 tables like default Chinook), full schema is cheap,
        # but few-shot golden examples are still valuable for complex queries.
        if self.settings.enable_schema_rag:
            try:
                retriever = SchemaRetriever(state.engine)
                # If total tables > 15, we strictly prune tables; otherwise we retain all tables
                # while injecting the most relevant few-shot golden queries.
                top_k = self.settings.rag_top_k_tables if total_tables > 15 else total_tables
                res = retriever.retrieve(state.question, top_k_tables=top_k)

                state.retrieved_tables = res.table_names if total_tables > 15 else list(snapshot.keys())
                state.golden_queries = res.golden_queries
                state.retrieval_ms = res.retrieval_ms
            except Exception as e:
                logger.warning("RetrievalAgent error, falling back to full schema: %s", e)
                state.retrieved_tables = list(snapshot.keys())
        else:
            state.retrieved_tables = list(snapshot.keys())

        elapsed = (time.monotonic() - start) * 1000
        state.step_latencies["retrieval_ms"] = elapsed
        return state

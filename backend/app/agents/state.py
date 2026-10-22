"""
AgentState represents the execution context flowing through the specialized agents.
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.engine import Engine

from app.llm.provider import LLMResponse


@dataclass
class AgentState:
    """Carries inputs, intermediate reasoning, RAG context, and results across agents."""

    question: str
    connection_id: int | None
    engine: Engine
    trace_id: int | None = None

    # Routing & Ambiguity
    is_ambiguous: bool = False
    clarification_question: str | None = None
    is_cache_hit: bool = False
    cache_similarity: float = 0.0

    # RAG Retrieval
    retrieved_tables: list[str] = field(default_factory=list)
    golden_queries: list[dict[str, str]] = field(default_factory=list)
    retrieval_ms: float = 0.0

    # SQL Generation & AST Validation
    sql: str | None = None
    is_valid_sql: bool = False
    validation_errors: list[str] = field(default_factory=list)

    # Self-Healing & Reflection
    self_corrected: bool = False
    retry_count: int = 0
    repair_history: list[dict[str, str]] = field(default_factory=list)

    # Execution & Results
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    execution_ms: float = 0.0
    execution_error: str | None = None

    # Synthesis & Analytics
    answer: str | None = None
    chart_recommendation: dict[str, Any] | None = None

    # Observability & Tokens
    step_latencies: dict[str, float] = field(default_factory=dict)
    llm_responses: list[LLMResponse] = field(default_factory=list)

"""
GET /api/stats — aggregate usage metrics from query_history.

Pure SQL aggregation, no LLM calls — cheap enough to call on every
page load. Surfaces real usage data (not the eval harness's
synthetic on/off comparison, which lives in eval/report.md) so the
frontend can show how the deployed system is actually performing.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import QueryHistory
from app.db.session import get_db

router = APIRouter()


class StatsResponse(BaseModel):
    total_queries: int
    successful_queries: int
    success_rate: float
    ambiguous_queries: int
    ambiguity_rate: float
    avg_execution_ms: float
    avg_input_tokens: float
    avg_output_tokens: float
    total_tokens_used: int


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    total_queries = db.scalar(select(func.count(QueryHistory.id))) or 0

    if total_queries == 0:
        return StatsResponse(
            total_queries=0,
            successful_queries=0,
            success_rate=0.0,
            ambiguous_queries=0,
            ambiguity_rate=0.0,
            avg_execution_ms=0.0,
            avg_input_tokens=0.0,
            avg_output_tokens=0.0,
            total_tokens_used=0,
        )

    successful_queries = db.scalar(
        select(func.count(QueryHistory.id)).where(QueryHistory.success.is_(True))
    ) or 0

    ambiguous_queries = db.scalar(
        select(func.count(QueryHistory.id)).where(QueryHistory.clarification_question.is_not(None))
    ) or 0

    avg_execution_ms = db.scalar(select(func.avg(QueryHistory.execution_ms))) or 0.0

    avg_input_tokens = db.scalar(select(func.avg(QueryHistory.input_tokens))) or 0.0
    avg_output_tokens = db.scalar(select(func.avg(QueryHistory.output_tokens))) or 0.0

    total_input = db.scalar(select(func.sum(QueryHistory.input_tokens))) or 0
    total_output = db.scalar(select(func.sum(QueryHistory.output_tokens))) or 0

    return StatsResponse(
        total_queries=total_queries,
        successful_queries=successful_queries,
        success_rate=successful_queries / total_queries,
        ambiguous_queries=ambiguous_queries,
        ambiguity_rate=ambiguous_queries / total_queries,
        avg_execution_ms=float(avg_execution_ms),
        avg_input_tokens=float(avg_input_tokens),
        avg_output_tokens=float(avg_output_tokens),
        total_tokens_used=int(total_input + total_output),
    )
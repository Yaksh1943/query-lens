"""
POST /api/query — the full Text-to-SQL pipeline in one endpoint.

Flow: generate SQL -> validate -> execute -> generate answer -> save
history -> return response. Validation/execution failures are not
server errors — they're the system correctly catching bad input, so
they return 200 with success=False, not a 500.
"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.sql_generation import generate_answer, generate_sql
from app.core.sql_validation import validate_sql
from app.db.analytics import execute_query
from app.db.models import QueryHistory
from app.db.schema import get_schema_snapshot
from app.db.session import get_db
from app.llm.provider import GeminiProvider

router = APIRouter()
settings = get_settings()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    trace_id: int
    sql: str
    success: bool
    result: dict
    answer: str | None
    errors: list[str] = []


def _sample_rows(rows: list[dict], limit: int = 3) -> list[dict]:
    return rows[:limit]


@router.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    provider = GeminiProvider(api_key=settings.gemini_api_key)

    # 1. Generate SQL
    generated = generate_sql(request.question, provider)

    # 2. Validate
    schema = get_schema_snapshot()
    validation = validate_sql(generated.sql, schema)

    if not validation.is_valid:
        history = QueryHistory(
            question=request.question,
            generated_sql=generated.sql,
            result_summary=None,
            answer=None,
            success=False,
            error="; ".join(validation.errors),
            execution_ms=0.0,
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        return QueryResponse(
            trace_id=history.id,
            sql=generated.sql,
            success=False,
            result={},
            answer=None,
            errors=validation.errors,
        )

    # 3. Execute
    query_result = execute_query(validation.sql)

    if not query_result.success:
        history = QueryHistory(
            question=request.question,
            generated_sql=validation.sql,
            result_summary=None,
            answer=None,
            success=False,
            error=query_result.error,
            execution_ms=query_result.execution_ms,
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        return QueryResponse(
            trace_id=history.id,
            sql=validation.sql,
            success=False,
            result={},
            answer=None,
            errors=[query_result.error or "Query execution failed."],
        )

    # 4. Generate natural-language answer
    answer = generate_answer(request.question, validation.sql, query_result.rows, provider)

    # 5. Save history
    result_summary = json.dumps(
        {"row_count": query_result.row_count, "sample_rows": _sample_rows(query_result.rows)},
        default=str,  # handles Decimal, datetime, etc.
    )

    history = QueryHistory(
        question=request.question,
        generated_sql=validation.sql,
        result_summary=result_summary,
        answer=answer,
        success=True,
        error=None,
        execution_ms=query_result.execution_ms,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    # 6. Return
    return QueryResponse(
        trace_id=history.id,
        sql=validation.sql,
        success=True,
        result={
            "columns": query_result.columns,
            "rows": query_result.rows,
            "row_count": query_result.row_count,
        },
        answer=answer,
        errors=[],
    )
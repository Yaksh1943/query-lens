"""
POST /api/query — the full Text-to-SQL pipeline in one endpoint.

Flow: resolve the target database -> check cache -> (if miss) check
ambiguity -> select relevant tables (large schemas only) -> generate
SQL -> validate -> execute -> generate answer -> save history ->
return response. Ambiguity and validation/execution failures are not
server errors — they're the system correctly catching bad input, so
they return 200 with success=False, not a 500.

Caching: a cache hit skips the ambiguity check, table selection, and
SQL generation LLM calls — the query is still always re-executed
fresh and the answer always regenerated from live data, so a cache
hit can never return stale or incorrect information. See
app.core.query_cache for the exact-match cache itself and its stated
limitations (no semantic matching).

Multi-database support: connection_id selects which database to
query. None (the default) means the original built-in Chinook
database from .env — see app.db.connection_manager for the
resolution logic and caching. Every downstream call that touches the
database receives the resolved engine explicitly rather than
assuming a single global one.

Schema scaling: for databases with more tables than
schema_selection.TABLE_COUNT_THRESHOLD, a cheap first LLM call
narrows down to relevant tables before the real SQL-generation prompt
includes their full column detail — see app.core.schema_selection.

Follow-up flow: if trace_id + clarification_answer are given, the
original question (and its connection_id) is looked up from history,
merged with the answer, and run through the pipeline starting at
table selection / SQL generation — the ambiguity check and cache
lookup are both skipped on this pass, since a merged follow-up
question is unlikely to be a repeat and skipping avoids an infinite
loop either way.

Token usage from every LLM call actually made on a request is summed
and saved to history, so real usage — including the drop from cache
hits — can be reported via /api/stats.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.ambiguity import detect_ambiguity
from app.core.config import get_settings
from app.core.query_cache import get_cached, save_to_cache
from app.core.schema_selection import select_relevant_tables
from app.core.sql_generation import generate_answer, generate_sql
from app.core.sql_validation import validate_sql
from app.db.analytics import execute_query
from app.db.connection_manager import get_engine_for_connection
from app.db.models import QueryHistory
from app.db.schema import get_schema_snapshot
from app.db.session import get_db
from app.llm.provider import GeminiProvider, LLMResponse

router = APIRouter()
settings = get_settings()


class QueryRequest(BaseModel):
    question: str | None = None
    trace_id: int | None = None
    clarification_answer: str | None = None
    connection_id: int | None = None


class QueryResponse(BaseModel):
    trace_id: int
    sql: str | None
    success: bool
    result: dict
    answer: str | None
    clarification_question: str | None = None
    errors: list[str] = []


def _sample_rows(rows: list[dict], limit: int = 3) -> list[dict]:
    return rows[:limit]


def _sum_tokens(responses: list[LLMResponse]) -> tuple[int, int]:
    """Sums input/output tokens across every LLM call made on this request."""
    return (
        sum(r.input_tokens for r in responses),
        sum(r.output_tokens for r in responses),
    )


def _save_history(
    db: Session,
    *,
    question: str,
    generated_sql: str,
    success: bool,
    connection_id: int | None,
    result_summary: str | None = None,
    answer: str | None = None,
    clarification_question: str | None = None,
    error: str | None = None,
    execution_ms: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    served_from_cache: bool = False,
) -> QueryHistory:
    history = QueryHistory(
        question=question,
        generated_sql=generated_sql,
        result_summary=result_summary,
        answer=answer,
        clarification_question=clarification_question,
        success=success,
        error=error,
        execution_ms=execution_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        connection_id=connection_id,
        served_from_cache=served_from_cache,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def _finish_with_sql(
    question: str,
    sql: str,
    provider: GeminiProvider,
    db: Session,
    llm_responses: list[LLMResponse],
    connection_id: int | None,
    engine,
    served_from_cache: bool,
) -> QueryResponse:
    """
    Shared tail end of the pipeline: validate -> execute -> generate
    answer -> save history -> return. Used by both the cache-hit path
    (sql already known) and the cache-miss path (sql just generated).
    """
    schema = get_schema_snapshot(engine)
    validation = validate_sql(sql, schema)

    if not validation.is_valid:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        history = _save_history(
            db,
            question=question,
            generated_sql=sql,
            success=False,
            connection_id=connection_id,
            error="; ".join(validation.errors),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            served_from_cache=served_from_cache,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=sql,
            success=False,
            result={},
            answer=None,
            errors=validation.errors,
        )

    query_result = execute_query(validation.sql, engine)

    if not query_result.success:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        history = _save_history(
            db,
            question=question,
            generated_sql=validation.sql,
            success=False,
            connection_id=connection_id,
            error=query_result.error,
            execution_ms=query_result.execution_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            served_from_cache=served_from_cache,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=validation.sql,
            success=False,
            result={},
            answer=None,
            errors=[query_result.error or "Query execution failed."],
        )

    generated_answer = generate_answer(question, validation.sql, query_result.rows, provider)
    llm_responses.append(generated_answer.raw_response)

    result_summary = json.dumps(
        {"row_count": query_result.row_count, "sample_rows": _sample_rows(query_result.rows)},
        default=str,
    )

    input_tokens, output_tokens = _sum_tokens(llm_responses)

    history = _save_history(
        db,
        question=question,
        generated_sql=validation.sql,
        success=True,
        connection_id=connection_id,
        result_summary=result_summary,
        answer=generated_answer.text,
        execution_ms=query_result.execution_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        served_from_cache=served_from_cache,
    )

    if not served_from_cache:
        save_to_cache(question, connection_id, db, sql=validation.sql, is_ambiguous=False)

    return QueryResponse(
        trace_id=history.id,
        sql=validation.sql,
        success=True,
        result={
            "columns": query_result.columns,
            "rows": query_result.rows,
            "row_count": query_result.row_count,
        },
        answer=generated_answer.text,
        errors=[],
    )


def _run_pipeline_no_ambiguity_check(
    question: str,
    provider: GeminiProvider,
    db: Session,
    llm_responses: list[LLMResponse],
    connection_id: int | None,
    engine,
) -> QueryResponse:
    """Table selection -> SQL generation, then the shared validate/execute/answer tail. Used by follow-ups."""
    selection = select_relevant_tables(question, provider, engine)
    if selection.raw_response is not None:
        llm_responses.append(selection.raw_response)

    generated = generate_sql(question, provider, engine, table_names=selection.table_names)
    llm_responses.append(generated.raw_response)

    return _finish_with_sql(
        question, generated.sql, provider, db, llm_responses, connection_id, engine, served_from_cache=False
    )


@router.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    provider = GeminiProvider(api_key=settings.gemini_api_key)

    is_followup = request.trace_id is not None or request.clarification_answer is not None

    if is_followup:
        if request.trace_id is None or request.clarification_answer is None:
            raise HTTPException(
                status_code=400,
                detail="Both trace_id and clarification_answer are required for a follow-up.",
            )

        original = db.get(QueryHistory, request.trace_id)
        if original is None:
            raise HTTPException(
                status_code=404,
                detail=f"No query history found for trace_id {request.trace_id}.",
            )

        connection_id = original.connection_id
        engine = get_engine_for_connection(connection_id, db)

        merged_question = f"{original.question} (Clarification: {request.clarification_answer})"
        return _run_pipeline_no_ambiguity_check(
            merged_question, provider, db, llm_responses=[], connection_id=connection_id, engine=engine
        )

    if not request.question:
        raise HTTPException(status_code=400, detail="question is required.")

    connection_id = request.connection_id
    engine = get_engine_for_connection(connection_id, db)

    # Check cache before spending anything on the LLM.
    cached = get_cached(request.question, connection_id, db)

    if cached is not None:
        if cached.is_ambiguous:
            history = _save_history(
                db,
                question=request.question,
                generated_sql="",
                success=False,
                connection_id=connection_id,
                clarification_question=cached.clarification_question,
                served_from_cache=True,
            )
            return QueryResponse(
                trace_id=history.id,
                sql=None,
                success=False,
                result={},
                answer=None,
                clarification_question=cached.clarification_question,
                errors=[],
            )

        if cached.sql:
            return _finish_with_sql(
                request.question, cached.sql, provider, db, llm_responses=[],
                connection_id=connection_id, engine=engine, served_from_cache=True,
            )

    # Cache miss: check ambiguity first, same as before.
    ambiguity = detect_ambiguity(request.question, provider, engine)
    llm_responses = [ambiguity.raw_response]

    if ambiguity.is_ambiguous:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        history = _save_history(
            db,
            question=request.question,
            generated_sql="",
            success=False,
            connection_id=connection_id,
            clarification_question=ambiguity.clarification_question,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        save_to_cache(
            request.question, connection_id, db,
            is_ambiguous=True, clarification_question=ambiguity.clarification_question,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=None,
            success=False,
            result={},
            answer=None,
            clarification_question=ambiguity.clarification_question,
            errors=[],
        )

    return _run_pipeline_no_ambiguity_check(
        request.question, provider, db, llm_responses, connection_id=connection_id, engine=engine
    )
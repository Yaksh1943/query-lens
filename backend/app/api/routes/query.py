"""
POST /api/query — the Text-to-SQL pipeline: resolve database ->
check cache -> select tables -> check ambiguity + generate SQL (one
combined call) -> validate -> execute -> generate answer -> save
history.

The ambiguity check and SQL generation used to be two separate LLM
calls, each sending the full schema — see app.core.combined_check for
the single-call version that halves that duplicated cost. The eval
harness (eval/run_eval.py) still measures the old two-call flow in
isolation to score ambiguity-detection accuracy on its own; it has
not been updated to reflect this combined flow yet — a known gap.

See app.core.query_cache, app.core.schema_selection, and
app.db.connection_manager for the caching, schema-scaling, and
multi-database logic this route orchestrates.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.core.combined_check import check_ambiguity_and_generate_sql
from app.core.config import get_settings
from app.core.query_cache import get_cached, save_to_cache
from app.core.schema_selection import select_relevant_tables
from app.core.sql_generation import generate_answer, generate_sql, repair_sql
from app.core.sql_validation import validate_sql
from app.db.analytics import execute_query
from app.db.connection_manager import get_engine_for_connection
from app.db.models import QueryHistory
from app.db.schema import get_schema_snapshot
from app.db.session import get_db
from app.llm.provider import LLMProvider, LLMResponse, get_llm_provider
from app.observability.logger import get_logger

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)


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
    self_corrected: bool = False
    chart_recommendation: dict | None = None
    retrieved_tables: list[str] = []


def _sample_rows(rows: list[dict], limit: int = 3) -> list[dict]:
    return rows[:limit]


def _sum_tokens(responses: list[LLMResponse]) -> tuple[int, int]:
    return (
        sum(r.input_tokens for r in responses),
        sum(r.output_tokens for r in responses),
    )


def _short(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


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
    self_corrected: bool = False,
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
        self_corrected=self_corrected,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def _finish_with_sql(
    question: str,
    sql: str,
    provider: LLMProvider,
    db: Session,
    llm_responses: list[LLMResponse],
    connection_id: int | None,
    engine,
    served_from_cache: bool,
    table_names: list[str] | None = None,
) -> QueryResponse:
    """Validate -> execute -> generate answer -> save history. Shared by cache-hit and cache-miss paths."""
    schema = get_schema_snapshot(engine)
    validation = validate_sql(sql, schema)
    self_corrected = False

    # Self-Correction Step 1: Repair validation failure (AST, missing column/table, etc.)
    if not validation.is_valid and settings.enable_self_healing and not served_from_cache:
        logger.info("Attempting SQL self-correction after validation failure: %s", "; ".join(validation.errors))
        repair = repair_sql(
            question=question,
            failed_sql=sql,
            error_message="; ".join(validation.errors),
            provider=provider,
            engine=engine,
            table_names=table_names,
        )
        llm_responses.append(repair.raw_response)
        repaired_val = validate_sql(repair.sql, schema)
        if repaired_val.is_valid:
            logger.info("Self-correction succeeded at validation stage! Repaired SQL: %s", repaired_val.sql)
            sql = repaired_val.sql
            validation = repaired_val
            self_corrected = True
        else:
            validation = repaired_val

    if not validation.is_valid:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        logger.warning("Validation failed: %s | question=%s", "; ".join(validation.errors), _short(question))
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
            self_corrected=self_corrected,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=sql,
            success=False,
            result={},
            answer=None,
            errors=validation.errors,
            self_corrected=self_corrected,
        )

    query_result = execute_query(validation.sql, engine)

    # Self-Correction Step 2: Repair runtime database execution failure (e.g. GROUP BY mismatch, division by zero)
    if not query_result.success and settings.enable_self_healing and not served_from_cache and not self_corrected:
        logger.info("Attempting SQL self-correction after database execution error: %s", query_result.error)
        repair = repair_sql(
            question=question,
            failed_sql=validation.sql,
            error_message=query_result.error or "Execution error",
            provider=provider,
            engine=engine,
            table_names=table_names,
        )
        llm_responses.append(repair.raw_response)
        repaired_val = validate_sql(repair.sql, schema)
        if repaired_val.is_valid:
            repaired_res = execute_query(repaired_val.sql, engine)
            if repaired_res.success:
                logger.info("Self-correction succeeded at database execution stage!")
                validation = repaired_val
                query_result = repaired_res
                self_corrected = True

    if not query_result.success:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        logger.warning("Execution failed: %s | question=%s", query_result.error, _short(question))
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
            self_corrected=self_corrected,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=validation.sql,
            success=False,
            result={},
            answer=None,
            errors=[query_result.error or "Query execution failed."],
            self_corrected=self_corrected,
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
        self_corrected=self_corrected,
    )

    if not served_from_cache:
        save_to_cache(question, connection_id, db, sql=validation.sql, is_ambiguous=False)

    logger.info(
        "Query succeeded | cache=%s | self_corrected=%s | tokens=%d | exec_ms=%.0f | question=%s",
        served_from_cache, self_corrected, input_tokens + output_tokens, query_result.execution_ms, _short(question),
    )

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
        self_corrected=self_corrected,
    )


def _run_followup_pipeline(
    question: str,
    provider: LLMProvider,
    db: Session,
    connection_id: int | None,
    engine,
) -> QueryResponse:
    """
    Follow-ups skip the ambiguity check (the user just answered one) —
    table selection -> SQL generation only, then the shared tail.
    """
    llm_responses: list[LLMResponse] = []

    selection = select_relevant_tables(question, provider, engine)
    if selection.raw_response is not None:
        llm_responses.append(selection.raw_response)
        logger.info("Table selection engaged | selected=%s", selection.table_names)

    generated = generate_sql(question, provider, engine, table_names=selection.table_names)
    llm_responses.append(generated.raw_response)

    return _finish_with_sql(
        question,
        generated.sql,
        provider,
        db,
        llm_responses,
        connection_id,
        engine,
        served_from_cache=False,
        table_names=selection.table_names,
    )


def _execute_agentic_pipeline(
    question: str,
    connection_id: int | None,
    engine,
    db: Session,
    provider: LLMProvider,
    skip_ambiguity_check: bool = False,
) -> QueryResponse:
    orchestrator = AgentOrchestrator(provider)
    state = orchestrator.execute_pipeline(
        question=question,
        connection_id=connection_id,
        engine=engine,
        db=db,
        skip_ambiguity_check=skip_ambiguity_check,
    )

    input_tokens, output_tokens = _sum_tokens(state.llm_responses)
    result_summary = (
        json.dumps(
            {"row_count": state.row_count, "sample_rows": _sample_rows(state.rows)},
            default=str,
        )
        if state.rows or state.is_valid_sql
        else None
    )

    errors = []
    if state.validation_errors:
        errors.extend(state.validation_errors)
    if state.execution_error:
        errors.append(state.execution_error)

    success = state.is_valid_sql and state.execution_error is None and not state.is_ambiguous

    history = _save_history(
        db,
        question=question,
        generated_sql=state.sql or "",
        success=success,
        connection_id=connection_id,
        result_summary=result_summary,
        answer=state.answer,
        clarification_question=state.clarification_question,
        error="; ".join(errors) if errors else None,
        execution_ms=state.execution_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        served_from_cache=state.is_cache_hit,
        self_corrected=state.self_corrected,
    )

    return QueryResponse(
        trace_id=history.id,
        sql=state.sql,
        success=success,
        result={
            "columns": state.columns,
            "rows": state.rows,
            "row_count": state.row_count,
        },
        answer=state.answer,
        clarification_question=state.clarification_question,
        errors=errors,
        self_corrected=state.self_corrected,
        chart_recommendation=state.chart_recommendation,
        retrieved_tables=state.retrieved_tables,
    )


@router.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    provider = get_llm_provider(settings)

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
        logger.info("Follow-up received | trace_id=%d", request.trace_id)

        if settings.enable_agentic_pipeline:
            return _execute_agentic_pipeline(
                merged_question, connection_id, engine, db, provider, skip_ambiguity_check=True
            )
        return _run_followup_pipeline(merged_question, provider, db, connection_id=connection_id, engine=engine)

    if not request.question:
        raise HTTPException(status_code=400, detail="question is required.")

    connection_id = request.connection_id
    engine = get_engine_for_connection(connection_id, db)

    logger.info("Question received | connection_id=%s | question=%s", connection_id, _short(request.question))

    if settings.enable_agentic_pipeline:
        return _execute_agentic_pipeline(
            request.question, connection_id, engine, db, provider, skip_ambiguity_check=False
        )

    cached = get_cached(request.question, connection_id, db)

    if cached is not None:
        logger.info("Cache hit | hit_count=%d", cached.hit_count)

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

    logger.info("Cache miss")

    # Table selection (large schemas only), then one combined call for
    # both ambiguity-checking and SQL generation.
    llm_responses: list[LLMResponse] = []

    selection = select_relevant_tables(request.question, provider, engine)
    if selection.raw_response is not None:
        llm_responses.append(selection.raw_response)
        logger.info("Table selection engaged | selected=%s", selection.table_names)

    combined = check_ambiguity_and_generate_sql(
        request.question, provider, engine, table_names=selection.table_names
    )
    llm_responses.append(combined.raw_response)

    if combined.is_ambiguous:
        logger.info("Ambiguity detected")
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        history = _save_history(
            db,
            question=request.question,
            generated_sql="",
            success=False,
            connection_id=connection_id,
            clarification_question=combined.clarification_question,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        save_to_cache(
            request.question, connection_id, db,
            is_ambiguous=True, clarification_question=combined.clarification_question,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=None,
            success=False,
            result={},
            answer=None,
            clarification_question=combined.clarification_question,
            errors=[],
        )

    if not combined.sql:
        input_tokens, output_tokens = _sum_tokens(llm_responses)
        logger.warning("Combined call returned no SQL and no ambiguity flag | question=%s", _short(request.question))
        history = _save_history(
            db,
            question=request.question,
            generated_sql="",
            success=False,
            connection_id=connection_id,
            error=combined.reasoning or "Model did not return SQL.",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return QueryResponse(
            trace_id=history.id,
            sql=None,
            success=False,
            result={},
            answer=None,
            errors=[combined.reasoning or "Model did not return SQL."],
        )

    return _finish_with_sql(
        request.question,
        combined.sql,
        provider,
        db,
        llm_responses,
        connection_id=connection_id,
        engine=engine,
        served_from_cache=False,
        table_names=selection.table_names,
    )
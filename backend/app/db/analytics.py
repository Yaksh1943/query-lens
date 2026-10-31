"""
Executes validated SQL against a target analytics database.

Takes an explicit engine rather than assuming a single global
database — mirrors the same change in app.db.schema, for the same
reason: multi-database support requires every DB-touching function
to operate on a caller-provided engine, not an implicit global one.

Assumes the SQL passed in has already been checked by
app.core.sql_validation.validate_sql() — this file only runs it and
shapes the result, it does not re-validate.
"""
import time
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import analytics_engine

MAX_RESULT_ROWS = 500


@dataclass
class QueryResult:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    execution_ms: float = 0.0
    error: str | None = None


def execute_query(sql: str, engine: Engine | None = None, max_rows: int = MAX_RESULT_ROWS) -> QueryResult:
    """Runs a validated SELECT statement against the given engine (or default analytics engine)."""
    start = time.monotonic()
    target_engine = engine or analytics_engine

    try:
        with target_engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            mappings = result.mappings()
            if max_rows is not None and max_rows > 0:
                rows = [dict(r) for r in mappings.fetchmany(max_rows)]
            else:
                rows = [dict(r) for r in mappings.fetchall()]

        execution_ms = (time.monotonic() - start) * 1000

        return QueryResult(
            success=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_ms=execution_ms,
        )

    except SQLAlchemyError as e:
        execution_ms = (time.monotonic() - start) * 1000
        return QueryResult(
            success=False,
            execution_ms=execution_ms,
            error=str(e),
        )

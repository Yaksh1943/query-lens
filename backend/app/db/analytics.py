"""
Executes validated SQL against the analytics database (Chinook).

Assumes the SQL passed in has already been checked by
app.core.sql_validation.validate_sql() — this file only runs it and
shapes the result, it does not re-validate.
"""
import time
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import analytics_engine


@dataclass
class QueryResult:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    execution_ms: float = 0.0
    error: str | None = None


def execute_query(sql: str) -> QueryResult:
    """Runs a validated SELECT statement against the analytics database."""
    start = time.monotonic()

    try:
        with analytics_engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

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
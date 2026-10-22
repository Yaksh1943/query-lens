"""
Deterministic Guard & Execution Agent.

Applies AST security and schema integrity verification (sqlglot)
before allowing queries to touch the target database.
"""
import time

from app.agents.state import AgentState
from app.core.sql_validation import validate_sql
from app.db.analytics import execute_query
from app.db.schema import get_schema_snapshot
from app.observability.logger import get_logger

logger = get_logger(__name__)


class GuardAgent:
    """Validates SQL safety and executes valid queries against the target engine."""

    def run(self, state: AgentState) -> AgentState:
        if state.is_ambiguous or not state.sql:
            return state

        start = time.monotonic()
        schema = get_schema_snapshot(state.engine)
        val = validate_sql(state.sql, schema)

        state.is_valid_sql = val.is_valid
        state.validation_errors = val.errors

        if not val.is_valid:
            elapsed = (time.monotonic() - start) * 1000
            state.step_latencies["guard_validation_ms"] = elapsed
            logger.warning("GuardAgent flagged invalid SQL: %s", "; ".join(val.errors))
            return state

        # Use normalized SQL with applied LIMIT
        state.sql = val.sql

        # Execute query safely
        exec_res = execute_query(val.sql, state.engine)
        if exec_res.success:
            state.columns = exec_res.columns
            state.rows = exec_res.rows
            state.row_count = exec_res.row_count
            state.execution_ms = exec_res.execution_ms
            state.execution_error = None
        else:
            state.execution_error = exec_res.error or "Database execution failed"
            logger.warning("GuardAgent runtime execution error: %s", state.execution_error)

        elapsed = (time.monotonic() - start) * 1000
        state.step_latencies["guard_execution_ms"] = elapsed
        return state

"""
Insight & Visualization Agent.

Synthesizes data answers and automatically infers optimal visualization charts
(bar, line, pie, table) for direct rendering in frontend charts (Recharts).
"""
import time
from typing import Any

from app.agents.state import AgentState
from app.core.sql_generation import generate_answer
from app.llm.provider import LLMProvider
from app.observability.logger import get_logger

logger = get_logger(__name__)


def _infer_chart_recommendation(columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Deterministically deduces the most informative chart type based on column types and cardinality.
    Time complexity: O(C * R) where C is columns (<10) and R is sample rows (<20), execution in <0.2ms.
    """
    if not rows or not columns or len(rows) < 2:
        return None

    # Find numeric and categorical candidates
    first_row = rows[0]
    numeric_cols = []
    text_cols = []
    date_cols = []

    for col in columns:
        val = first_row.get(col)
        clow = col.lower()
        if any(d in clow for d in ("date", "month", "year", "time", "day")):
            date_cols.append(col)
        elif isinstance(val, (int, float)) or (isinstance(val, str) and val.replace(".", "", 1).isdigit()):
            numeric_cols.append(col)
        else:
            text_cols.append(col)

    if not numeric_cols:
        return None

    # Time-series -> Line Chart
    if date_cols and numeric_cols:
        return {
            "type": "line",
            "x_key": date_cols[0],
            "y_key": numeric_cols[0],
            "title": f"Trend over {date_cols[0]}",
        }

    # Small distribution (<= 6 rows) -> Pie or Bar Chart
    if text_cols and numeric_cols:
        if len(rows) <= 6:
            return {
                "type": "pie",
                "name_key": text_cols[0],
                "value_key": numeric_cols[0],
                "title": f"Distribution by {text_cols[0]}",
            }
        return {
            "type": "bar",
            "x_key": text_cols[0],
            "y_key": numeric_cols[0],
            "title": f"Comparison by {text_cols[0]}",
        }

    # Fallback to horizontal or single-metric bar
    if numeric_cols:
        return {
            "type": "bar",
            "x_key": columns[0],
            "y_key": numeric_cols[0],
            "title": f"{numeric_cols[0]} Overview",
        }

    return None


class InsightAgent:
    """Specialist agent for data interpretation and frontend chart recommendation."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, state: AgentState) -> AgentState:
        if state.is_ambiguous or not state.is_valid_sql or state.execution_error is not None:
            return state

        start = time.monotonic()

        # Generate natural language synthesis
        gen_ans = generate_answer(state.question, state.sql or "", state.rows, self.provider)
        state.llm_responses.append(gen_ans.raw_response)
        state.answer = gen_ans.text

        # Infer chart recommendation
        state.chart_recommendation = _infer_chart_recommendation(state.columns, state.rows)

        elapsed = (time.monotonic() - start) * 1000
        state.step_latencies["insight_generation_ms"] = elapsed
        return state

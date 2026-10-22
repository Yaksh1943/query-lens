"""
Unit and integration tests for specialized AI Agents (Guard, Insight, Healing, SQL).
"""
import pytest
from sqlalchemy import create_engine, text

from app.agents.guard_agent import GuardAgent
from app.agents.healing_agent import HealingAgent
from app.agents.insight_agent import _infer_chart_recommendation
from app.agents.state import AgentState
from app.llm.provider import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text
        self.call_count = 0

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            text=self.response_text,
            input_tokens=10,
            output_tokens=5,
            latency_ms=12.0,
        )


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price FLOAT, sale_date TEXT);"))
        conn.execute(text("INSERT INTO items (name, price, sale_date) VALUES ('Item A', 10.5, '2026-01-01');"))
        conn.execute(text("INSERT INTO items (name, price, sale_date) VALUES ('Item B', 25.0, '2026-02-01');"))
        conn.commit()
    return engine


def test_chart_recommendation_inference():
    # 1. Date + Numeric -> Line chart
    line_rec = _infer_chart_recommendation(
        columns=["sale_date", "total_sales"],
        rows=[
            {"sale_date": "2026-01", "total_sales": 100},
            {"sale_date": "2026-02", "total_sales": 250},
        ],
    )
    assert line_rec is not None
    assert line_rec["type"] == "line"
    assert line_rec["x_key"] == "sale_date"

    # 2. Category + Numeric (<=6 rows) -> Pie chart
    pie_rec = _infer_chart_recommendation(
        columns=["category", "count"],
        rows=[
            {"category": "Rock", "count": 50},
            {"category": "Jazz", "count": 20},
        ],
    )
    assert pie_rec is not None
    assert pie_rec["type"] == "pie"

    # 3. Category + Numeric (>6 rows) -> Bar chart
    bar_rec = _infer_chart_recommendation(
        columns=["artist", "tracks"],
        rows=[{"artist": f"Artist {i}", "tracks": i * 10} for i in range(10)],
    )
    assert bar_rec is not None
    assert bar_rec["type"] == "bar"


def test_guard_agent_valid_and_execution(memory_db):
    guard = GuardAgent()
    state = AgentState(
        question="Select all items",
        connection_id=None,
        engine=memory_db,
        sql="SELECT id, name, price FROM items",
    )

    state = guard.run(state)
    assert state.is_valid_sql is True
    assert len(state.rows) == 2
    assert state.row_count == 2
    assert "name" in state.columns


def test_guard_agent_rejects_destructive_sql(memory_db):
    guard = GuardAgent()
    state = AgentState(
        question="Drop items table",
        connection_id=None,
        engine=memory_db,
        sql="DROP TABLE items",
    )

    state = guard.run(state)
    assert state.is_valid_sql is False
    assert len(state.validation_errors) > 0


def test_healing_agent_reflection_success(memory_db):
    # LLM mock returns valid repaired SQL
    mock_provider = MockLLMProvider(response_text="SELECT id, name, price FROM items")
    healing = HealingAgent(provider=mock_provider)

    state = AgentState(
        question="Select items",
        connection_id=None,
        engine=memory_db,
        sql="SELECT invalid_col FROM items",
        is_valid_sql=False,
        validation_errors=["Column invalid_col does not exist"],
    )

    state = healing.run(state)
    assert state.self_corrected is True
    assert state.is_valid_sql is True
    assert state.retry_count == 1
    assert len(state.rows) == 2

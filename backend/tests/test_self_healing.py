from unittest.mock import MagicMock, patch

from app.core.prompts import build_sql_repair_prompt
from app.core.sql_generation import repair_sql
from app.api.routes.query import _finish_with_sql
from app.db.analytics import QueryResult
from app.llm.provider import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts_received = []

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts_received.append(prompt)
        text = self.responses.pop(0) if self.responses else "SELECT 1"
        return LLMResponse(text=text, input_tokens=50, output_tokens=20, latency_ms=10.0)


def test_build_sql_repair_prompt():
    prompt = build_sql_repair_prompt(
        question="How many customers from Brazil?",
        failed_sql="SELECT COUNT(*) FROM non_existent_table WHERE country = 'Brazil'",
        error_message="Unknown table(s): non_existent_table",
        schema_text="Table: customer\n  Columns: customer_id, country",
    )
    assert "Original question: How many customers from Brazil?" in prompt
    assert "non_existent_table" in prompt
    assert "Unknown table(s): non_existent_table" in prompt
    assert "Table: customer" in prompt


def test_repair_sql_invocation():
    mock_provider = MockProvider(["```sql\nSELECT COUNT(*) FROM customer WHERE country = 'Brazil';\n```"])
    engine = MagicMock()

    with patch("app.core.sql_generation.format_schema_for_prompt", return_value="Table: customer"):
        result = repair_sql(
            question="How many customers from Brazil?",
            failed_sql="SELECT COUNT(*) FROM customer WHERE cntry = 'Brazil'",
            error_message="Unknown column(s): cntry",
            provider=mock_provider,
            engine=engine,
        )

    assert result.sql == "SELECT COUNT(*) FROM customer WHERE country = 'Brazil';"
    assert len(mock_provider.prompts_received) == 1
    assert "cntry" in mock_provider.prompts_received[0]


def test_finish_with_sql_self_healing_validation_failure():
    """
    Tests that if initial SQL fails validation (unknown column),
    self-healing calls repair_sql, validates the repaired SQL,
    and returns a successful QueryResponse with self_corrected=True.
    """
    mock_db = MagicMock()
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 123)
    engine = MagicMock()

    sample_schema = {
        "customer": {
            "columns": [{"name": "customer_id", "type": "INTEGER", "nullable": False},
                        {"name": "country", "type": "VARCHAR", "nullable": True}],
            "primary_key": ["customer_id"],
            "foreign_keys": [],
        }
    }

    # Initial SQL has invalid column "cntry"
    initial_sql = "SELECT COUNT(*) FROM customer WHERE cntry = 'Brazil'"

    # Mock provider will return repaired SQL on the repair call, then natural language answer
    mock_provider = MockProvider([
        "SELECT COUNT(*) FROM customer WHERE country = 'Brazil'",  # repair response
        "There are 5 customers from Brazil.",                     # answer response
    ])

    query_exec_result = QueryResult(
        success=True,
        columns=["count"],
        rows=[{"count": 5}],
        row_count=1,
        execution_ms=1.5,
    )

    with patch("app.api.routes.query.get_schema_snapshot", return_value=sample_schema), \
         patch("app.api.routes.query.execute_query", return_value=query_exec_result), \
         patch("app.api.routes.query.save_to_cache"):

        response = _finish_with_sql(
            question="How many customers from Brazil?",
            sql=initial_sql,
            provider=mock_provider,
            db=mock_db,
            llm_responses=[],
            connection_id=None,
            engine=engine,
            served_from_cache=False,
        )

        assert response.success is True
        assert response.self_corrected is True
        assert "country = 'Brazil'" in response.sql
        assert response.answer == "There are 5 customers from Brazil."


def test_finish_with_sql_self_healing_execution_failure():
    """
    Tests that if initial SQL passes AST validation but fails at DB execution
    (e.g. GROUP BY mismatch), self-healing calls repair_sql, re-executes,
    and returns success with self_corrected=True.
    """
    mock_db = MagicMock()
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 123)
    engine = MagicMock()

    sample_schema = {
        "customer": {
            "columns": [{"name": "customer_id", "type": "INTEGER", "nullable": False},
                        {"name": "country", "type": "VARCHAR", "nullable": True}],
            "primary_key": ["customer_id"],
            "foreign_keys": [],
        }
    }

    valid_ast_sql = "SELECT country, COUNT(customer_id) FROM customer"  # missing GROUP BY

    # First DB execution fails; second DB execution (after repair) succeeds
    fail_exec = QueryResult(
        success=False,
        error='column "customer.country" must appear in the GROUP BY clause or be used in an aggregate function',
    )
    success_exec = QueryResult(
        success=True,
        columns=["country", "count"],
        rows=[{"country": "Brazil", "count": 5}],
        row_count=1,
        execution_ms=2.1,
    )

    mock_provider = MockProvider([
        "SELECT country, COUNT(customer_id) FROM customer GROUP BY country",  # repaired SQL
        "Here are the customer counts by country.",                            # answer
    ])

    with patch("app.api.routes.query.get_schema_snapshot", return_value=sample_schema), \
         patch("app.api.routes.query.execute_query", side_effect=[fail_exec, success_exec]), \
         patch("app.api.routes.query.save_to_cache"):

        response = _finish_with_sql(
            question="Customer counts by country?",
            sql=valid_ast_sql,
            provider=mock_provider,
            db=mock_db,
            llm_responses=[],
            connection_id=None,
            engine=engine,
            served_from_cache=False,
        )

        assert response.success is True
        assert response.self_corrected is True
        assert "GROUP BY country" in response.sql
        assert response.answer == "Here are the customer counts by country."

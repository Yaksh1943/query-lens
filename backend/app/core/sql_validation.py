"""
Validates LLM-generated SQL before it's allowed to run against the
database. Pure code, no LLM calls — this is the safety gate that
must hold even if prompt-level guardrails fail.
"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

DEFAULT_ROW_LIMIT = 200


@dataclass
class ValidationResult:
    is_valid: bool
    sql: str
    errors: list[str] = field(default_factory=list)


def validate_sql(sql: str, schema: dict) -> ValidationResult:
    """
    Validates a SQL string against the given schema snapshot
    (as returned by app.db.schema.get_schema_snapshot()).

    Checks, in order:
    - Parses as exactly one statement
    - That statement is a SELECT
    - Every referenced table exists in the schema
    - Every referenced column exists on some table in the schema, OR
      is a SELECT-clause alias defined within this query
    - Adds a LIMIT clause if one isn't present
    """
    errors: list[str] = []

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as e:
        return ValidationResult(is_valid=False, sql=sql, errors=[f"SQL failed to parse: {e}"])

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        return ValidationResult(
            is_valid=False,
            sql=sql,
            errors=[f"Expected exactly one SQL statement, found {len(statements)}."],
        )

    statement = statements[0]

    if not isinstance(statement, exp.Select):
        return ValidationResult(
            is_valid=False,
            sql=sql,
            errors=[f"Only SELECT statements are allowed, got: {statement.key.upper()}"],
        )

    known_tables = {name.lower() for name in schema.keys()}
    known_columns = {
        col["name"].lower()
        for table_info in schema.values()
        for col in table_info["columns"]
    }

    # Aliases defined in the SELECT clause (e.g. SUM(x) AS total) are
    # valid to reference elsewhere in the query (ORDER BY, HAVING),
    # even though they aren't real schema columns.
    defined_aliases = {
        alias.alias.lower()
        for alias in statement.find_all(exp.Alias)
        if alias.alias
    }

    referenced_tables = {t.name.lower() for t in statement.find_all(exp.Table)}
    unknown_tables = referenced_tables - known_tables
    if unknown_tables:
        errors.append(f"Unknown table(s): {', '.join(sorted(unknown_tables))}")

    referenced_columns = {
        c.name.lower() for c in statement.find_all(exp.Column) if c.name != "*"
    }
    unknown_columns = referenced_columns - known_columns - defined_aliases
    if unknown_columns:
        errors.append(f"Unknown column(s): {', '.join(sorted(unknown_columns))}")

    if errors:
        return ValidationResult(is_valid=False, sql=sql, errors=errors)

    if statement.args.get("limit") is None:
        statement = statement.limit(DEFAULT_ROW_LIMIT)

    final_sql = statement.sql(dialect="postgres")

    return ValidationResult(is_valid=True, sql=final_sql, errors=[])
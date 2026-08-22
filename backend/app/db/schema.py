"""
Reads the schema of the analytics database (Chinook) via SQLAlchemy
introspection and caches it for the lifetime of the server process.

Two entry points:
- get_schema_snapshot()      -> structured dict, for code that needs
                                 to reason about tables/columns (e.g.
                                 sql_validation.py)
- format_schema_for_prompt() -> compact text block, for injecting
                                 into the LLM prompt (prompts.py)
"""
from functools import lru_cache
from typing import Any

from sqlalchemy import inspect

from app.db.session import analytics_engine


@lru_cache(maxsize=1)
def get_schema_snapshot() -> dict[str, Any]:
    """
    Introspects analytics_engine once and caches the result.

    Returns a dict shaped like:
    {
        "table_name": {
            "columns": [{"name": ..., "type": ..., "nullable": ...}, ...],
            "primary_key": ["col1", ...],
            "foreign_keys": [{"column": ..., "references_table": ..., "references_column": ...}, ...],
        },
        ...
    }
    """
    inspector = inspect(analytics_engine)
    snapshot: dict[str, Any] = {}

    for table_name in inspector.get_table_names():
        columns = [
            {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
            }
            for col in inspector.get_columns(table_name)
        ]

        pk_constraint = inspector.get_pk_constraint(table_name)
        primary_key = pk_constraint.get("constrained_columns", [])

        foreign_keys = [
            {
                "column": fk["constrained_columns"][0],
                "references_table": fk["referred_table"],
                "references_column": fk["referred_columns"][0],
            }
            for fk in inspector.get_foreign_keys(table_name)
            if fk.get("constrained_columns") and fk.get("referred_columns")
        ]

        snapshot[table_name] = {
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
        }

    return snapshot


def format_schema_for_prompt() -> str:
    """
    Renders the cached schema snapshot as compact text for the LLM prompt.

    Example output per table:

    Table: albums
      Columns: AlbumId (INTEGER, PK), Title (VARCHAR), ArtistId (INTEGER, FK -> artists.ArtistId)
    """
    snapshot = get_schema_snapshot()
    lines: list[str] = []

    for table_name, info in snapshot.items():
        fk_by_column = {fk["column"]: fk for fk in info["foreign_keys"]}
        col_strs = []

        for col in info["columns"]:
            tags = []
            if col["name"] in info["primary_key"]:
                tags.append("PK")
            if col["name"] in fk_by_column:
                fk = fk_by_column[col["name"]]
                tags.append(f"FK -> {fk['references_table']}.{fk['references_column']}")

            tag_str = f", {', '.join(tags)}" if tags else ""
            col_strs.append(f"{col['name']} ({col['type']}{tag_str})")

        lines.append(f"Table: {table_name}")
        lines.append(f"  Columns: {', '.join(col_strs)}")

    return "\n".join(lines)
"""
Reads the schema of a target analytics database via SQLAlchemy
introspection and caches it per-engine for the lifetime of the server
process.

Takes an explicit engine rather than assuming a single global
database — this is what makes multi-database support safe. Caching
must be keyed per-engine, not global: with multiple databases, a
single unkeyed cache would silently serve the wrong schema to every
database after the first one introspected.

Two entry points:
- get_schema_snapshot(engine)      -> structured dict, for code that
                                       needs to reason about
                                       tables/columns (e.g.
                                       sql_validation.py)
- format_schema_for_prompt(engine) -> compact text block, for
                                       injecting into the LLM prompt
                                       (prompts.py)
"""
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

_schema_cache: dict[int, dict[str, Any]] = {}


def get_schema_snapshot(engine: Engine) -> dict[str, Any]:
    """
    Introspects the given engine once per process and caches the
    result, keyed by the engine's identity (id()) so different
    databases never share a cache entry.

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
    cache_key = id(engine)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    inspector = inspect(engine)
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

    _schema_cache[cache_key] = snapshot
    return snapshot


def format_schema_for_prompt(engine: Engine) -> str:
    """
    Renders the cached schema snapshot for the given engine as compact
    text for the LLM prompt.

    Example output per table:

    Table: albums
      Columns: AlbumId (INTEGER, PK), Title (VARCHAR), ArtistId (INTEGER, FK -> artists.ArtistId)
    """
    snapshot = get_schema_snapshot(engine)
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
"""
Reads the schema of a target analytics database via SQLAlchemy
introspection and caches it per-engine for the lifetime of the server
process.

Takes an explicit engine rather than assuming a single global
database — this is what makes multi-database support safe. Caching
must be keyed per-engine, not global: with multiple databases, a
single unkeyed cache would silently serve the wrong schema to every
database after the first one introspected.

Scaling note: format_schema_for_prompt() dumps every table's full
column detail into the LLM prompt. That's fine for small schemas
(Chinook's 11 tables) but doesn't scale — a database with hundreds of
tables would blow up both token cost and accuracy (LLMs get worse at
picking the right table when flooded with irrelevant ones). For large
schemas, app.core.schema_selection does a cheap first pass (table
names only) to narrow down to relevant tables before this module
formats their full detail — see get_table_summaries and the
table_names parameter on format_schema_for_prompt below.

Entry points:
- get_schema_snapshot(engine)                  -> full structured
  dict for every table, for code that needs to reason about
  tables/columns (e.g. sql_validation.py, which must validate against
  the whole schema regardless of what was "selected" for a prompt)
- get_table_summaries(engine)                  -> lightweight list of
  {name, column_count} for every table, cheap to send to an LLM for
  table-selection without the full column detail
- format_schema_for_prompt(engine, table_names) -> compact text block
  for the LLM prompt, optionally filtered to only the given tables
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


def get_table_summaries(engine: Engine) -> list[dict[str, Any]]:
    """
    Lightweight per-table summary: just the name and column count.
    Cheap enough to send to an LLM for table-selection (stage 1 of
    two-stage schema retrieval) without paying for full column detail
    up front.
    """
    snapshot = get_schema_snapshot(engine)
    return [
        {"name": table_name, "column_count": len(info["columns"])}
        for table_name, info in snapshot.items()
    ]


def format_table_list_for_prompt(engine: Engine) -> str:
    """
    Renders just table names + column counts as compact text — used
    for the stage-1 "which tables are relevant" prompt, not for SQL
    generation itself.
    """
    summaries = get_table_summaries(engine)
    return "\n".join(f"- {s['name']} ({s['column_count']} columns)" for s in summaries)


def format_schema_for_prompt(engine: Engine, table_names: list[str] | None = None) -> str:
    """
    Renders the cached schema snapshot for the given engine as compact
    text for the LLM prompt.

    If table_names is given, only those tables are included — this is
    stage 2 of two-stage schema retrieval for large databases. If
    omitted (the default), every table is included, which is correct
    and sufficient for small-to-medium schemas.

    Example output per table:

    Table: albums
      Columns: AlbumId (INTEGER, PK), Title (VARCHAR), ArtistId (INTEGER, FK -> artists.ArtistId)
    """
    snapshot = get_schema_snapshot(engine)

    if table_names is not None:
        snapshot = {name: info for name, info in snapshot.items() if name in table_names}

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
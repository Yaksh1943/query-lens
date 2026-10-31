"""
Reads and caches a target database's schema via SQLAlchemy
introspection. Takes an explicit engine (not a global one) so
multiple databases can be introspected safely, each with its own
cache entry — see app.db.connection_manager.

format_schema_for_prompt() can optionally filter to specific tables
(table_names) — used for large schemas, see app.core.schema_selection.
"""
import threading
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

_SCHEMA_LOCK = threading.Lock()
_schema_cache: dict[int, dict[str, Any]] = {}
_table_prompt_cache: dict[int, dict[str, str]] = {}
_full_prompt_cache: dict[int, str] = {}


def get_schema_snapshot(engine: Engine) -> dict[str, Any]:
    """
    Introspects the given engine once per process and caches the
    result, keyed by the engine's identity (id()) so different
    databases never share a cache entry. Thread-safe with precomputed
    lookups for O(1) prompt and validation rendering.
    """
    cache_key = id(engine)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    with _SCHEMA_LOCK:
        if cache_key in _schema_cache:
            return _schema_cache[cache_key]

        inspector = inspect(engine)
        snapshot: dict[str, Any] = {}
        table_prompt_snippets: dict[str, str] = {}
        known_tables: set[str] = set()
        known_columns: set[str] = set()

        for table_name in inspector.get_table_names():
            known_tables.add(table_name.lower())
            columns = [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                }
                for col in inspector.get_columns(table_name)
            ]

            for c in columns:
                known_columns.add(c["name"].lower())

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

            # Precompute formatted prompt snippet for this table: O(1) formatting later
            fk_by_column = {fk["column"]: fk for fk in foreign_keys}
            col_strs = []
            for col in columns:
                tags = []
                if col["name"] in primary_key:
                    tags.append("PK")
                if col["name"] in fk_by_column:
                    fk = fk_by_column[col["name"]]
                    tags.append(f"FK -> {fk['references_table']}.{fk['references_column']}")

                tag_str = f", {', '.join(tags)}" if tags else ""
                col_strs.append(f"{col['name']} ({col['type']}{tag_str})")

            table_prompt_snippets[table_name] = f"Table: {table_name}\n  Columns: {', '.join(col_strs)}"

        # Store precomputed fast lookups for validation
        snapshot["__known_tables__"] = known_tables
        snapshot["__known_columns__"] = known_columns

        _table_prompt_cache[cache_key] = table_prompt_snippets
        _full_prompt_cache[cache_key] = "\n".join(table_prompt_snippets.values())
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
        if not table_name.startswith("__")
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
    text for the LLM prompt. Uses precomputed string cache for O(1) or O(T) lookup.
    """
    cache_key = id(engine)
    if cache_key not in _schema_cache:
        get_schema_snapshot(engine)

    if table_names is None:
        return _full_prompt_cache.get(cache_key, "")

    table_cache = _table_prompt_cache.get(cache_key, {})
    return "\n".join(table_cache[name] for name in table_names if name in table_cache)

"""
SQLAlchemy ORM models for app_db (the application's own database —
query history, not the Chinook data being queried).

Base is defined here since no declarative base exists elsewhere in
the codebase yet. Any future app_db models should import Base from
this file so they all register on the same metadata.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class QueryHistory(Base):
    """One row per question asked through the /api/query pipeline."""

    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON-serialized summary: {"row_count": N, "sample_rows": [...]}
    # not the full result set, to keep app_db small.
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    execution_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    served_from_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class DatabaseConnection(Base):
    """
    A user-added database connection to query via natural language.
    connection_url_encrypted is a Fernet token (see app.core.crypto)
    — the raw connection string is never stored or logged in plaintext.
    """

    __tablename__ = "database_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    connection_url_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class QueryCache(Base):
    """
    Caches the validated SQL for a given (connection, question) pair,
    so a repeated question skips the ambiguity check, table selection,
    and SQL generation LLM calls entirely.

    Deliberately caches SQL, not the final answer or result rows: the
    query is always re-executed fresh and the answer always
    regenerated from live data, so a cache hit can never return stale
    or incorrect information — only the LLM calls that don't need to
    change once a phrasing is known to work are skipped.

    Exact-match only (question_normalized is a simple lowercase/trim
    normalization, not semantic matching) — a differently-worded but
    equivalent question is a cache miss. Semantic matching would need
    embeddings/a vector store (see e.g. GPTCache, Redis LangCache) —
    a legitimate future improvement, scoped out here since it crosses
    into infrastructure this project deliberately avoids.
    """

    __tablename__ = "query_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
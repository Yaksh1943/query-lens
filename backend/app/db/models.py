"""
SQLAlchemy ORM models for app_db (the application's own database —
query history, not the Chinook data being queried).

Base is defined here since no declarative base exists elsewhere in
the codebase yet. Any future app_db models should import Base from
this file so they all register on the same metadata.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
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

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    execution_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
"""
Exact-match cache for validated SQL, keyed by (connection, normalized
question). See app.db.models.QueryCache for the full rationale: this
skips the ambiguity check, table selection, and SQL generation LLM
calls on a cache hit, while always re-executing fresh and
regenerating the answer, so results can never go stale.

Exact-match only — see QueryCache's docstring for why semantic
matching is deliberately out of scope here.
"""
import re

from sqlalchemy.orm import Session

from app.db.models import QueryCache

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_question(question: str) -> str:
    """Lowercase, trim, and collapse whitespace — simple exact-match normalization."""
    return _WHITESPACE_RE.sub(" ", question.strip().lower())


def get_cached(question: str, connection_id: int | None, db: Session) -> QueryCache | None:
    """
    Looks up a cached entry for this exact (normalized) question and
    connection. On a hit, updates hit_count/last_used_at so real
    cache usage is visible in stats.
    """
    normalized = normalize_question(question)

    entry = (
        db.query(QueryCache)
        .filter(
            QueryCache.question_normalized == normalized,
            QueryCache.connection_id == connection_id,
        )
        .first()
    )

    if entry is not None:
        entry.hit_count += 1
        from datetime import datetime, timezone

        entry.last_used_at = datetime.now(timezone.utc)
        db.commit()

    return entry


def save_to_cache(
    question: str,
    connection_id: int | None,
    db: Session,
    *,
    sql: str | None = None,
    is_ambiguous: bool = False,
    clarification_question: str | None = None,
) -> None:
    """
    Saves (or updates, if already present) a cache entry for this
    question. Called after a successful pipeline run — a question is
    only cached once we know, for certain, whether it's ambiguous and
    what valid SQL (if any) answers it.
    """
    normalized = normalize_question(question)

    existing = (
        db.query(QueryCache)
        .filter(
            QueryCache.question_normalized == normalized,
            QueryCache.connection_id == connection_id,
        )
        .first()
    )

    if existing is not None:
        existing.sql = sql
        existing.is_ambiguous = is_ambiguous
        existing.clarification_question = clarification_question
        db.commit()
        return

    entry = QueryCache(
        connection_id=connection_id,
        question_normalized=normalized,
        sql=sql,
        is_ambiguous=is_ambiguous,
        clarification_question=clarification_question,
    )
    db.add(entry)
    db.commit()
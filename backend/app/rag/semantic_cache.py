"""
Semantic Vector Cache for QueryLens.

Replaces rigid exact-string matching with dense semantic similarity matching.
Paraphrased questions (e.g. "top spending customers" vs "who spent the most money?")
trigger a cache hit, dropping latency to ~15ms and LLM API cost to $0.

Algorithm:
1. Exact string match check (O(1)) for instantaneous return.
2. If exact miss, dense cosine similarity search over cached questions for the same connection_id.
3. If similarity >= threshold (default 0.94), return cached SQL and increment hit stats.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import QueryCache
from app.observability.logger import get_logger
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import InMemoryVectorStore, VectorDocument

logger = get_logger(__name__)

# Dedicated vector store for semantic query cache
_CACHE_VECTOR_STORE = InMemoryVectorStore()
_CACHE_HYDRATED: bool = False


@dataclass
class SemanticCacheHit:
    entry: QueryCache
    similarity: float
    is_exact: bool


def _hydrate_cache_if_needed(db: Session, embedding_provider: EmbeddingProvider) -> None:
    global _CACHE_HYDRATED
    if _CACHE_HYDRATED:
        return

    try:
        entries = db.query(QueryCache).all()
        if entries:
            questions = [e.question_normalized for e in entries]
            vectors = embedding_provider.embed_batch(questions)
            docs = [
                VectorDocument(
                    id=f"cache:{e.id}",
                    text=e.question_normalized,
                    vector=v,
                    metadata={"cache_id": e.id, "connection_id": e.connection_id},
                )
                for e, v in zip(entries, vectors, strict=True)
            ]
            _CACHE_VECTOR_STORE.add_documents(docs)
            logger.info("Hydrated Semantic Cache with %d entries", len(entries))
    except Exception as e:
        logger.warning("Could not hydrate semantic cache from DB: %s", e)
    finally:
        _CACHE_HYDRATED = True


def get_cached_semantic(
    question: str,
    connection_id: int | None,
    db: Session,
    threshold: float | None = None,
) -> SemanticCacheHit | None:
    """
    Checks exact match first, then falls back to vector cosine similarity search.
    Returns SemanticCacheHit if similarity >= threshold, else None.
    """
    settings = get_settings()
    if threshold is None:
        threshold = settings.semantic_cache_threshold

    normalized = question.strip().lower()

    # Step 1: Instant exact-match check (O(1))
    exact_entry = (
        db.query(QueryCache)
        .filter(
            QueryCache.question_normalized == normalized,
            QueryCache.connection_id == connection_id,
        )
        .first()
    )
    if exact_entry is not None:
        exact_entry.hit_count += 1
        exact_entry.last_used_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Exact cache hit for question: '%s'", question)
        return SemanticCacheHit(entry=exact_entry, similarity=1.0, is_exact=True)

    if not settings.enable_semantic_cache:
        return None

    # Step 2: Semantic vector match
    embedding_provider = get_embedding_provider(settings)
    _hydrate_cache_if_needed(db, embedding_provider)

    q_vector = embedding_provider.embed_text(normalized)
    matches = _CACHE_VECTOR_STORE.search(
        query_vector=q_vector,
        top_k=1,
        filter_metadata={"connection_id": connection_id},
    )

    if not matches:
        return None

    best_doc, sim_score = matches[0]
    if sim_score >= threshold:
        cache_id = best_doc.metadata.get("cache_id")
        entry = db.get(QueryCache, cache_id)
        if entry is not None:
            entry.hit_count += 1
            entry.last_used_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                "Semantic cache hit! Score=%.3f (threshold=%.2f) | Query: '%s' -> Cached: '%s'",
                sim_score,
                threshold,
                question,
                entry.question_normalized,
            )
            return SemanticCacheHit(entry=entry, similarity=sim_score, is_exact=False)

    return None


def save_to_semantic_cache(
    question: str,
    connection_id: int | None,
    db: Session,
    *,
    sql: str | None = None,
    is_ambiguous: bool = False,
    clarification_question: str | None = None,
) -> QueryCache:
    """Saves to DB query_cache and updates the in-memory vector index."""
    settings = get_settings()
    normalized = question.strip().lower()

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
        entry = existing
    else:
        entry = QueryCache(
            connection_id=connection_id,
            question_normalized=normalized,
            sql=sql,
            is_ambiguous=is_ambiguous,
            clarification_question=clarification_question,
            hit_count=0,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

    # Index into Vector Store
    if settings.enable_semantic_cache:
        try:
            emb_provider = get_embedding_provider(settings)
            vec = emb_provider.embed_text(normalized)
            doc = VectorDocument(
                id=f"cache:{entry.id}",
                text=normalized,
                vector=vec,
                metadata={"cache_id": entry.id, "connection_id": connection_id},
            )
            _CACHE_VECTOR_STORE.add_documents([doc])
        except Exception as e:
            logger.warning("Failed to embed question for semantic cache: %s", e)

    return entry

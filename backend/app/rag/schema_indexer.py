"""
Indexes database schemas and few-shot golden queries into an in-memory vector index.

Time Complexity:
- Build Index: O(T * D) where T is number of tables, D is vector dimension. Computed in single batch.
- Space Complexity: O(T * D) floats in memory (~30KB for 100 tables).
- Cached by engine id() so it runs exactly once per database connection.
"""
import threading

from sqlalchemy.engine import Engine

from app.db.schema import get_schema_snapshot
from app.observability.logger import get_logger
from app.rag.chunking import GoldenQueryChunk, SchemaTableChunk
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import InMemoryVectorStore, VectorDocument

logger = get_logger(__name__)

# Global singleton index and registry
_GLOBAL_VECTOR_STORE = InMemoryVectorStore()
_INDEXED_ENGINES: set[int] = set()
_INDEX_LOCK = threading.RLock()


# Curated Golden Few-Shot Queries for Chinook & General SQL Patterns
DEFAULT_GOLDEN_QUERIES = [
    GoldenQueryChunk(
        question="Who are the top customers by total spending?",
        sql="""SELECT c."CustomerId", c."FirstName", c."LastName", SUM(i."Total") AS total_spent
FROM "Customer" c
JOIN "Invoice" i ON c."CustomerId" = i."CustomerId"
GROUP BY c."CustomerId", c."FirstName", c."LastName"
ORDER BY total_spent DESC
LIMIT 5;""",
        explanation="Calculates top spending customers by aggregating invoice totals and joining customer details.",
        tables_used=["Customer", "Invoice"],
    ),
    GoldenQueryChunk(
        question="Which artists have the most tracks?",
        sql="""SELECT a."Name", COUNT(t."TrackId") AS track_count
FROM "Artist" a
JOIN "Album" al ON a."ArtistId" = al."ArtistId"
JOIN "Track" t ON al."AlbumId" = t."AlbumId"
GROUP BY a."ArtistId", a."Name"
ORDER BY track_count DESC
LIMIT 5;""",
        explanation="Finds most prolific artists by multi-table join across Artist -> Album -> Track.",
        tables_used=["Artist", "Album", "Track"],
    ),
    GoldenQueryChunk(
        question="What is the monthly sales revenue trend?",
        sql="""SELECT DATE_TRUNC('month', i."InvoiceDate") AS sales_month, SUM(i."Total") AS monthly_revenue
FROM "Invoice" i
GROUP BY sales_month
ORDER BY sales_month ASC;""",
        explanation="Groups invoice sales by month to show revenue trends over time.",
        tables_used=["Invoice"],
    ),
    GoldenQueryChunk(
        question="Which genres have the highest average track length?",
        sql="""SELECT g."Name", AVG(t."Milliseconds") / 1000.0 AS avg_duration_seconds
FROM "Genre" g
JOIN "Track" t ON g."GenreId" = t."GenreId"
GROUP BY g."GenreId", g."Name"
ORDER BY avg_duration_seconds DESC
LIMIT 5;""",
        explanation="Averages track durations grouped by musical genre.",
        tables_used=["Genre", "Track"],
    ),
]


def index_database_schema(
    engine: Engine,
    embedding_provider: EmbeddingProvider | None = None,
    force_refresh: bool = False,
) -> InMemoryVectorStore:
    """
    Introspects and indexes an SQLAlchemy engine's tables and few-shot examples.
    Thread-safe and cached per engine.
    """
    engine_key = id(engine)

    with _INDEX_LOCK:
        if not force_refresh and engine_key in _INDEXED_ENGINES:
            return _GLOBAL_VECTOR_STORE

        if embedding_provider is None:
            embedding_provider = get_embedding_provider()

        snapshot = get_schema_snapshot(engine)
        chunks: list[SchemaTableChunk] = []

        for table_name, meta in snapshot.items():
            fks = [
                {
                    "referred_table": fk["references_table"],
                    "constrained_columns": [fk["column"]],
                    "referred_columns": [fk["references_column"]],
                }
                for fk in meta.get("foreign_keys", [])
            ]
            chunk = SchemaTableChunk(
                table_name=table_name,
                columns=meta.get("columns", []),
                primary_keys=meta.get("primary_key", []),
                foreign_keys=fks,
            )
            chunks.append(chunk)

        # Generate texts to embed
        texts_to_embed = [c.to_text() for c in chunks]
        embeddings = embedding_provider.embed_batch(texts_to_embed)

        documents: list[VectorDocument] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            doc_id = f"schema:{engine_key}:{chunk.table_name}"
            documents.append(
                VectorDocument(
                    id=doc_id,
                    text=chunk.to_text(),
                    vector=emb,
                    metadata={
                        "type": "table_schema",
                        "engine_id": engine_key,
                        "table_name": chunk.table_name,
                        "columns": [c["name"] for c in chunk.columns],
                    },
                )
            )

        # Index Golden Queries if not yet added
        golden_texts = [g.to_text() for g in DEFAULT_GOLDEN_QUERIES]
        golden_embeddings = embedding_provider.embed_batch(golden_texts)

        for g_chunk, emb in zip(DEFAULT_GOLDEN_QUERIES, golden_embeddings, strict=True):
            doc_id = f"golden:{hash(g_chunk.question)}"
            documents.append(
                VectorDocument(
                    id=doc_id,
                    text=g_chunk.to_text(),
                    vector=emb,
                    metadata={
                        "type": "golden_query",
                        "question": g_chunk.question,
                        "sql": g_chunk.sql,
                        "tables_used": g_chunk.tables_used,
                    },
                )
            )

        _GLOBAL_VECTOR_STORE.add_documents(documents)
        _INDEXED_ENGINES.add(engine_key)
        logger.info(
            "Schema RAG indexed %d tables and %d golden queries for engine %s",
            len(chunks),
            len(DEFAULT_GOLDEN_QUERIES),
            engine_key,
        )

        return _GLOBAL_VECTOR_STORE


def get_global_vector_store() -> InMemoryVectorStore:
    return _GLOBAL_VECTOR_STORE

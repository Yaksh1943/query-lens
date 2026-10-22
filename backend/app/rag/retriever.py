"""
Hybrid Schema Retriever with Reciprocal Rank Fusion (RRF) and FlashRank Reranking.

Combines:
1. Dense semantic search (FastEmbed / Gemini embeddings)
2. Sparse keyword matching (table & column identifier presence)
3. RRF rank fusion: score = 1 / (60 + rank_dense) + 1 / (60 + rank_sparse)
4. FlashRank cross-encoder reranking for ultra-high precision table filtering.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.observability.logger import get_logger
from app.rag.embeddings import get_embedding_provider
from app.rag.schema_indexer import index_database_schema
from app.rag.vector_store import VectorDocument

logger = get_logger(__name__)

# FlashRank model singleton
_FLASHRANK_RANKER = None


def _get_ranker():
    global _FLASHRANK_RANKER
    if _FLASHRANK_RANKER is None:
        try:
            from flashrank import Ranker

            # Default model: ms-marco-TinyBERT-L-2-v2 (compact 4MB cross-encoder, ~5ms latency)
            _FLASHRANK_RANKER = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
        except Exception as e:
            logger.warning("FlashRank initialization failed, falling back to pure RRF: %s", e)
            _FLASHRANK_RANKER = False
    return _FLASHRANK_RANKER


@dataclass
class RetrievalResult:
    table_names: list[str]
    golden_queries: list[dict[str, str]]
    scores: dict[str, float] = field(default_factory=dict)
    retrieval_ms: float = 0.0


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower()))


class SchemaRetriever:
    """Hybrid Retriever for database schemas and few-shot examples."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.settings = get_settings()
        self.embedding_provider = get_embedding_provider(self.settings)
        # Ensure schema is indexed
        self.vector_store = index_database_schema(engine, self.embedding_provider)

    def retrieve(
        self,
        question: str,
        top_k_tables: int | None = None,
        top_k_golden: int | None = None,
    ) -> RetrievalResult:
        import time

        start_time = time.monotonic()
        if top_k_tables is None:
            top_k_tables = self.settings.rag_top_k_tables
        if top_k_golden is None:
            top_k_golden = self.settings.rag_top_k_golden_queries

        engine_key = id(self.engine)
        q_vec = self.embedding_provider.embed_text(question)

        # 1. Dense retrieval for tables
        dense_results = self.vector_store.search(
            query_vector=q_vec,
            top_k=top_k_tables * 3,
            filter_metadata={"type": "table_schema", "engine_id": engine_key},
        )

        dense_ranks: dict[str, int] = {}
        doc_map: dict[str, VectorDocument] = {}
        for rank, (doc, _) in enumerate(dense_results):
            t_name = doc.metadata.get("table_name", "")
            dense_ranks[t_name] = rank
            doc_map[t_name] = doc

        # 2. Sparse keyword matching for tables & columns
        q_tokens = _tokenize(question)
        sparse_scores: list[tuple[str, float]] = []
        for t_name, doc in doc_map.items():
            t_tokens = _tokenize(t_name)
            col_tokens = set()
            for col in doc.metadata.get("columns", []):
                col_tokens.update(_tokenize(col))

            match_count = len(q_tokens.intersection(t_tokens)) * 3 + len(q_tokens.intersection(col_tokens))
            sparse_scores.append((t_name, float(match_count)))

        sparse_scores.sort(key=lambda x: x[1], reverse=True)
        sparse_ranks = {t_name: rank for rank, (t_name, _) in enumerate(sparse_scores)}

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: dict[str, float] = {}
        for t_name in doc_map:
            d_rank = dense_ranks.get(t_name, 999)
            s_rank = sparse_ranks.get(t_name, 999)
            rrf = (1.0 / (60.0 + d_rank)) + (1.0 / (60.0 + s_rank))
            rrf_scores[t_name] = rrf

        sorted_tables = sorted(rrf_scores.keys(), key=lambda t: rrf_scores[t], reverse=True)
        candidate_tables = sorted_tables[: top_k_tables * 2]

        # 4. Optional FlashRank Cross-Encoder Reranking
        final_tables = candidate_tables[:top_k_tables]
        ranker = _get_ranker() if self.settings.enable_reranking else None

        if ranker and len(candidate_tables) > 1:
            try:
                passages = [
                    {"id": t, "text": doc_map[t].text}
                    for t in candidate_tables
                    if t in doc_map
                ]
                rerank_req = {"query": question, "passages": passages}
                reranked = ranker.rerank(rerank_req)
                final_tables = [item["id"] for item in reranked[:top_k_tables]]
            except Exception as e:
                logger.warning("FlashRank reranking error, using RRF order: %s", e)

        # 5. Retrieve Few-Shot Golden Queries
        golden_results = self.vector_store.search(
            query_vector=q_vec,
            top_k=top_k_golden,
            filter_metadata={"type": "golden_query"},
        )
        golden_queries = [
            {
                "question": doc.metadata.get("question", ""),
                "sql": doc.metadata.get("sql", ""),
                "tables": ", ".join(doc.metadata.get("tables_used", [])),
            }
            for doc, _ in golden_results
        ]

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Schema RAG retrieved %d tables (%s) and %d golden queries in %.2fms",
            len(final_tables),
            ", ".join(final_tables),
            len(golden_queries),
            elapsed_ms,
        )

        return RetrievalResult(
            table_names=final_tables,
            golden_queries=golden_queries,
            scores=rrf_scores,
            retrieval_ms=elapsed_ms,
        )

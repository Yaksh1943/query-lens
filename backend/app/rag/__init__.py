"""
RAG and Vector Search subsystem for QueryLens.
"""
from app.rag.embeddings import EmbeddingProvider, FastEmbedProvider, get_embedding_provider
from app.rag.retriever import RetrievalResult, SchemaRetriever
from app.rag.schema_indexer import index_database_schema
from app.rag.semantic_cache import get_cached_semantic, save_to_semantic_cache
from app.rag.vector_store import InMemoryVectorStore, VectorDocument

__all__ = [
    "EmbeddingProvider",
    "FastEmbedProvider",
    "get_embedding_provider",
    "InMemoryVectorStore",
    "VectorDocument",
    "index_database_schema",
    "SchemaRetriever",
    "RetrievalResult",
    "get_cached_semantic",
    "save_to_semantic_cache",
]

"""
Unit and integration tests for RAG pipeline, Vector Store, and Semantic Cache.
"""
import pytest

from app.rag.chunking import SchemaTableChunk
from app.rag.embeddings import EmbeddingProvider, FastEmbedProvider
from app.rag.vector_store import InMemoryVectorStore, VectorDocument


class DummyEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for fast test execution."""

    def __init__(self, dim: int = 4) -> None:
        self._dim = dim

    def embed_text(self, text: str) -> list[float]:
        # Simple deterministic vector based on character sum
        val = float(sum(ord(c) for c in text) % 100) / 100.0
        return [val, 1.0 - val, val * 0.5, 0.5]

    def embed_batch(self, texts):
        return [self.embed_text(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dim


def test_in_memory_vector_store():
    store = InMemoryVectorStore()
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0, 0.0]
    v3 = [0.9, 0.1, 0.0, 0.0]

    store.add_documents([
        VectorDocument("doc1", "customer data", v1, {"type": "table", "tenant": 1}),
        VectorDocument("doc2", "invoice data", v2, {"type": "table", "tenant": 1}),
        VectorDocument("doc3", "client data", v3, {"type": "table", "tenant": 2}),
    ])

    assert len(store) == 3

    # Query close to v1
    query = [1.0, 0.0, 0.0, 0.0]
    results = store.search(query, top_k=2)
    assert len(results) == 2
    assert results[0][0].id == "doc1"
    assert pytest.approx(results[0][1], 0.01) == 1.0
    assert results[1][0].id == "doc3"

    # Filter by metadata tenant=1
    filtered = store.search(query, top_k=2, filter_metadata={"tenant": 1})
    assert len(filtered) == 2
    assert filtered[0][0].id == "doc1"
    assert filtered[1][0].id == "doc2"


def test_schema_chunking():
    chunk = SchemaTableChunk(
        table_name="Customer",
        columns=[
            {"name": "CustomerId", "type": "INTEGER"},
            {"name": "Email", "type": "VARCHAR"},
        ],
        primary_keys=["CustomerId"],
        foreign_keys=[],
        description="Customer accounts",
    )
    text = chunk.to_text()
    assert "Table Name: Customer" in text
    assert "CustomerId INTEGER (PK)" in text
    assert "Email VARCHAR" in text
    assert "Description: Customer accounts" in text


def test_fastembed_provider():
    provider = FastEmbedProvider()
    assert provider.dimension == 384
    vec = provider.embed_text("Who are the top customers?")
    assert len(vec) == 384
    batch = provider.embed_batch(["question 1", "question 2"])
    assert len(batch) == 2
    assert len(batch[0]) == 384

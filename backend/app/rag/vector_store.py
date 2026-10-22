"""
In-memory vector store with vectorized NumPy cosine similarity and metadata filtering.

Complexity:
- Add documents: O(N * D) space and initialization, continuous 2D float32 matrix.
- Search: O(N * D) dot-product matrix multiplication (AVX2/SIMD accelerated).
- Top-K: O(N + K log K) using numpy.argpartition (significantly faster than full O(N log N) sorting).
"""
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class VectorDocument:
    id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryVectorStore:
    """Thread-safe, vectorized in-memory vector index."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, VectorDocument] = {}
        self._doc_ids: list[str] = []
        self._matrix: np.ndarray | None = None  # shape (N, D) normalized float32
        self._dirty: bool = False

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()
            self._doc_ids.clear()
            self._matrix = None
            self._dirty = False

    def add_documents(self, documents: list[VectorDocument]) -> None:
        if not documents:
            return

        with self._lock:
            for doc in documents:
                self._docs[doc.id] = doc
                if doc.id not in self._doc_ids:
                    self._doc_ids.append(doc.id)
            self._dirty = True

    def _rebuild_matrix(self) -> None:
        if not self._dirty and self._matrix is not None:
            return

        if not self._doc_ids:
            self._matrix = None
            self._dirty = False
            return

        vectors = [self._docs[doc_id].vector for doc_id in self._doc_ids]
        mat = np.array(vectors, dtype=np.float32)

        # Pre-normalize rows so cosine similarity is simply the dot product:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self._matrix = mat / norms
        self._dirty = False

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[VectorDocument, float]]:
        """
        Calculates cosine similarity across all documents matching filter_metadata.
        Returns sorted list of (VectorDocument, similarity_score) with score in [-1.0, 1.0].
        """
        with self._lock:
            self._rebuild_matrix()
            if self._matrix is None or len(self._doc_ids) == 0:
                return []

            # Normalize query vector
            q = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q)
            if q_norm > 0:
                q = q / q_norm

            # Vectorized dot product for all documents: O(N * D)
            scores = np.dot(self._matrix, q)

            # Metadata filtering
            candidates = []
            for idx, doc_id in enumerate(self._doc_ids):
                doc = self._docs[doc_id]
                if filter_metadata:
                    match = True
                    for k, v in filter_metadata.items():
                        if doc.metadata.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                candidates.append((idx, float(scores[idx])))

            if not candidates:
                return []

            # If candidates are fewer than or equal to top_k, just sort candidates
            if len(candidates) <= top_k:
                candidates.sort(key=lambda x: x[1], reverse=True)
                return [(self._docs[self._doc_ids[idx]], score) for idx, score in candidates]

            # Top-K selection via numpy.argpartition: O(N + K log K)
            cand_scores = np.array([c[1] for c in candidates], dtype=np.float32)
            # Find indices of largest top_k elements
            top_k_sub_indices = np.argpartition(-cand_scores, top_k)[:top_k]
            # Sort only the top_k slice
            sorted_order = np.argsort(-cand_scores[top_k_sub_indices])
            sorted_top_k = [candidates[top_k_sub_indices[i]] for i in sorted_order]

            return [(self._docs[self._doc_ids[idx]], score) for idx, score in sorted_top_k]

    def __len__(self) -> int:
        return len(self._docs)

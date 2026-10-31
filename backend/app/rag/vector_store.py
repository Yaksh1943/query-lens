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
    """Thread-safe, vectorized in-memory vector index with metadata inverted index."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, VectorDocument] = {}
        self._doc_ids: list[str] = []
        self._id_to_idx: dict[str, int] = {}
        self._matrix: np.ndarray | None = None  # shape (N, D) normalized float32
        self._metadata_index: dict[str, dict[Any, set[int]]] = {}
        self._dirty: bool = False

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()
            self._doc_ids.clear()
            self._id_to_idx.clear()
            self._matrix = None
            self._metadata_index.clear()
            self._dirty = False

    def add_documents(self, documents: list[VectorDocument]) -> None:
        if not documents:
            return

        with self._lock:
            for doc in documents:
                if doc.id in self._id_to_idx:
                    idx = self._id_to_idx[doc.id]
                    # Remove previous metadata mappings for this index
                    old_doc = self._docs[doc.id]
                    for k, v in old_doc.metadata.items():
                        if isinstance(v, (str, int, float, bool)):
                            s = self._metadata_index.get(k, {}).get(v)
                            if s:
                                s.discard(idx)
                    self._docs[doc.id] = doc
                else:
                    idx = len(self._doc_ids)
                    self._docs[doc.id] = doc
                    self._doc_ids.append(doc.id)
                    self._id_to_idx[doc.id] = idx

                # Index scalar metadata
                for k, v in doc.metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        if k not in self._metadata_index:
                            self._metadata_index[k] = {}
                        if v not in self._metadata_index[k]:
                            self._metadata_index[k][v] = set()
                        self._metadata_index[k][v].add(idx)

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

    def _get_matching_indices(self, filter_metadata: dict[str, Any] | None) -> list[int] | None:
        """Finds document indices matching all criteria using inverted index where possible."""
        if not filter_metadata:
            return None

        matching: set[int] | None = None
        unindexed_filters: dict[str, Any] = {}

        for k, v in filter_metadata.items():
            if k in self._metadata_index and isinstance(v, (str, int, float, bool)):
                indices = self._metadata_index[k].get(v, set())
                if matching is None:
                    matching = set(indices)
                else:
                    matching = matching.intersection(indices)
                if not matching:
                    return []
            else:
                unindexed_filters[k] = v

        if matching is None:
            # Fallback to full range
            candidate_list = list(range(len(self._doc_ids)))
        else:
            candidate_list = sorted(matching)

        if unindexed_filters:
            filtered = []
            for idx in candidate_list:
                doc = self._docs[self._doc_ids[idx]]
                match = True
                for k, v in unindexed_filters.items():
                    if doc.metadata.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(idx)
            return filtered

        return candidate_list

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[VectorDocument, float]]:
        """
        Calculates cosine similarity across documents matching filter_metadata.
        Returns sorted list of (VectorDocument, similarity_score) with score in [-1.0, 1.0].
        """
        with self._lock:
            self._rebuild_matrix()
            if self._matrix is None or len(self._doc_ids) == 0:
                return []

            matched_indices = self._get_matching_indices(filter_metadata)
            if matched_indices is not None and len(matched_indices) == 0:
                return []

            # Normalize query vector
            q = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q)
            if q_norm > 0:
                q = q / q_norm

            # Compute dot product only on matched slice if filtered, else all
            if matched_indices is not None:
                sub_matrix = self._matrix[matched_indices]
                sub_scores = np.dot(sub_matrix, q)
                candidate_indices = matched_indices
                scores_array = sub_scores
            else:
                scores_array = np.dot(self._matrix, q)
                candidate_indices = list(range(len(self._doc_ids)))

            num_cands = len(candidate_indices)
            if num_cands == 0:
                return []

            if num_cands <= top_k:
                sorted_local_indices = np.argsort(-scores_array)
                return [
                    (self._docs[self._doc_ids[candidate_indices[i]]], float(scores_array[i]))
                    for i in sorted_local_indices
                ]

            # Top-K selection via numpy.argpartition: O(N + K log K)
            top_k_sub_indices = np.argpartition(-scores_array, top_k)[:top_k]
            sorted_order = np.argsort(-scores_array[top_k_sub_indices])

            return [
                (
                    self._docs[self._doc_ids[candidate_indices[top_k_sub_indices[i]]]],
                    float(scores_array[top_k_sub_indices[i]]),
                )
                for i in sorted_order
            ]

    def __len__(self) -> int:
        return len(self._docs)

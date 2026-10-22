"""
Embedding provider interface and implementations.

Supports:
- FastEmbedProvider: CPU-optimized local ONNX embeddings (BAAI/bge-small-en-v1.5).
  Runs in ~8-15ms, 0 API cost, zero rate limits, completely offline.
- GeminiEmbeddingProvider: Google Gemini text-embedding-004 via google-genai SDK.
"""
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Sequence


from app.core.config import Settings, get_settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface for dense text embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single string into a float vector."""
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed multiple strings in one call."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        raise NotImplementedError


class FastEmbedProvider(EmbeddingProvider):
    """Local, CPU-optimized embedding provider using FastEmbed (ONNX)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model = None
        self._dim: int = 384  # bge-small-en-v1.5 dimension

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("Initializing FastEmbed model: %s", self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        # FastEmbed returns an iterator of numpy ndarrays
        embeddings_iter = model.embed(texts)
        result = [emb.tolist() for emb in embeddings_iter]
        if result and len(result[0]) != self._dim:
            self._dim = len(result[0])
        return result

    @property
    def dimension(self) -> int:
        return self._dim


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Gemini text-embedding-004 provider via official google-genai SDK."""

    def __init__(self, api_key: str, model: str = "text-embedding-004") -> None:
        self.api_key = api_key
        self.model = model
        self._dim = 768

    def embed_text(self, text: str) -> list[float]:
        res = self.embed_batch([text])
        return res[0]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        from google import genai

        client = genai.Client(api_key=self.api_key)
        response = client.models.embed_content(
            model=self.model,
            contents=list(texts),
        )
        embeddings = []
        for emb in response.embeddings:
            embeddings.append(list(emb.values))
        if embeddings:
            self._dim = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        return self._dim


@lru_cache
def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    if settings is None:
        settings = get_settings()

    provider_name = settings.embedding_provider.lower().strip()
    if provider_name == "gemini" and settings.gemini_api_key:
        return GeminiEmbeddingProvider(api_key=settings.gemini_api_key)

    # Default to fastembed (local, 0 cost, instant)
    return FastEmbedProvider(model_name=settings.fastembed_model)

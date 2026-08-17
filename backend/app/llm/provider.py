"""
LLM provider abstraction.

The rest of the codebase depends only on the LLMProvider interface,
never on a specific vendor SDK. This is what lets us swap Gemini for
another free-tier provider (e.g. OpenRouter) later without touching
any business logic — see docs/blueprint for the reasoning.

Phase 1 note: generate_sql() is intentionally a stub raised as
NotImplementedError until the prompt/schema-retrieval pipeline is
built. Wiring the API key and a "hello world" completion happens
first, as a standalone verification step, before real SQL generation
logic is added on top.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMProvider(ABC):
    """Contract every LLM provider adapter must satisfy."""

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        """Send a prompt, return the raw completion plus usage metadata."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Google Gemini adapter (free tier). Implemented in Phase 1."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        raise NotImplementedError(
            "GeminiProvider.complete() will be implemented in Phase 1 "
            "once the API key is wired up and tested."
        )

"""
LLM provider abstraction.

The rest of the codebase depends only on the LLMProvider interface,
never on a specific vendor SDK. This is what lets us swap Gemini for
another free-tier provider (e.g. OpenRouter) later without touching
any business logic — see docs/blueprint for the reasoning.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from google import genai
from google.genai import types


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
    """Google Gemini adapter (free tier), via the google-genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash") -> None:
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=self.api_key)

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        config = types.GenerateContentConfig(system_instruction=system) if system else None

        start = time.monotonic()
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        latency_ms = (time.monotonic() - start) * 1000

        usage = response.usage_metadata

        return LLMResponse(
            text=response.text.strip(),
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            latency_ms=latency_ms,
        )
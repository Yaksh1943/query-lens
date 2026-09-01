"""
LLM provider abstraction.

The rest of the codebase depends only on the LLMProvider interface,
never on a specific vendor SDK. This is what lets us swap Gemini for
another free-tier provider (e.g. OpenRouter) later without touching
any business logic — see docs/blueprint for the reasoning.
"""
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from google import genai
from google.genai import errors, types


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

    MAX_RETRIES = 3
    DEFAULT_BACKOFF_S = 15.0

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash") -> None:
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=self.api_key)

    def _extract_retry_delay(self, error: errors.ClientError) -> float:
        """
        Gemini's 429 response includes a RetryInfo block with the exact
        number of seconds to wait. Fall back to a fixed backoff if it's
        not present or unparseable, rather than failing the whole call.
        """
        try:
            details = error.details.get("error", {}).get("details", [])
            for d in details:
                if d.get("@type", "").endswith("RetryInfo"):
                    delay_str = d.get("retryDelay", "")  # e.g. "41s"
                    match = re.match(r"([\d.]+)s", delay_str)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass
        return self.DEFAULT_BACKOFF_S

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        config = types.GenerateContentConfig(system_instruction=system) if system else None

        for attempt in range(self.MAX_RETRIES + 1):
            start = time.monotonic()
            try:
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

            except errors.ClientError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES:
                    delay = self._extract_retry_delay(e)
                    print(f"[GeminiProvider] Rate limited, retrying in {delay:.0f}s "
                          f"(attempt {attempt + 1}/{self.MAX_RETRIES})...")
                    time.sleep(delay)
                    continue
                raise
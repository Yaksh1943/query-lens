"""
LLM provider abstraction.

The rest of the codebase depends only on the LLMProvider interface,
never on a specific vendor SDK.
"""
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from google import genai
from google.genai import errors, types

from app.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Google Gemini adapter (free tier), via the google-genai SDK."""

    MAX_RETRIES = 3
    DEFAULT_BACKOFF_S = 15.0
    MIN_SECONDS_BETWEEN_CALLS = 13.0  # free tier: 5 requests/minute
    SERVER_ERROR_BACKOFF_S = 5.0  # for transient 5xx, shorter backoff than a real rate-limit wait

    _last_call_time: float = 0.0

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash") -> None:
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=self.api_key)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - GeminiProvider._last_call_time
        if elapsed < self.MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(self.MIN_SECONDS_BETWEEN_CALLS - elapsed)
        GeminiProvider._last_call_time = time.monotonic()

    def _extract_retry_delay(self, error: errors.ClientError) -> float:
        try:
            details = error.details.get("error", {}).get("details", [])
            for d in details:
                if d.get("@type", "").endswith("RetryInfo"):
                    delay_str = d.get("retryDelay", "")
                    match = re.match(r"([\d.]+)s", delay_str)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass
        return self.DEFAULT_BACKOFF_S

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        config = types.GenerateContentConfig(system_instruction=system) if system else None

        for attempt in range(self.MAX_RETRIES + 1):
            self._throttle()
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
                    logger.warning("Rate limited, retrying in %.0fs (attempt %d/%d)", delay, attempt + 1, self.MAX_RETRIES)
                    time.sleep(delay)
                    continue
                raise

            except errors.ServerError as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        "Gemini server error (%s), retrying in %.0fs (attempt %d/%d)",
                        e.code, self.SERVER_ERROR_BACKOFF_S, attempt + 1, self.MAX_RETRIES,
                    )
                    time.sleep(self.SERVER_ERROR_BACKOFF_S)
                    continue
                raise
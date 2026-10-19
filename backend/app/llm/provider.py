"""
LLM provider abstraction.

The rest of the codebase depends only on the LLMProvider interface,
never on a specific vendor SDK.
"""
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
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
    SERVER_ERROR_BACKOFF_S = 5.0

    _last_call_time: float = 0.0

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        min_seconds_between_calls: float = 0.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.min_seconds_between_calls = min_seconds_between_calls
        self.client = genai.Client(api_key=self.api_key)

    def _throttle(self) -> None:
        if self.min_seconds_between_calls <= 0.0:
            return
        elapsed = time.monotonic() - GeminiProvider._last_call_time
        if elapsed < self.min_seconds_between_calls:
            time.sleep(self.min_seconds_between_calls - elapsed)
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
                    input_tokens=usage.prompt_token_count if usage else 0,
                    output_tokens=usage.candidates_token_count if usage else 0,
                    latency_ms=latency_ms,
                )

            except errors.ClientError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES:
                    delay = self._extract_retry_delay(e)
                    logger.warning("Gemini rate limited, retrying in %.0fs (attempt %d/%d)", delay, attempt + 1, self.MAX_RETRIES)
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


class GroqProvider(LLMProvider):
    """
    Groq free-tier provider (high-speed inference for open models such as Llama-3.3-70B).
    Uses standard HTTP requests via httpx.
    """

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MAX_RETRIES = 2

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout_s: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }

        for attempt in range(self.MAX_RETRIES + 1):
            start = time.monotonic()
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.post(self.BASE_URL, headers=headers, json=payload)
                    if resp.status_code == 429 and attempt < self.MAX_RETRIES:
                        logger.warning("Groq rate limited, retrying in 2.0s (attempt %d/%d)", attempt + 1, self.MAX_RETRIES)
                        time.sleep(2.0)
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                latency_ms = (time.monotonic() - start) * 1000
                choice = data["choices"][0]
                text = choice["message"]["content"].strip()
                usage = data.get("usage", {})

                return LLMResponse(
                    text=text,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms,
                )
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning("Groq call failed (%s), retrying (attempt %d/%d)", e, attempt + 1, self.MAX_RETRIES)
                    time.sleep(1.0)
                    continue
                raise


class OllamaProvider(LLMProvider):
    """
    Local Ollama provider (100% free, runs locally on CPU/GPU, zero network latency/quota).
    Works with local open models like qwen2.5-coder:7b or llama3.2.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5-coder:7b",
        timeout_s: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        endpoint = f"{self.base_url}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }

        start = time.monotonic()
        with httpx.Client(timeout=self.timeout_s) as client:
            resp = client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.monotonic() - start) * 1000
        choice = data["choices"][0]
        text = choice["message"]["content"].strip()
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )


class FallbackProvider(LLMProvider):
    """
    Chains multiple providers in priority order.
    If the primary provider encounters a rate limit (429), connection error, or outage,
    it automatically fails over to the next available free provider in the chain.
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        self.providers = providers

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        last_error = None
        for i, provider in enumerate(self.providers):
            try:
                return provider.complete(prompt, system=system)
            except Exception as e:
                last_error = e
                prov_name = provider.__class__.__name__
                if i < len(self.providers) - 1:
                    next_prov = self.providers[i + 1].__class__.__name__
                    logger.warning(
                        "Provider %s failed (%s); failing over to %s",
                        prov_name, e, next_prov
                    )
                else:
                    logger.error("All providers in fallback chain failed. Last error: %s", e)
        if last_error:
            raise last_error
        raise RuntimeError("No provider succeeded.")


def get_llm_provider(settings: Any | None = None) -> LLMProvider:
    """
    Factory creating the configured LLM provider or multi-provider fallback pool.
    """
    if settings is None:
        from app.core.config import get_settings
        settings = get_settings()

    provider_name = (settings.llm_provider or "gemini").lower()

    if provider_name == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)

    if provider_name == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)

    if provider_name in ("fallback", "auto"):
        pool: list[LLMProvider] = []
        if settings.gemini_api_key:
            pool.append(
                GeminiProvider(
                    api_key=settings.gemini_api_key,
                    model=getattr(settings, "gemini_model", "gemini-2.5-flash"),
                    min_seconds_between_calls=getattr(settings, "gemini_min_seconds_between_calls", 0.0),
                )
            )
        if getattr(settings, "groq_api_key", ""):
            pool.append(GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model))
        if pool:
            return FallbackProvider(pool) if len(pool) > 1 else pool[0]

    # Default to GeminiProvider
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=getattr(settings, "gemini_model", "gemini-2.5-flash"),
        min_seconds_between_calls=getattr(settings, "gemini_min_seconds_between_calls", 0.0),
    )
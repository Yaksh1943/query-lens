import time
from unittest.mock import MagicMock, patch
import pytest

from app.llm.provider import (
    FallbackProvider,
    GeminiProvider,
    GroqProvider,
    LLMProvider,
    LLMResponse,
    OllamaProvider,
    get_llm_provider,
)


class DummySuccessProvider(LLMProvider):
    def __init__(self, name: str = "dummy", text: str = "SELECT 1"):
        self.name = name
        self.text = text

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        return LLMResponse(
            text=self.text,
            input_tokens=10,
            output_tokens=5,
            latency_ms=12.5,
        )


class DummyFailingProvider(LLMProvider):
    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        raise RuntimeError("Provider connection failed")


def test_fallback_provider_success_on_first():
    p1 = DummySuccessProvider("first", "FIRST")
    p2 = DummySuccessProvider("second", "SECOND")
    fallback = FallbackProvider([p1, p2])

    resp = fallback.complete("test prompt")
    assert resp.text == "FIRST"


def test_fallback_provider_failover():
    p1 = DummyFailingProvider()
    p2 = DummySuccessProvider("second", "SECOND_RECOVERED")
    fallback = FallbackProvider([p1, p2])

    resp = fallback.complete("test prompt")
    assert resp.text == "SECOND_RECOVERED"


def test_fallback_provider_all_fail():
    p1 = DummyFailingProvider()
    p2 = DummyFailingProvider()
    fallback = FallbackProvider([p1, p2])

    with pytest.raises(RuntimeError, match="Provider connection failed"):
        fallback.complete("test prompt")


def test_groq_provider_complete():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "SELECT * FROM tracks;"}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 8},
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        provider = GroqProvider(api_key="gsk-fake-key", model="llama-3.3-70b-versatile")
        resp = provider.complete("generate sql")

        assert resp.text == "SELECT * FROM tracks;"
        assert resp.input_tokens == 15
        assert resp.output_tokens == 8
        assert resp.latency_ms >= 0


def test_ollama_provider_complete():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "SELECT count(*) FROM albums;"}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        provider = OllamaProvider(base_url="http://localhost:11434/v1", model="qwen2.5-coder:7b")
        resp = provider.complete("how many albums")

        assert resp.text == "SELECT count(*) FROM albums;"
        assert resp.input_tokens == 20
        assert resp.output_tokens == 10


def test_gemini_provider_throttling():
    with patch("google.genai.Client"):
        # With min_seconds_between_calls = 0.0, no forced sleep
        provider = GeminiProvider(api_key="fake-key", min_seconds_between_calls=0.0)
        start = time.monotonic()
        provider._throttle()
        duration = time.monotonic() - start
        assert duration < 0.1


def test_get_llm_provider_factory():
    settings = MagicMock()
    settings.llm_provider = "groq"
    settings.groq_api_key = "gsk-test"
    settings.groq_model = "llama-3.3-70b-versatile"

    provider = get_llm_provider(settings)
    assert isinstance(provider, GroqProvider)

    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://localhost:11434/v1"
    settings.ollama_model = "qwen2.5-coder:7b"
    provider = get_llm_provider(settings)
    assert isinstance(provider, OllamaProvider)

    settings.llm_provider = "auto"
    settings.gemini_api_key = "gemini-key"
    settings.gemini_model = "gemini-3.5-flash-lite"
    settings.gemini_min_seconds_between_calls = 0.0
    settings.groq_api_key = "gsk-test"
    provider = get_llm_provider(settings)
    assert isinstance(provider, FallbackProvider)

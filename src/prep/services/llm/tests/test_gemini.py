"""Tests for GeminiProvider fallback behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.prep.services.llm.base import LLMResponse
from src.prep.services.llm.gemini import GeminiProvider, NonRetryableGeminiError


def _make_provider(monkeypatch, *, model: str = "gemini-3-pro-preview", fallback_model: str | None = None):
    class DummyInteractions:
        async def create(self, **kwargs):  # pragma: no cover - overridden in most tests
            return SimpleNamespace(outputs=[], usage=None, id="dummy-interaction")

    class DummyAio:
        def __init__(self):
            self.interactions = DummyInteractions()

    class DummyClient:
        def __init__(self):
            self.aio = DummyAio()

    monkeypatch.setattr("src.prep.services.llm.gemini.genai.Client", lambda api_key: DummyClient())
    return GeminiProvider(
        model=model,
        api_key="test-key",
        system_prompt="You are helpful",
        fallback_model=fallback_model,
    )


@pytest.mark.asyncio
async def test_generate_primary_success_no_fallback_attempt(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model="gemini-2.5-flash")
    attempted_models: list[str] = []

    async def mock_generate_complete(request_params):
        attempted_models.append(request_params["model"])
        return LLMResponse(content="ok", metadata={"model": request_params["model"]})

    provider._generate_complete = AsyncMock(side_effect=mock_generate_complete)

    response = await provider.generate("hello")

    assert response.content == "ok"
    assert response.metadata["model"] == "gemini-3-pro-preview"
    assert attempted_models == ["gemini-3-pro-preview"]


@pytest.mark.asyncio
async def test_generate_falls_back_when_primary_fails(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model="gemini-2.5-flash")
    attempted_models: list[str] = []

    async def mock_generate_complete(request_params):
        attempted_models.append(request_params["model"])
        if request_params["model"] == "gemini-3-pro-preview":
            raise RuntimeError("primary failed")
        return LLMResponse(content="fallback-ok", metadata={"model": request_params["model"]})

    provider._generate_complete = AsyncMock(side_effect=mock_generate_complete)

    response = await provider.generate("hello")

    assert response.content == "fallback-ok"
    assert response.metadata["model"] == "gemini-2.5-flash"
    assert attempted_models == ["gemini-3-pro-preview", "gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_generate_raises_when_primary_fails_and_fallback_missing(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model=None)
    provider._generate_complete = AsyncMock(side_effect=RuntimeError("primary failed"))

    with pytest.raises(RuntimeError, match="primary failed"):
        await provider.generate("hello")

    assert provider._generate_complete.call_count == 1


@pytest.mark.asyncio
async def test_generate_raises_when_fallback_equals_primary(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model="gemini-3-pro-preview")
    provider._generate_complete = AsyncMock(side_effect=RuntimeError("primary failed"))

    with pytest.raises(RuntimeError, match="primary failed"):
        await provider.generate("hello")

    assert provider._generate_complete.call_count == 1


@pytest.mark.asyncio
async def test_generate_raises_when_primary_and_fallback_fail(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model="gemini-2.5-flash")
    attempted_models: list[str] = []

    async def mock_generate_complete(request_params):
        attempted_models.append(request_params["model"])
        raise RuntimeError(f"failed-{request_params['model']}")

    provider._generate_complete = AsyncMock(side_effect=mock_generate_complete)

    with pytest.raises(RuntimeError, match="failed-gemini-2.5-flash"):
        await provider.generate("hello")

    assert attempted_models == ["gemini-3-pro-preview", "gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_generate_complete_sets_model_metadata_from_request(monkeypatch):
    provider = _make_provider(monkeypatch)

    async def create_interaction(**kwargs):
        return SimpleNamespace(
            outputs=[{"text": "Hello", "finish_reason": "stop"}],
            usage={"total_input_tokens": 3, "total_output_tokens": 2},
            id="interaction-1",
        )

    provider.client.aio.interactions.create = create_interaction

    response = await provider._generate_complete(provider._build_request_params(model="gemini-fallback"))

    assert response.content == "Hello"
    assert response.metadata["model"] == "gemini-fallback"


@pytest.mark.asyncio
async def test_generate_falls_back_on_non_retryable_primary_error(monkeypatch):
    provider = _make_provider(monkeypatch, fallback_model="gemini-2.5-flash")
    attempted_models: list[str] = []

    async def mock_generate_complete(request_params):
        attempted_models.append(request_params["model"])
        if request_params["model"] == "gemini-3-pro-preview":
            raise NonRetryableGeminiError("quota exceeded")
        return LLMResponse(content="fallback-ok", metadata={"model": request_params["model"]})

    provider._generate_complete = AsyncMock(side_effect=mock_generate_complete)

    response = await provider.generate("hello")

    assert response.content == "fallback-ok"
    assert attempted_models == ["gemini-3-pro-preview", "gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_generate_complete_quota_error_is_non_retryable(monkeypatch):
    provider = _make_provider(monkeypatch)
    attempts = 0

    async def create_interaction(**kwargs):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Error code: 429 - quota exceeded for metric; limit: 0")

    provider.client.aio.interactions.create = create_interaction

    with pytest.raises(NonRetryableGeminiError):
        await provider._generate_complete(provider._build_request_params(model="gemini-3-pro-preview"))

    # No tenacity retries for non-retryable quota exhaustion.
    assert attempts == 1


def test_structured_output_uses_response_format_top_level(monkeypatch):
    """Interactions API supports response_format as a top-level param.

    response_mime_type is NOT supported and must not appear anywhere.
    generation_config must not contain response_schema or response_mime_type.
    """
    schema = {"type": "object", "properties": {"summary": {"type": "string"}}}
    monkeypatch.setattr(
        "src.prep.services.llm.gemini.genai.Client",
        lambda api_key: type("C", (), {"aio": None})(),
    )
    provider = GeminiProvider(
        model="gemini-3-pro-preview",
        api_key="test-key",
        system_prompt="test",
        response_format=schema,
        enable_thinking=False,
    )

    params = provider._build_request_params()
    gen_config = params["generation_config"]

    # response_format at top level (supported by Interactions API)
    assert params["response_format"] == schema
    # response_mime_type must NOT appear anywhere
    assert "response_mime_type" not in params
    assert "response_mime_type" not in gen_config
    # response_schema must NOT be in generation_config
    assert "response_schema" not in gen_config

"""Integration tests for LLM factory."""

import os
from unittest.mock import patch

import pytest

from src.prep.services.llm import get_llm_provider
from src.prep.services.llm.anthropic import AnthropicProvider
from src.prep.services.llm.gemini import GeminiProvider


def test_get_llm_provider_anthropic():
    """Test getting Anthropic provider from factory."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-anthropic-key"}):
        provider = get_llm_provider(
            provider_name="anthropic",
            model="claude-sonnet-4-5-20250929",
            system_prompt="You are helpful",
        )

        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-sonnet-4-5-20250929"
        assert provider.system_prompt == "You are helpful"


def test_get_llm_provider_gemini():
    """Test getting Gemini provider from factory."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}):
        provider = get_llm_provider(
            provider_name="gemini",
            model="gemini-2.0-flash-exp",
            system_prompt="You are helpful",
        )

        assert isinstance(provider, GeminiProvider)
        assert provider.model == "gemini-2.0-flash-exp"
        assert provider.system_prompt == "You are helpful"


def test_get_llm_provider_default_from_settings():
    """Test getting provider with defaults from settings."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        provider = get_llm_provider(system_prompt="You are helpful")

        # Should use settings defaults (anthropic, claude-sonnet-4-5-20250929)
        assert isinstance(provider, AnthropicProvider)


def test_get_llm_provider_unsupported():
    """Test that unsupported provider raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
        get_llm_provider(
            provider_name="unsupported",
            system_prompt="You are helpful",
        )


def test_get_llm_provider_no_api_key():
    """Test that missing API key raises ValueError."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear any existing API keys
        with patch("src.prep.services.llm.settings.anthropic_api_key", ""):
            with pytest.raises(ValueError, match="API key not found for provider"):
                get_llm_provider(
                    provider_name="anthropic",
                    system_prompt="You are helpful",
                )


def test_get_llm_provider_with_kwargs():
    """Test getting provider with additional kwargs."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        provider = get_llm_provider(
            provider_name="anthropic",
            model="claude-sonnet-4-5-20250929",
            system_prompt="You are helpful",
            enable_thinking=True,
            thinking_budget=16000,
            enable_caching=True,
            cache_ttl="1h",
            temperature=0.9,
            max_tokens=1000,
        )

        assert isinstance(provider, AnthropicProvider)
        assert provider.enable_thinking is True
        assert provider.thinking_budget == 16000
        assert provider.enable_caching is True
        assert provider.cache_ttl == "1h"
        assert provider.temperature == 0.9
        assert provider.max_tokens == 1000


def test_provider_registry_contains_expected_providers():
    """Test that provider registry contains expected providers."""
    from src.prep.services.llm import LLM_PROVIDERS

    assert "anthropic" in LLM_PROVIDERS
    assert "gemini" in LLM_PROVIDERS
    assert LLM_PROVIDERS["anthropic"] == AnthropicProvider
    assert LLM_PROVIDERS["gemini"] == GeminiProvider


def test_get_llm_provider_api_key_from_env():
    """Test that API key is read from environment variable."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-api-key"}):
        provider = get_llm_provider(
            provider_name="anthropic",
            model="claude-sonnet-4-5-20250929",
            system_prompt="You are helpful",
        )

        assert provider.api_key == "env-api-key"


def test_get_llm_provider_gemini_with_thinking():
    """Test getting Gemini provider with thinking mode."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}):
        provider = get_llm_provider(
            provider_name="gemini",
            model="gemini-2.5-pro",
            system_prompt="You are helpful",
            enable_thinking=True,
            thinking_level="high",
        )

        assert isinstance(provider, GeminiProvider)
        assert provider.enable_thinking is True
        assert provider.thinking_level == "high"

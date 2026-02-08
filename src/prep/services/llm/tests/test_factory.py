"""Integration tests for LLM factory."""

import os
from unittest.mock import patch

import pytest

from src.prep.services.llm import get_llm_provider
from src.prep.services.llm.gemini import GeminiProvider


def test_get_llm_provider_gemini():
    """Test getting Gemini provider from factory."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-google-key"}):
        provider = get_llm_provider(
            provider_name="gemini",
            model="gemini-2.0-flash-exp",
            system_prompt="You are helpful",
        )

        assert isinstance(provider, GeminiProvider)
        assert provider.model == "gemini-2.0-flash-exp"
        assert provider.system_prompt == "You are helpful"


def test_get_llm_provider_default_provider():
    """Test that provider_name defaults to 'gemini' when not specified."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-google-key"}):
        # Should default to gemini provider
        provider = get_llm_provider(model="gemini-2.0-flash-exp", system_prompt="You are helpful")

        assert isinstance(provider, GeminiProvider)
        assert provider.model == "gemini-2.0-flash-exp"


def test_get_llm_provider_unsupported():
    """Test that unsupported provider raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
        get_llm_provider(
            provider_name="unsupported",
            model="some-model",
            system_prompt="You are helpful",
        )


def test_get_llm_provider_no_api_key():
    """Test that missing API key raises ValueError."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear any existing API keys
        with patch("src.prep.services.llm.settings.google_api_key", ""):
            with pytest.raises(ValueError, match="API key not found for provider"):
                get_llm_provider(
                    provider_name="gemini",
                    model="gemini-2.0-flash-exp",
                    system_prompt="You are helpful",
                )


def test_provider_registry_contains_expected_providers():
    """Test that only Gemini is in the provider registry."""
    from src.prep.services.llm import LLM_PROVIDERS

    # Should contain gemini
    assert "gemini" in LLM_PROVIDERS
    assert LLM_PROVIDERS["gemini"] == GeminiProvider

    # Should NOT contain removed providers
    assert "anthropic" not in LLM_PROVIDERS
    assert "openai" not in LLM_PROVIDERS

    # Verify only one provider
    assert len(LLM_PROVIDERS) == 1


def test_get_llm_provider_gemini_with_thinking():
    """Test getting Gemini provider with thinking mode."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-google-key"}):
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


def test_get_llm_provider_requires_model():
    """Test that model parameter is required."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        with pytest.raises(ValueError, match="Model parameter is required"):
            get_llm_provider(provider_name="gemini", system_prompt="You are helpful")


def test_get_llm_provider_sets_configured_fallback_model():
    """Test that configured global fallback model is passed to provider."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        with patch("src.prep.services.llm.settings.llm_fallback_model", "gemini-2.5-flash"):
            provider = get_llm_provider(
                provider_name="gemini",
                model="gemini-3-pro-preview",
                system_prompt="You are helpful",
            )
            assert provider.fallback_model == "gemini-2.5-flash"


def test_get_llm_provider_respects_explicit_fallback_override():
    """Test that explicit fallback_model in kwargs overrides config default."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        with patch("src.prep.services.llm.settings.llm_fallback_model", "gemini-2.5-flash"):
            provider = get_llm_provider(
                provider_name="gemini",
                model="gemini-3-pro-preview",
                system_prompt="You are helpful",
                fallback_model="gemini-2.0-flash-exp",
            )
            assert provider.fallback_model == "gemini-2.0-flash-exp"


def test_get_llm_provider_uses_google_api_key_from_env():
    """GOOGLE_API_KEY should be preferred when present."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-env-key"}, clear=True):
        with patch("src.prep.services.llm.settings.google_api_key", ""):
            provider = get_llm_provider(
                provider_name="gemini",
                model="gemini-2.5-pro",
                system_prompt="You are helpful",
            )
            assert provider.api_key == "google-env-key"


def test_get_llm_provider_uses_google_settings_when_env_missing():
    """settings.google_api_key should be used when env key is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.prep.services.llm.settings.google_api_key", "google-settings-key"):
            provider = get_llm_provider(
                provider_name="gemini",
                model="gemini-2.5-pro",
                system_prompt="You are helpful",
            )
            assert provider.api_key == "google-settings-key"

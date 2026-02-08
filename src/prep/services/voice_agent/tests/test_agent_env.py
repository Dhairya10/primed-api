"""Tests for voice-agent GenAI environment setup."""

import os
from unittest.mock import patch

from src.prep.services.voice_agent.agent import _ensure_genai_env


def test_ensure_genai_env_sets_google_only_when_no_keys_present() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.prep.services.voice_agent.agent.settings.google_api_key", "google-settings-key"):
            _ensure_genai_env()

            assert os.environ.get("GOOGLE_API_KEY") == "google-settings-key"


def test_ensure_genai_env_leaves_google_unset_when_no_google_key_exists() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.prep.services.voice_agent.agent.settings.google_api_key", ""):
            _ensure_genai_env()

        assert "GOOGLE_API_KEY" not in os.environ


def test_ensure_genai_env_keeps_existing_google_env_key() -> None:
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-env-key"}, clear=True):
        _ensure_genai_env()

        assert os.environ.get("GOOGLE_API_KEY") == "google-env-key"

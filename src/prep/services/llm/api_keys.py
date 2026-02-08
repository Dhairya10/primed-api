"""Helpers for resolving Google GenAI API keys."""

from __future__ import annotations

import os

from src.prep.config import settings


def resolve_google_api_key() -> str | None:
    """Resolve API key from GOOGLE sources only."""
    for candidate in (os.getenv("GOOGLE_API_KEY"), settings.google_api_key):
        value = (candidate or "").strip()
        if value:
            return value
    return None

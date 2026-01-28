"""Shared services module for external integrations."""

from src.prep.services.analytics.posthog import PostHogService

__all__ = [
    "PostHogService",
]

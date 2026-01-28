"""PostHog analytics service for event tracking."""

import posthog

from src.prep.config import settings


class PostHogService:
    """Service for tracking analytics events via PostHog."""

    def __init__(self) -> None:
        """Initialize PostHog service."""
        if settings.posthog_api_key:
            posthog.api_key = settings.posthog_api_key
            posthog.host = settings.posthog_host

    def capture(self, distinct_id: str, event: str, properties: dict | None = None) -> None:
        """
        Track an event.

        Args:
            distinct_id: Unique identifier for the user
            event: Event name (e.g., "interview_started", "payment_completed")
            properties: Optional event properties

        Example:
            >>> service = PostHogService()
            >>> service.capture(
            ...     "user-123",
            ...     "interview_started",
            ...     {"session_id": "abc", "domain": "health_tech"}
            ... )
        """
        if not settings.posthog_api_key:
            return

        posthog.capture(distinct_id=distinct_id, event=event, properties=properties or {})

    def identify(self, distinct_id: str, properties: dict | None = None) -> None:
        """
        Identify a user with their properties.

        Args:
            distinct_id: Unique identifier for the user
            properties: User properties to set

        Example:
            >>> service = PostHogService()
            >>> service.identify("user-123", {"email": "user@example.com", "plan": "pro"})
        """
        if not settings.posthog_api_key:
            return

        posthog.identify(distinct_id=distinct_id, properties=properties or {})

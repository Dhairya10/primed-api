"""QStash service for async job management."""

from qstash import QStash

from src.prep.config import settings


class QStashService:
    """Service for triggering async jobs via QStash."""

    def __init__(self) -> None:
        """Initialize QStash service."""
        self.client = QStash(token=settings.qstash_token)

    def publish_json(
        self, url: str, body: dict, headers: dict | None = None, delay_seconds: int | None = None
    ) -> str:
        """
        Publish a JSON message to a URL endpoint.

        Args:
            url: Target URL for the message
            body: JSON body to send
            headers: Optional HTTP headers
            delay_seconds: Optional delay before delivery

        Returns:
            Message ID

        Raises:
            Exception: If publishing fails

        Example:
            >>> service = QStashService()
            >>> msg_id = service.publish_json(
            ...     "https://api.example.com/webhook",
            ...     {"session_id": "abc", "user_id": "123"},
            ...     {"Content-Type": "application/json"}
            ... )
        """
        try:
            kwargs = {"url": url, "body": body}
            if headers:
                kwargs["headers"] = headers
            if delay_seconds:
                kwargs["delay"] = delay_seconds

            response = self.client.message.publish_json(**kwargs)
            return response.message_id
        except Exception as e:
            raise Exception(f"Failed to publish message: {str(e)}") from e

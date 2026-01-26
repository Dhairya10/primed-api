"""Courier notification service."""

from courier.client import Courier

from src.prep.config import settings


class CourierService:
    """Service for sending notifications via Courier API."""

    def __init__(self) -> None:
        """Initialize Courier service."""
        self.client = Courier(authorization_token=settings.courier_api_key)

    def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        channels: list[str] | None = None,
        data: dict | None = None,
    ) -> None:
        """
        Send a notification to a user.

        Args:
            user_id: User UUID
            title: Notification title
            body: Notification body text
            channels: Delivery channels (default: ["push"])
            data: Optional additional data

        Raises:
            Exception: If notification fails

        Example:
            >>> service = CourierService()
            >>> service.send_notification(
            ...     "user-123",
            ...     "Your feedback is ready!",
            ...     "Check your dashboard",
            ...     ["push", "email"],
            ...     {"session_id": "abc"}
            ... )
        """
        try:
            self.client.send_message(
                message={
                    "to": {"user_id": str(user_id)},
                    "content": {"title": title, "body": body},
                    "routing": {"method": "single", "channels": channels or ["push"]},
                    "data": data or {},
                }
            )
        except Exception as e:
            raise Exception(f"Failed to send notification: {str(e)}") from e

    def send_email(
        self, email: str, subject: str, body: str, template_id: str | None = None
    ) -> None:
        """
        Send an email notification.

        Args:
            email: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            template_id: Optional Courier template ID

        Raises:
            Exception: If email fails

        Example:
            >>> service = CourierService()
            >>> service.send_email(
            ...     "user@example.com",
            ...     "Welcome",
            ...     "Thanks for signing up!"
            ... )
        """
        try:
            message = {
                "to": {"email": email},
                "content": {"title": subject, "body": body},
                "routing": {"method": "single", "channels": ["email"]},
            }

            if template_id:
                message["template"] = template_id

            self.client.send_message(message=message)
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}") from e

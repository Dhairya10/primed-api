"""Custom exceptions for feedback service."""


class FeedbackError(Exception):
    """Base exception for all feedback-related errors."""

    pass


class FeedbackEvaluationError(FeedbackError):
    """Raised when evaluation fails."""

    pass


class PromptNotFoundError(FeedbackError):
    """Raised when prompt cannot be fetched from Langfuse."""

    pass

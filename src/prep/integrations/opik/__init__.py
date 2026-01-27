"""Opik integration for LLM observability and evaluation."""

import logging
import os
from collections.abc import Callable
from typing import Any

from src.prep.config import settings

logger = logging.getLogger(__name__)

# Initialize Opik client
_opik_client: Any = None


def get_opik_client() -> Any:
    """
    Get or create Opik client singleton.

    Returns:
        Opik client instance

    Raises:
        RuntimeError: If Opik is not enabled in settings
    """
    global _opik_client

    if not settings.opik_enabled:
        raise RuntimeError("Opik is not enabled in settings")

    if _opik_client is None:
        import opik

        # Configure Opik
        opik.configure(
            api_key=settings.opik_api_key,
            workspace=settings.opik_workspace,
        )

        # Set project name globally
        os.environ["OPIK_PROJECT_NAME"] = settings.opik_project_name

        _opik_client = opik.Opik(project_name=settings.opik_project_name)

    return _opik_client


def opik_track(
    name: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """
    Decorator to track function execution in Opik with conditional enabling.

    Args:
        name: Trace name (defaults to function name)
        capture_input: Whether to capture function inputs
        capture_output: Whether to capture function outputs
        tags: Tags to attach to the trace
        metadata: Metadata to attach to the trace

    Returns:
        Wrapped function with Opik tracing if enabled, otherwise original function

    Example:
        @opik_track(name="feedback_evaluation", tags=["feedback", "skill-eval"])
        async def evaluate_drill_session(session_id: str) -> None:
            # ... implementation
    """

    def decorator(func: Callable) -> Callable:
        if not settings.opik_enabled:
            # Return original function if Opik disabled
            return func

        # Apply Opik @track decorator
        from opik import track

        tracked_func = track(
            name=name or func.__name__,
            capture_input=capture_input,
            capture_output=capture_output,
            tags=tags or [],
            metadata=metadata or {},
        )(func)

        return tracked_func

    return decorator


# Import at bottom to avoid circular dependency
from src.prep.integrations.opik.prompts import (  # noqa: E402
    PromptManager,
    get_prompt_manager,
)

__all__ = [
    "get_opik_client",
    "opik_track",
    "PromptManager",
    "get_prompt_manager",
]

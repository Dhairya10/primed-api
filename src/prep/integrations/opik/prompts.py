"""Opik prompt management utilities."""

import logging
from typing import Any

import opik
from src.prep.config import settings
from src.prep.integrations.opik import get_opik_client

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manage prompts in Opik with versioning.

    Provides centralized access to prompts stored in Opik Prompt Library,
    with support for versioning and variable formatting.
    """

    def __init__(self) -> None:
        """Initialize PromptManager."""
        if settings.opik_enabled:
            self.client = get_opik_client()
        else:
            self.client = None
            logger.warning("Opik is disabled - PromptManager will not fetch prompts from Opik")

    def get_prompt(self, name: str, version: int | None = None) -> opik.Prompt:
        """
        Fetch prompt from Opik by name.

        Args:
            name: Prompt name (e.g., 'skill-feedback-evaluation')
            version: Optional version number (defaults to latest)

        Returns:
            Opik Prompt object

        Raises:
            RuntimeError: If Opik is not enabled

        Example:
            >>> prompt_obj = prompt_mgr.get_prompt("skill-feedback-evaluation")
            >>> formatted = prompt_obj.format(
            ...     drill_name="Prioritization at Swiggy",
            ...     transcript="...",
            ... )
        """
        if not settings.opik_enabled:
            raise RuntimeError("Opik is not enabled - cannot fetch prompts")

        return opik.Prompt(name=name, version=version)

    def format_prompt(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        version: int | None = None,
    ) -> str:
        """
        Generic method to format any prompt with variables.

        Args:
            prompt_name: Name of the prompt in Opik (e.g., 'skill-feedback-evaluation')
            variables: Dictionary of variables to format the prompt with
            version: Optional version number (defaults to latest)

        Returns:
            Formatted prompt string

        Raises:
            RuntimeError: If Opik is not enabled

        Example:
            >>> formatted = prompt_mgr.format_prompt(
            ...     prompt_name="skill-feedback-evaluation",
            ...     variables={
            ...         "drill_name": "Prioritization at Swiggy",
            ...         "drill_description": "...",
            ...         "skills_with_criteria": "...",
            ...         "transcript": "...",
            ...         "past_evaluations": "...",
            ...     }
            ... )
        """
        if not settings.opik_enabled:
            raise RuntimeError("Opik is not enabled - cannot format prompts")

        prompt_obj = self.get_prompt(prompt_name, version=version)
        formatted = prompt_obj.format(**variables)

        logger.debug(
            f"Formatted prompt '{prompt_name}' (version: {version or 'latest'}) "
            f"with {len(variables)} variables"
        )

        return formatted


# Singleton instance
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get or create PromptManager singleton."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


__all__ = [
    "PromptManager",
    "get_prompt_manager",
]

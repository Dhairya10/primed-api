"""
LLM provider factory.

This module provides a factory function for creating LLM provider instances.
Currently supports Gemini, with the abstraction kept for future extensibility.

Used by:
- Drill selection (home_screen)
- Feedback generation (feedback service)
- User profile updates (feedback service)

Available providers:
- GeminiProvider: Google Gemini models with thinking mode and structured output

Usage:
    >>> from src.prep.services.llm import get_llm_provider
    >>> llm = get_llm_provider(model="gemini-2.0-flash-exp")
    >>> response = await llm.generate("Hello")
"""

import os

from src.prep.config import settings
from src.prep.features.feedback.schemas import DrillFeedback
from src.prep.services.llm.base import BaseLLMProvider
from src.prep.services.llm.gemini import GeminiProvider
from src.prep.services.llm.schemas import (
    DrillRecommendation,
    SkillEvaluation,
    SkillScoreChange,
    UserProfileUpdate,
)

# Provider registry
LLM_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "gemini": GeminiProvider,
}


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    system_prompt: str = "",
    **kwargs,
) -> BaseLLMProvider:
    """
    Factory function to get LLM provider instance.

    Args:
        provider_name: Provider name ('gemini'). Defaults to 'gemini'.
        model: Model identifier (required). Examples: 'gemini-2.0-flash-exp', 'gemini-2.5-pro'
        system_prompt: System instruction
        **kwargs: Additional provider-specific config (e.g., enable_thinking, thinking_level, response_format)

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider not supported
        ValueError: If model not provided
        ValueError: If API key not found for provider

    Example:
        >>> llm = get_llm_provider(
        ...     model="gemini-2.0-flash-exp",
        ...     system_prompt="You are an interviewer"
        ... )
        >>> response = await llm.generate("Hello")
    """
    provider_name = provider_name or "gemini"  # Default to Gemini
    if not model:
        raise ValueError("Model parameter is required")

    if provider_name not in LLM_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. Supported: {list(LLM_PROVIDERS.keys())}"
        )

    provider_class = LLM_PROVIDERS[provider_name]

    # Get API key from environment
    api_key_map = {
        "gemini": os.getenv("GEMINI_API_KEY") or settings.gemini_api_key,
    }
    api_key = api_key_map.get(provider_name)

    if not api_key:
        raise ValueError(f"API key not found for provider: {provider_name}")

    return provider_class(model=model, api_key=api_key, system_prompt=system_prompt, **kwargs)


__all__ = [
    "get_llm_provider",
    "BaseLLMProvider",
    "GeminiProvider",
    "DrillFeedback",
    "SkillEvaluation",
    "SkillScoreChange",
    "DrillRecommendation",
    "UserProfileUpdate",
]

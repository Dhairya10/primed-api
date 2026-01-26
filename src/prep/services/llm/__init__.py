"""
LLM provider factory.

STATUS: Not currently used, KEPT for future features.

This module provides abstract LLM providers for future use.
Currently unused because:
- Evaluation features are disabled (being rebuilt)

Will be used for future features like:
- Custom interview question generation
- Real-time interview analysis
- Advanced analytics features
- Multi-model support

Available providers:
- AnthropicProvider: Claude models with extended thinking
- GeminiProvider: Google Gemini models with thinking mode

Usage (when needed):
    >>> from src.prep.services.llm import get_llm_provider
    >>> llm = get_llm_provider(provider_name="anthropic", model="claude-3-5-sonnet")
    >>> response = await llm.generate("Hello")
"""

import os

from src.prep.config import settings
from src.prep.services.llm.anthropic import AnthropicProvider
from src.prep.services.llm.base import BaseLLMProvider
from src.prep.services.llm.gemini import GeminiProvider

# Provider registry
LLM_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    # "openai": OpenAIProvider,  # Add when implementing GPT support
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
        provider_name: Provider name ('anthropic', 'gemini', 'openai')
                      Defaults to settings.voice_agent_llm_provider
        model: Model identifier. Defaults to settings.voice_agent_llm_model
        system_prompt: System instruction
        **kwargs: Additional provider-specific config

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider not supported

    Example:
        >>> llm = get_llm_provider(system_prompt="You are an interviewer")
        >>> response = await llm.generate("Hello")
    """
    provider_name = provider_name or settings.voice_agent_llm_provider
    model = model or settings.voice_agent_llm_model

    if provider_name not in LLM_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. Supported: {list(LLM_PROVIDERS.keys())}"
        )

    provider_class = LLM_PROVIDERS[provider_name]

    # Get API key from environment
    api_key_map = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY") or settings.anthropic_api_key,
        "gemini": os.getenv("GEMINI_API_KEY") or settings.gemini_api_key,
        "openai": os.getenv("OPENAI_API_KEY") or settings.openai_api_key,
    }
    api_key = api_key_map.get(provider_name)

    if not api_key:
        raise ValueError(f"API key not found for provider: {provider_name}")

    return provider_class(model=model, api_key=api_key, system_prompt=system_prompt, **kwargs)


__all__ = ["get_llm_provider", "BaseLLMProvider", "AnthropicProvider", "GeminiProvider"]

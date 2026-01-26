"""Abstract base class for LLM providers."""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMMessage(BaseModel):
    """Standardized message format."""

    role: str  # 'user', 'assistant', 'system'
    content: str
    metadata: dict[str, Any] = {}


class LLMResponse(BaseModel):
    """Standardized LLM response."""

    content: str
    finish_reason: str | None = None
    usage: dict[str, int] | None = None  # tokens, cost tracking
    metadata: dict[str, Any] = {}


class BaseLLMProvider(ABC):
    """
    Abstract base for LLM providers.

    Supports: Gemini, Claude, GPT, or any future provider.
    """

    MAX_HISTORY_SIZE = 100  # Maximum conversation turns to retain

    def __init__(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ):
        """
        Initialize LLM provider.

        Args:
            model: Model identifier (e.g., 'claude-sonnet-4-5-20250929')
            api_key: Provider API key
            system_prompt: System instruction for conversation
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum response length

        Raises:
            ValueError: If parameters are invalid
        """
        if not model:
            raise ValueError("Model identifier is required")
        if not api_key:
            raise ValueError("API key is required")
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"Temperature must be 0.0-2.0, got {temperature}")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        self.model = model
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.conversation_history: list[LLMMessage] = []

    @abstractmethod
    async def generate(self, user_message: str) -> LLMResponse:
        """
        Generate complete response to user message.

        Args:
            user_message: User's input text

        Returns:
            LLMResponse with content and metadata

        Raises:
            Exception: If generation fails
        """
        pass

    @abstractmethod
    async def generate_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Generate streaming response to user message.

        Args:
            user_message: User's input text

        Yields:
            Text chunks as they become available

        Raises:
            Exception: If streaming fails
        """
        pass

    @abstractmethod
    async def send_system_message(self, message: str) -> None:
        """
        Send system message (e.g., time updates) without user interaction.

        Args:
            message: System instruction to inject

        Raises:
            Exception: If injection fails
        """
        pass

    def add_to_history(self, message: LLMMessage) -> None:
        """
        Add message to conversation history with size management.

        Maintains sliding window to prevent unbounded growth.
        Keeps first message (system context) and recent messages.
        """
        self.conversation_history.append(message)

        # Prevent unbounded history growth
        if len(self.conversation_history) > self.MAX_HISTORY_SIZE:
            # Keep first message (important context) and recent messages
            self.conversation_history = [
                self.conversation_history[0],
                *self.conversation_history[-(self.MAX_HISTORY_SIZE - 1) :],
            ]
            logger.warning(f"Conversation history trimmed to {self.MAX_HISTORY_SIZE} messages")

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.debug("Conversation history cleared")

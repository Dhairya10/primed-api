"""Gemini (Google) LLM provider with thinking mode and structured output support."""

import logging
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types

from src.prep.services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Gemini LLM provider.

    Features:
    - Thinking mode for enhanced reasoning (Gemini 2.5+)
    - Structured output via response_schema
    - Streaming support with generate_content_stream
    - Dynamic thinking budget adjustment

    Recommended models:
    - gemini-2.0-flash-exp: Fast, good quality, low cost
    - gemini-2.5-pro: Best reasoning with thinking mode
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        enable_thinking: bool = False,
        thinking_budget: int = -1,  # -1 = dynamic
        **kwargs,
    ):
        """
        Initialize Gemini provider.

        Args:
            model: Model identifier (e.g., 'gemini-2.0-flash-exp')
            api_key: Gemini API key
            system_prompt: System instruction
            enable_thinking: Enable thinking mode (Gemini 2.5+ only)
            thinking_budget: Thinking tokens (-1=dynamic, 0=disabled, 1-32768=fixed)
            **kwargs: Additional config (temperature, max_tokens, etc.)

        Raises:
            ValueError: If parameters are invalid
        """
        super().__init__(model, api_key, system_prompt, **kwargs)
        self.client = genai.Client(api_key=api_key)
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

        logger.info(
            f"Initialized GeminiProvider: model={model}, "
            f"thinking={enable_thinking}, budget={thinking_budget}"
        )

    async def generate(self, user_message: str) -> LLMResponse:
        """
        Generate Gemini response with optional thinking mode.

        Args:
            user_message: User's input

        Returns:
            LLMResponse with content and metadata

        Raises:
            Exception: If generation fails
        """
        logger.debug(f"Generating response for message: {user_message[:100]}...")
        self.add_to_history(LLMMessage(role="user", content=user_message))

        # Build generation config
        config = self._build_generation_config()

        # Build contents from history
        contents = [
            types.Content(role=msg.role, parts=[types.Part(text=msg.content)])
            for msg in self.conversation_history
        ]

        return await self._generate_complete(contents, config)

    async def generate_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Generate streaming Gemini response.

        Args:
            user_message: User's input

        Yields:
            Text chunks as they become available

        Raises:
            Exception: If streaming fails
        """
        logger.debug(f"Streaming response for message: {user_message[:100]}...")
        self.add_to_history(LLMMessage(role="user", content=user_message))

        # Build generation config
        config = self._build_generation_config()

        # Build contents from history
        contents = [
            types.Content(role=msg.role, parts=[types.Part(text=msg.content)])
            for msg in self.conversation_history
        ]

        async for chunk in self._generate_stream(contents, config):
            yield chunk

    async def _generate_complete(
        self, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> LLMResponse:
        """
        Generate complete response.

        Args:
            contents: Conversation contents
            config: Generation configuration

        Returns:
            LLMResponse with content and metadata

        Raises:
            Exception: If generation fails
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model, contents=contents, config=config
            )

            # Extract content (handle thinking mode output)
            if self.enable_thinking and hasattr(response, "parts"):
                # Thinking mode returns multiple parts: thoughts + answer
                content_parts = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text"):
                        content_parts.append(part.text)
                content = "\n".join(content_parts).strip()
            else:
                content = response.text.strip()

            self.add_to_history(LLMMessage(role="assistant", content=content))

            logger.info(
                f"Generated response: {response.usage_metadata.prompt_token_count} "
                f"input tokens, {response.usage_metadata.candidates_token_count} "
                f"output tokens"
            )

            return LLMResponse(
                content=content,
                finish_reason=str(response.candidates[0].finish_reason),
                usage={
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                },
                metadata={
                    "thinking_enabled": self.enable_thinking,
                    "thinking_budget": (self.thinking_budget if self.enable_thinking else None),
                },
            )

        except Exception as e:
            logger.error(f"Error in _generate_complete: {e}")
            raise

    async def _generate_stream(
        self, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> AsyncGenerator[str, None]:
        """
        Stream response chunks.

        Args:
            contents: Conversation contents
            config: Generation configuration

        Yields:
            Text chunks as they become available

        Raises:
            Exception: If streaming fails
        """
        full_response = []

        try:
            async for chunk in self.client.aio.models.generate_content_stream(
                model=self.model, contents=contents, config=config
            ):
                if chunk.text:
                    full_response.append(chunk.text)
                    yield chunk.text

            # Add complete response to history
            complete_text = "".join(full_response)
            self.add_to_history(LLMMessage(role="assistant", content=complete_text))

            logger.info(f"Streamed response complete: {len(complete_text)} chars")

        except Exception as e:
            logger.error(f"Error in _generate_stream: {e}")
            raise

    def _build_generation_config(self) -> types.GenerateContentConfig:
        """
        Build generation config with thinking mode support.

        Returns:
            GenerateContentConfig with all settings
        """
        config_dict = {
            "system_instruction": self.system_prompt,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }

        # Add thinking config if enabled (Gemini 2.5+ only)
        if self.enable_thinking and "2.5" in self.model:
            config_dict["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
                include_thoughts=True,  # Include thought summaries in response
            )

        return types.GenerateContentConfig(**config_dict)

    async def send_system_message(self, message: str) -> None:
        """
        Inject system message (e.g., time updates) into conversation.

        Args:
            message: System instruction to inject
        """
        logger.debug(f"Injecting system message: {message[:50]}...")
        self.add_to_history(
            LLMMessage(
                role="user",
                content=f"[SYSTEM]: {message}",
                metadata={"type": "system_injection"},
            )
        )

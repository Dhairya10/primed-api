"""Gemini (Google) LLM provider using the Interactions API."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from src.prep.config import settings
from src.prep.services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Gemini LLM provider.

    Features:
    - Interactions API for stateless conversations
    - Thinking mode with thinking_level configuration
    - Structured output via response_format
    - Server-side persistence opt-out (store=False)
    """

    _VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high"}

    def __init__(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        enable_thinking: bool = False,
        thinking_level: str = "high",
        response_format: dict[str, Any] | None = None,
        response_mime_type: str | None = None,
        store: bool = False,
        **kwargs,
    ):
        """
        Initialize Gemini provider.

        Args:
            model: Model identifier (e.g., 'gemini-2.0-flash-exp')
            api_key: Gemini API key
            system_prompt: System instruction
            enable_thinking: Enable thinking mode
            thinking_level: Thinking level (minimal|low|medium|high)
            response_format: JSON schema for structured output
            response_mime_type: Mime type for structured responses
            store: Whether to persist interaction server-side
            **kwargs: Additional config (temperature, max_tokens, etc.)

        Raises:
            ValueError: If parameters are invalid
        """
        super().__init__(model, api_key, system_prompt, **kwargs)
        self.client = genai.Client(api_key=api_key)

        # Wrap client with Opik tracking if enabled
        if settings.opik_enabled:
            try:
                from opik.integrations.genai import track_genai

                self.client = track_genai(self.client)
                logger.info("Wrapped Gemini client with Opik track_genai")
            except Exception as e:
                logger.warning(f"Failed to wrap Gemini client with Opik: {e}")

        self.enable_thinking = enable_thinking
        self.thinking_level = thinking_level
        self.response_format = response_format
        self.response_mime_type = response_mime_type
        self.store = store

        if self.enable_thinking and self.thinking_level not in self._VALID_THINKING_LEVELS:
            raise ValueError(f"thinking_level must be one of {sorted(self._VALID_THINKING_LEVELS)}")

        if self.response_format and not self.response_mime_type:
            self.response_mime_type = "application/json"

        logger.info(
            f"Initialized GeminiProvider: model={model}, "
            f"thinking={enable_thinking}, level={thinking_level}, store={store}"
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

        request_params = self._build_request_params()

        return await self._generate_complete(request_params)

    async def generate_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Generate Gemini response as a single chunk.

        Args:
            user_message: User's input

        Yields:
            Full response content in one chunk

        Raises:
            Exception: If generation fails
        """
        logger.warning("Gemini streaming is deferred; returning a single response chunk.")
        response = await self.generate(user_message)
        yield response.content

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_complete(self, request_params: dict[str, Any]) -> LLMResponse:
        """
        Generate complete response with automatic retry logic.

        Automatically retries on transient API failures with exponential backoff:
        - Maximum 3 attempts
        - Exponential backoff: 2s → 4s → 8s (capped at 10s)
        - Re-raises exception after exhausting retries

        Args:
            request_params: Interactions API request parameters

        Returns:
            LLMResponse with content and metadata

        Raises:
            Exception: If generation fails after max retries
        """
        try:
            interaction = await self.client.aio.interactions.create(**request_params)
            content = self._extract_text_from_outputs(getattr(interaction, "outputs", None))

            self.add_to_history(LLMMessage(role="assistant", content=content))

            usage = self._extract_usage(getattr(interaction, "usage", None))
            finish_reason = self._extract_finish_reason(interaction)

            logger.info(
                "Generated response: %s input tokens, %s output tokens",
                usage.get("input_tokens") if usage else None,
                usage.get("output_tokens") if usage else None,
            )

            # Extract thought summaries if thinking is enabled
            thought_summaries = []
            if self.enable_thinking:
                thought_summaries = self._extract_thought_summaries(
                    getattr(interaction, "outputs", None)
                )

            return LLMResponse(
                content=content,
                finish_reason=finish_reason,
                usage=usage,
                metadata={
                    "interaction_id": getattr(interaction, "id", None),
                    "thinking_enabled": self.enable_thinking,
                    "thinking_level": (self.thinking_level if self.enable_thinking else None),
                    "thought_summaries": thought_summaries,
                    "response_format_enabled": self.response_format is not None,
                    "store": self.store,
                },
            )

        except Exception as e:
            logger.error(f"Error in _generate_complete: {e}")
            raise

    def _build_request_params(self) -> dict[str, Any]:
        """
        Build Interactions API request parameters.
        """
        request_params: dict[str, Any] = {
            "model": self.model,
            "input": self._build_interaction_input(),
            "system_instruction": self.system_prompt,
            "generation_config": self._build_generation_config(),
            "store": self.store,
        }

        if self.response_format is not None:
            request_params["response_format"] = self.response_format
            if self.response_mime_type is not None:
                request_params["response_mime_type"] = self.response_mime_type

        return request_params

    def _build_interaction_input(self) -> list[dict[str, Any]]:
        """
        Build Interactions API input payload from conversation history.
        """
        turns: list[dict[str, Any]] = []
        for message in self.conversation_history:
            if message.role == "assistant":
                turns.append(
                    {
                        "role": "model",
                        "content": [{"type": "text", "text": message.content}],
                    }
                )
            else:
                turns.append({"role": "user", "content": message.content})
        return turns

    def _build_generation_config(self) -> dict[str, Any]:
        """
        Build generation config with thinking mode support.

        Returns:
            Dictionary with generation settings
        """
        config_dict: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }

        # Add thinking config if enabled
        if self.enable_thinking:
            config_dict["thinking_level"] = self.thinking_level
            config_dict["thinking_summaries"] = "auto"

        return config_dict

    @staticmethod
    def _get_value(obj: Any, key: str) -> Any:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def _extract_usage(self, usage: Any) -> dict[str, int] | None:
        if usage is None:
            return None
        total_input = self._get_value(usage, "total_input_tokens")
        total_output = self._get_value(usage, "total_output_tokens")
        total_tokens = self._get_value(usage, "total_tokens")
        thoughts_tokens = self._get_value(usage, "thoughts_token_count")

        usage_dict: dict[str, int] = {}
        if total_input is not None:
            usage_dict["input_tokens"] = int(total_input)
        if total_output is not None:
            usage_dict["output_tokens"] = int(total_output)
        if total_tokens is not None:
            usage_dict["total_tokens"] = int(total_tokens)
        elif total_input is not None and total_output is not None:
            usage_dict["total_tokens"] = int(total_input) + int(total_output)
        if thoughts_tokens is not None:
            usage_dict["thoughts_token_count"] = int(thoughts_tokens)

        return usage_dict or None

    def _extract_text_from_outputs(self, outputs: Any) -> str:
        """
        Extract text content from outputs, excluding thought summaries.

        Only extracts text parts that are not marked as thoughts.
        """
        if outputs is None:
            return ""
        items = outputs if isinstance(outputs, list) else [outputs]
        parts: list[str] = []
        for output in items:
            # Skip thought outputs - only extract actual response text
            output_type = self._get_value(output, "type")
            if output_type == "thought":
                continue

            text = self._get_value(output, "text")
            if text is None:
                content = self._get_value(output, "content")
                if isinstance(content, list):
                    for item in content:
                        # Skip thought parts in content
                        item_type = self._get_value(item, "type")
                        if item_type == "thought":
                            continue
                        item_text = self._get_value(item, "text")
                        if isinstance(item_text, str) and item_text:
                            parts.append(item_text)
                    continue
                text = content
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n".join(parts).strip()

    def _extract_thought_summaries(self, outputs: Any) -> list[str]:
        """
        Extract thought summaries from outputs.

        Returns:
            List of thought summary strings
        """
        thoughts = []
        if outputs is None:
            return thoughts

        items = outputs if isinstance(outputs, list) else [outputs]
        for output in items:
            # Check if this output is a thought
            if self._get_value(output, "type") == "thought":
                summary = self._get_value(output, "summary")
                if summary:
                    thoughts.append(str(summary))
                # Also check text field as fallback
                elif text := self._get_value(output, "text"):
                    thoughts.append(str(text))

        return thoughts

    def _extract_finish_reason(self, interaction: Any) -> str | None:
        outputs = self._get_value(interaction, "outputs")
        if not outputs:
            return None
        items = outputs if isinstance(outputs, list) else [outputs]
        for output in items:
            reason = self._get_value(output, "finish_reason")
            if reason:
                return str(reason)
        return None

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

"""Anthropic (Claude) LLM provider with advanced features."""

import logging
from collections.abc import AsyncGenerator

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.prep.services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Primary model: claude-sonnet-4-5-20250929

    Features:
    - Prompt caching (5-minute and 1-hour TTL)
    - Extended thinking mode (up to 64k thinking tokens)
    - Streaming with server-sent events
    - Skills integration (for evaluation workflows)
    - 200k context window (1M in beta)
    - Token counting endpoint

    Recommended usage:
    - Voice interviews: Standard Messages API with streaming
    - Post-interview evaluation: Skills API with code execution
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        system_prompt: str,
        enable_thinking: bool = False,
        thinking_budget: int = 10000,
        enable_caching: bool = True,
        cache_ttl: str = "5m",  # "5m" or "1h"
        **kwargs,
    ):
        """
        Initialize Anthropic provider.

        Args:
            model: Model identifier (e.g., 'claude-sonnet-4-5-20250929')
            api_key: Anthropic API key
            system_prompt: System instruction
            enable_thinking: Enable extended thinking mode
            thinking_budget: Max thinking tokens (1024-64000, default: 10000)
            enable_caching: Enable prompt caching
            cache_ttl: Cache time-to-live ("5m" or "1h")
            **kwargs: Additional config (temperature, max_tokens, etc.)

        Raises:
            ValueError: If parameters are invalid
        """
        super().__init__(model, api_key, system_prompt, **kwargs)

        # Validate thinking_budget range
        if enable_thinking and not (1024 <= thinking_budget <= 64000):
            raise ValueError(f"thinking_budget must be 1024-64000, got {thinking_budget}")

        # Validate cache_ttl
        if cache_ttl not in ("5m", "1h"):
            raise ValueError(f"cache_ttl must be '5m' or '1h', got {cache_ttl}")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl

        logger.info(
            f"Initialized AnthropicProvider: model={model}, "
            f"thinking={enable_thinking}, caching={enable_caching}"
        )

    async def generate(self, user_message: str) -> LLMResponse:
        """
        Generate complete Claude response with thinking and caching.

        Args:
            user_message: User's input

        Returns:
            LLMResponse with content and metadata

        Raises:
            anthropic.APIError: If API request fails
            anthropic.RateLimitError: If rate limit exceeded
        """
        logger.debug(f"Generating response for message: {user_message[:100]}...")
        self.add_to_history(LLMMessage(role="user", content=user_message))

        # Build request parameters
        request_params = self._build_request_params(stream=False)

        return await self._generate_complete(request_params)

    async def generate_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Generate streaming Claude response with thinking and caching.

        Args:
            user_message: User's input

        Yields:
            Text chunks as they become available

        Raises:
            anthropic.APIError: If API request fails
            anthropic.RateLimitError: If rate limit exceeded
        """
        logger.debug(f"Streaming response for message: {user_message[:100]}...")
        self.add_to_history(LLMMessage(role="user", content=user_message))

        # Build request parameters
        request_params = self._build_request_params(stream=True)

        async for chunk in self._stream_response(request_params):
            yield chunk

    def _build_request_params(self, stream: bool = False) -> dict:
        """
        Build request parameters for Claude API.

        Args:
            stream: Whether to stream response

        Returns:
            Dictionary of request parameters
        """
        # Build messages from history
        messages = self._build_messages()

        # Build system prompt with caching
        system = self._build_system_with_cache()

        # Build request parameters
        request_params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": messages,
            "stream": stream,
        }

        # Add thinking config if enabled
        if self.enable_thinking:
            request_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }

        return request_params

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_complete(self, request_params: dict) -> LLMResponse:
        """
        Generate complete response with retry logic.

        Retries up to 3 times with exponential backoff for transient failures.

        Args:
            request_params: API request parameters

        Returns:
            LLMResponse with content and metadata

        Raises:
            anthropic.APIError: If all retries fail
        """
        try:
            response = await self.client.messages.create(**request_params)

            # Extract content (handle thinking blocks)
            content_parts = []
            thinking_content = None

            for block in response.content:
                if block.type == "thinking":
                    thinking_content = block.thinking
                elif block.type == "text":
                    content_parts.append(block.text)

            content = "\n".join(content_parts).strip()
            self.add_to_history(LLMMessage(role="assistant", content=content))

            logger.info(
                f"Generated response: {response.usage.input_tokens} input tokens, "
                f"{response.usage.output_tokens} output tokens"
            )

            return LLMResponse(
                content=content,
                finish_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "cache_creation_input_tokens": getattr(
                        response.usage, "cache_creation_input_tokens", 0
                    ),
                    "cache_read_input_tokens": getattr(
                        response.usage, "cache_read_input_tokens", 0
                    ),
                },
                metadata={
                    "thinking_enabled": self.enable_thinking,
                    "thinking_content": thinking_content,
                    "model_id": response.model,
                    "stop_sequence": response.stop_sequence,
                },
            )

        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except anthropic.APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in _generate_complete: {e}")
            raise

    async def _stream_response(self, request_params: dict) -> AsyncGenerator[str, None]:
        """
        Stream response chunks using server-sent events with error handling.

        Handles event types:
        - message_start: Initial message metadata
        - content_block_start: Start of thinking or text block
        - content_block_delta: Incremental content (thinking_delta or text_delta)
        - content_block_stop: End of content block
        - message_delta: Usage metadata updates
        - message_stop: End of stream

        Yields:
            Text chunks as they become available

        Raises:
            anthropic.APIError: If streaming fails
        """
        full_response = []
        thinking_blocks = []

        try:
            async with self.client.messages.stream(**request_params) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            # Regular text content
                            chunk = event.delta.text
                            full_response.append(chunk)
                            yield chunk
                        elif event.delta.type == "thinking_delta":
                            # Thinking content (not yielded to user)
                            thinking_blocks.append(event.delta.thinking)

            # Add complete response to history
            complete_text = "".join(full_response)
            self.add_to_history(
                LLMMessage(
                    role="assistant",
                    content=complete_text,
                    metadata={"thinking": "".join(thinking_blocks) if thinking_blocks else None},
                )
            )

            logger.info(f"Streamed response complete: {len(complete_text)} chars")

        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded during streaming: {e}")
            raise
        except anthropic.APIConnectionError as e:
            logger.error(f"Connection error during streaming: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error during streaming: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in _stream_response: {e}")
            raise

    def _build_messages(self) -> list[dict]:
        """
        Build messages array from conversation history.

        Claude Messages API requires alternating user/assistant roles.
        """
        messages = []
        for msg in self.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def _build_system_with_cache(self) -> str | list[dict]:
        """
        Build system prompt with cache_control for prompt caching.

        System prompts are prime caching candidates since they:
        - Remain constant across conversations
        - Are typically large (interview instructions, rubrics)
        - Get reused frequently

        Returns:
            String for uncached, or list of structured blocks for cached
        """
        if not self.enable_caching:
            return self.system_prompt

        # Build cache control based on TTL
        # 5m cache: {"type": "ephemeral"} (default, no ttl field)
        # 1h cache: {"type": "ephemeral", "ttl": "1h"}
        cache_control = {"type": "ephemeral"}
        if self.cache_ttl == "1h":
            cache_control["ttl"] = "1h"

        system_blocks = [
            {
                "type": "text",
                "text": self.system_prompt,
                "cache_control": cache_control,
            }
        ]

        logger.debug(f"Built system prompt with caching: ttl={self.cache_ttl}")
        return system_blocks

    async def send_system_message(self, message: str) -> None:
        """
        Inject system message (e.g., time updates) into conversation.

        Claude requires alternating user/assistant messages. To inject system info,
        we append to the last user message or create a new user message pair.

        Args:
            message: System instruction to inject

        Raises:
            ValueError: If conversation history is in invalid state
        """
        logger.debug(f"Injecting system message: {message[:50]}...")

        # Check if last message is from assistant
        if self.conversation_history and self.conversation_history[-1].role == "assistant":
            # Create new user message with system update
            self.add_to_history(
                LLMMessage(
                    role="user",
                    content=f"[SYSTEM UPDATE]: {message}",
                    metadata={"type": "system_injection"},
                )
            )
            # Immediately add acknowledgment from assistant to maintain pattern
            self.add_to_history(
                LLMMessage(
                    role="assistant",
                    content="Understood.",
                    metadata={"type": "system_ack"},
                )
            )
        else:
            # Last message is user, append to it
            if self.conversation_history:
                last_msg = self.conversation_history[-1]
                last_msg.content += f"\n\n[SYSTEM UPDATE]: {message}"
                last_msg.metadata["has_system_injection"] = True
            else:
                # Empty history, just add user message
                self.add_to_history(
                    LLMMessage(
                        role="user",
                        content=f"[SYSTEM UPDATE]: {message}",
                        metadata={"type": "system_injection"},
                    )
                )

    async def count_tokens(self, messages: list[dict], system: str | list[dict]) -> int:
        """
        Count tokens for a request using Claude's token counting API.

        Args:
            messages: Messages array
            system: System prompt (string or structured blocks)

        Returns:
            Estimated input token count
        """
        response = await self.client.messages.count_tokens(
            model=self.model, messages=messages, system=system
        )
        return response.input_tokens

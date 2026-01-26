"""Tests for base LLM provider."""

from collections.abc import AsyncGenerator

import pytest

from src.prep.services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing base functionality."""

    async def generate(self, user_message: str) -> LLMResponse:
        """Mock generate method."""
        self.add_to_history(LLMMessage(role="user", content=user_message))
        response = LLMResponse(
            content="Mock response",
            finish_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        self.add_to_history(LLMMessage(role="assistant", content=response.content))
        return response

    async def generate_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Mock streaming method."""
        self.add_to_history(LLMMessage(role="user", content=user_message))
        chunks = ["Mock ", "streaming ", "response"]
        for chunk in chunks:
            yield chunk
        self.add_to_history(LLMMessage(role="assistant", content="".join(chunks)))

    async def send_system_message(self, message: str) -> None:
        """Mock send system message."""
        self.add_to_history(
            LLMMessage(
                role="user",
                content=f"[SYSTEM]: {message}",
                metadata={"type": "system_injection"},
            )
        )


def test_base_provider_initialization():
    """Test base provider initialization with valid parameters."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
        temperature=0.7,
        max_tokens=100,
    )

    assert provider.model == "test-model"
    assert provider.api_key == "test-key"
    assert provider.system_prompt == "You are helpful"
    assert provider.temperature == 0.7
    assert provider.max_tokens == 100
    assert len(provider.conversation_history) == 0


def test_base_provider_invalid_model():
    """Test that empty model raises ValueError."""
    with pytest.raises(ValueError, match="Model identifier is required"):
        MockLLMProvider(
            model="",
            api_key="test-key",
            system_prompt="You are helpful",
        )


def test_base_provider_invalid_api_key():
    """Test that empty API key raises ValueError."""
    with pytest.raises(ValueError, match="API key is required"):
        MockLLMProvider(
            model="test-model",
            api_key="",
            system_prompt="You are helpful",
        )


def test_base_provider_invalid_temperature():
    """Test that invalid temperature raises ValueError."""
    with pytest.raises(ValueError, match="Temperature must be 0.0-2.0"):
        MockLLMProvider(
            model="test-model",
            api_key="test-key",
            system_prompt="You are helpful",
            temperature=3.0,
        )


def test_base_provider_invalid_max_tokens():
    """Test that invalid max_tokens raises ValueError."""
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        MockLLMProvider(
            model="test-model",
            api_key="test-key",
            system_prompt="You are helpful",
            max_tokens=-1,
        )


def test_add_to_history():
    """Test adding messages to conversation history."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    msg1 = LLMMessage(role="user", content="Hello")
    msg2 = LLMMessage(role="assistant", content="Hi there")

    provider.add_to_history(msg1)
    provider.add_to_history(msg2)

    assert len(provider.conversation_history) == 2
    assert provider.conversation_history[0] == msg1
    assert provider.conversation_history[1] == msg2


def test_history_trimming():
    """Test that history is trimmed when exceeding MAX_HISTORY_SIZE."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    # Set a smaller max for testing
    provider.MAX_HISTORY_SIZE = 10

    # Add more messages than the limit
    for i in range(15):
        provider.add_to_history(
            LLMMessage(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
        )

    # Should be trimmed to MAX_HISTORY_SIZE
    assert len(provider.conversation_history) == provider.MAX_HISTORY_SIZE

    # First message should be kept
    assert provider.conversation_history[0].content == "Message 0"

    # Recent messages should be kept
    assert provider.conversation_history[-1].content == "Message 14"


def test_clear_history():
    """Test clearing conversation history."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    provider.add_to_history(LLMMessage(role="user", content="Hello"))
    provider.add_to_history(LLMMessage(role="assistant", content="Hi"))

    assert len(provider.conversation_history) == 2

    provider.clear_history()

    assert len(provider.conversation_history) == 0


@pytest.mark.asyncio
async def test_generate():
    """Test generate method."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    response = await provider.generate("Hello")

    assert response.content == "Mock response"
    assert response.finish_reason == "stop"
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 5
    assert len(provider.conversation_history) == 2


@pytest.mark.asyncio
async def test_generate_stream():
    """Test streaming generation."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    chunks = []
    async for chunk in provider.generate_stream("Hello"):
        chunks.append(chunk)

    assert chunks == ["Mock ", "streaming ", "response"]
    assert len(provider.conversation_history) == 2
    assert provider.conversation_history[-1].content == "Mock streaming response"


@pytest.mark.asyncio
async def test_send_system_message():
    """Test sending system message."""
    provider = MockLLMProvider(
        model="test-model",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    await provider.send_system_message("Time update: 5 minutes remaining")

    assert len(provider.conversation_history) == 1
    assert "[SYSTEM]" in provider.conversation_history[0].content
    assert provider.conversation_history[0].metadata["type"] == "system_injection"


def test_llm_message_creation():
    """Test LLMMessage model creation."""
    msg = LLMMessage(role="user", content="Hello")

    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.metadata == {}


def test_llm_message_with_metadata():
    """Test LLMMessage with metadata."""
    msg = LLMMessage(
        role="assistant",
        content="Response",
        metadata={"thinking": "Some thinking content"},
    )

    assert msg.metadata["thinking"] == "Some thinking content"


def test_llm_response_creation():
    """Test LLMResponse model creation."""
    response = LLMResponse(
        content="Hello",
        finish_reason="stop",
        usage={"input_tokens": 10, "output_tokens": 5},
        metadata={"model_id": "test-model"},
    )

    assert response.content == "Hello"
    assert response.finish_reason == "stop"
    assert response.usage["input_tokens"] == 10
    assert response.metadata["model_id"] == "test-model"

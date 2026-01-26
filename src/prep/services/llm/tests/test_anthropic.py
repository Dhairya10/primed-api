"""Tests for Anthropic LLM provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.prep.services.llm.anthropic import AnthropicProvider


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    with patch("src.prep.services.llm.anthropic.anthropic.AsyncAnthropic") as mock:
        yield mock


def test_anthropic_provider_initialization():
    """Test Anthropic provider initialization with valid parameters."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_thinking=False,
        enable_caching=True,
        cache_ttl="5m",
    )

    assert provider.model == "claude-sonnet-4-5-20250929"
    assert provider.enable_thinking is False
    assert provider.enable_caching is True
    assert provider.cache_ttl == "5m"
    assert provider.thinking_budget == 10000  # default


def test_anthropic_provider_invalid_thinking_budget():
    """Test that invalid thinking budget raises ValueError."""
    with pytest.raises(ValueError, match="thinking_budget must be 1024-64000"):
        AnthropicProvider(
            model="claude-sonnet-4-5-20250929",
            api_key="test-key",
            system_prompt="You are helpful",
            enable_thinking=True,
            thinking_budget=500,  # Too low
        )


def test_anthropic_provider_invalid_cache_ttl():
    """Test that invalid cache_ttl raises ValueError."""
    with pytest.raises(ValueError, match="cache_ttl must be '5m' or '1h'"):
        AnthropicProvider(
            model="claude-sonnet-4-5-20250929",
            api_key="test-key",
            system_prompt="You are helpful",
            cache_ttl="10m",  # Invalid
        )


def test_build_system_without_caching():
    """Test building system prompt without caching."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_caching=False,
    )

    system = provider._build_system_with_cache()

    assert system == "You are helpful"
    assert isinstance(system, str)


def test_build_system_with_caching_5m():
    """Test building system prompt with 5-minute caching."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_caching=True,
        cache_ttl="5m",
    )

    system = provider._build_system_with_cache()

    assert isinstance(system, list)
    assert len(system) == 1
    assert system[0]["type"] == "text"
    assert system[0]["text"] == "You are helpful"
    assert system[0]["cache_control"]["type"] == "ephemeral"
    assert "ttl" not in system[0]["cache_control"]


def test_build_system_with_caching_1h():
    """Test building system prompt with 1-hour caching."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_caching=True,
        cache_ttl="1h",
    )

    system = provider._build_system_with_cache()

    assert isinstance(system, list)
    assert len(system) == 1
    assert system[0]["cache_control"]["type"] == "ephemeral"
    assert system[0]["cache_control"]["ttl"] == "1h"


def test_build_messages():
    """Test building messages from conversation history."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    from src.prep.services.llm.base import LLMMessage

    provider.add_to_history(LLMMessage(role="user", content="Hello"))
    provider.add_to_history(LLMMessage(role="assistant", content="Hi there"))

    messages = provider._build_messages()

    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Hello"}
    assert messages[1] == {"role": "assistant", "content": "Hi there"}


def test_build_request_params_without_thinking():
    """Test building request parameters without thinking mode."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_thinking=False,
        temperature=0.7,
        max_tokens=100,
    )

    params = provider._build_request_params(stream=False)

    assert params["model"] == "claude-sonnet-4-5-20250929"
    assert params["temperature"] == 0.7
    assert params["max_tokens"] == 100
    assert params["stream"] is False
    assert "thinking" not in params


def test_build_request_params_with_thinking():
    """Test building request parameters with thinking mode."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_thinking=True,
        thinking_budget=16000,
    )

    params = provider._build_request_params(stream=False)

    assert "thinking" in params
    assert params["thinking"]["type"] == "enabled"
    assert params["thinking"]["budget_tokens"] == 16000


@pytest.mark.asyncio
async def test_send_system_message_after_assistant():
    """Test injecting system message after assistant message."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    from src.prep.services.llm.base import LLMMessage

    # Add assistant message first
    provider.add_to_history(LLMMessage(role="assistant", content="Hello"))

    await provider.send_system_message("Time update: 5 minutes")

    # Should create user message and assistant acknowledgment
    assert len(provider.conversation_history) == 3
    assert "[SYSTEM UPDATE]" in provider.conversation_history[1].content
    assert provider.conversation_history[1].role == "user"
    assert provider.conversation_history[2].role == "assistant"
    assert provider.conversation_history[2].content == "Understood."


@pytest.mark.asyncio
async def test_send_system_message_after_user():
    """Test injecting system message after user message."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    from src.prep.services.llm.base import LLMMessage

    # Add user message first
    provider.add_to_history(LLMMessage(role="user", content="Hello"))

    await provider.send_system_message("Time update: 5 minutes")

    # Should append to last user message
    assert len(provider.conversation_history) == 1
    assert "[SYSTEM UPDATE]" in provider.conversation_history[0].content
    assert provider.conversation_history[0].metadata["has_system_injection"] is True


@pytest.mark.asyncio
async def test_send_system_message_empty_history():
    """Test injecting system message with empty history."""
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    await provider.send_system_message("Time update: 5 minutes")

    # Should create new user message
    assert len(provider.conversation_history) == 1
    assert "[SYSTEM UPDATE]" in provider.conversation_history[0].content
    assert provider.conversation_history[0].role == "user"


@pytest.mark.asyncio
async def test_count_tokens(mock_anthropic_client):
    """Test token counting functionality."""
    # Setup mock
    mock_client_instance = MagicMock()
    mock_count_response = MagicMock()
    mock_count_response.input_tokens = 150
    mock_client_instance.messages.count_tokens = AsyncMock(return_value=mock_count_response)
    mock_anthropic_client.return_value = mock_client_instance

    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
    )

    messages = [{"role": "user", "content": "Hello"}]
    system = "You are helpful"

    token_count = await provider.count_tokens(messages=messages, system=system)

    assert token_count == 150
    mock_client_instance.messages.count_tokens.assert_called_once_with(
        model="claude-sonnet-4-5-20250929", messages=messages, system=system
    )


def test_thinking_budget_validation_lower_bound():
    """Test thinking budget validation at lower bound."""
    # Should accept 1024
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_thinking=True,
        thinking_budget=1024,
    )
    assert provider.thinking_budget == 1024


def test_thinking_budget_validation_upper_bound():
    """Test thinking budget validation at upper bound."""
    # Should accept 64000
    provider = AnthropicProvider(
        model="claude-sonnet-4-5-20250929",
        api_key="test-key",
        system_prompt="You are helpful",
        enable_thinking=True,
        thinking_budget=64000,
    )
    assert provider.thinking_budget == 64000

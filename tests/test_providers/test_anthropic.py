from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoopilot.agent.providers.anthropic import AnthropicProvider
from odoopilot.agent.providers.base import Message


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(id: str, name: str, input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = id
    block.name = name
    block.input = input
    return block


def _make_anthropic_response(*blocks: MagicMock) -> MagicMock:
    resp = MagicMock()
    resp.content = list(blocks)
    return resp


@pytest.mark.asyncio
async def test_chat_plain_text_response() -> None:
    provider = AnthropicProvider(api_key="test-key")
    mock_response = _make_anthropic_response(_make_text_block("Hello from Claude"))

    with patch.object(
        provider._client.messages, "create", new=AsyncMock(return_value=mock_response)
    ):
        response = await provider.chat(
            messages=[Message(role="user", content="Hello")],
            tools=[],
        )

    assert response.text == "Hello from Claude"
    assert not response.has_tool_calls


@pytest.mark.asyncio
async def test_chat_with_tool_call() -> None:
    provider = AnthropicProvider(api_key="test-key")
    tool_block = _make_tool_use_block("toolu_abc", "find_product", {"query": "Widget"})
    mock_response = _make_anthropic_response(tool_block)

    with patch.object(
        provider._client.messages, "create", new=AsyncMock(return_value=mock_response)
    ):
        response = await provider.chat(
            messages=[Message(role="user", content="Find widget")],
            tools=[{"name": "find_product", "description": "...", "parameters": {}}],
        )

    assert response.has_tool_calls
    assert response.tool_calls[0].name == "find_product"
    assert response.tool_calls[0].arguments == {"query": "Widget"}
    assert response.tool_calls[0].id == "toolu_abc"


@pytest.mark.asyncio
async def test_system_message_separated() -> None:
    """Anthropic's API takes system as a separate param, not in messages array."""
    provider = AnthropicProvider(api_key="test-key")
    mock_response = _make_anthropic_response(_make_text_block("OK"))
    captured: list = []

    async def capture(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        return mock_response

    with patch.object(provider._client.messages, "create", new=capture):
        await provider.chat(
            messages=[
                Message(role="system", content="You are a bot"),
                Message(role="user", content="Hello"),
            ],
            tools=[],
        )

    # System must be a top-level param, not inside messages
    assert "system" in captured[0]
    assert captured[0]["system"] == "You are a bot"
    for msg in captured[0]["messages"]:
        assert msg.get("role") != "system"


@pytest.mark.asyncio
async def test_text_and_tool_call_combined() -> None:
    provider = AnthropicProvider(api_key="test-key")
    mock_response = _make_anthropic_response(
        _make_text_block("Let me check that for you."),
        _make_tool_use_block("toolu_001", "find_product", {"query": "Bolt"}),
    )

    with patch.object(
        provider._client.messages, "create", new=AsyncMock(return_value=mock_response)
    ):
        response = await provider.chat(
            messages=[Message(role="user", content="Find bolt")],
            tools=[{"name": "find_product", "description": "...", "parameters": {}}],
        )

    assert "Let me check" in (response.text or "")
    assert response.has_tool_calls

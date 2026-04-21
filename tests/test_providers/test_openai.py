from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoopilot.agent.providers.base import Message
from odoopilot.agent.providers.openai import OpenAIProvider


def _make_oai_response(content: str, tool_calls: list | None = None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_chat_plain_text_response() -> None:
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
    mock_response = _make_oai_response("Hello from GPT")

    with patch.object(
        provider._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
    ):
        response = await provider.chat(
            messages=[Message(role="user", content="Hello")],
            tools=[],
        )

    assert response.text == "Hello from GPT"
    assert not response.has_tool_calls


@pytest.mark.asyncio
async def test_chat_with_tool_call() -> None:
    import json

    provider = OpenAIProvider(api_key="test-key", model="gpt-4o")

    tc = MagicMock()
    tc.id = "call_abc123"
    tc.function.name = "find_product"
    tc.function.arguments = json.dumps({"query": "Widget"})

    mock_response = _make_oai_response(content=None, tool_calls=[tc])

    with patch.object(
        provider._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
    ):
        response = await provider.chat(
            messages=[Message(role="user", content="Find widget")],
            tools=[{"name": "find_product", "description": "...", "parameters": {}}],
        )

    assert response.has_tool_calls
    assert response.tool_calls[0].name == "find_product"
    assert response.tool_calls[0].arguments == {"query": "Widget"}
    assert response.tool_calls[0].id == "call_abc123"


@pytest.mark.asyncio
async def test_chat_sends_system_message() -> None:
    provider = OpenAIProvider(api_key="test-key")
    mock_response = _make_oai_response("OK")
    captured: list = []

    async def capture(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        return mock_response

    with patch.object(provider._client.chat.completions, "create", new=capture):
        await provider.chat(
            messages=[
                Message(role="system", content="You are a bot"),
                Message(role="user", content="Hello"),
            ],
            tools=[],
        )

    messages_sent = captured[0]["messages"]
    roles = [m["role"] for m in messages_sent]
    assert "system" in roles
    assert "user" in roles

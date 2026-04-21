from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from odoopilot.agent.core import AgentCore
from odoopilot.agent.providers.base import LLMResponse, ToolCallRequest
from odoopilot.agent.tools.base import ConfirmationRequired, ToolResult
from odoopilot.channels.base import ChannelMessage
from odoopilot.storage.models import UserIdentity


def _make_identity() -> UserIdentity:
    return UserIdentity(
        odoo_user_id=2,
        odoo_password="pass",
        odoo_username="user@example.com",
        display_name="Test User",
    )


def _make_message(text: str = "Find Widget Pro") -> ChannelMessage:
    return ChannelMessage(
        channel="telegram",
        chat_id="12345",
        user_display_name="Test User",
        text=text,
    )


@pytest.mark.asyncio
async def test_handle_message_plain_text_response() -> None:
    llm = AsyncMock()
    llm.chat.return_value = LLMResponse(text="Widget Pro found: 42 units.", tool_calls=[])
    odoo = AsyncMock()
    audit = AsyncMock()
    audit.log = AsyncMock()
    channel = AsyncMock()

    agent = AgentCore(llm=llm, odoo=odoo, audit=audit)
    await agent.handle_message(msg=_make_message(), channel=channel, identity=_make_identity())

    channel.send_message.assert_called_once()
    assert "Widget Pro" in channel.send_message.call_args[0][1]


@pytest.mark.asyncio
async def test_handle_message_with_tool_call() -> None:
    llm = AsyncMock()
    # First call: tool call; second call: final text
    llm.chat.side_effect = [
        LLMResponse(
            text=None,
            tool_calls=[
                ToolCallRequest(id="tc1", name="find_product", arguments={"query": "Widget"})
            ],
        ),
        LLMResponse(text="Found Widget Pro: 42 units on hand.", tool_calls=[]),
    ]
    odoo = AsyncMock()
    audit = AsyncMock()
    audit.log = AsyncMock()
    channel = AsyncMock()

    # Patch the tool registry so we don't need a real Odoo connection
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(return_value=ToolResult(text="Widget Pro — 42 Units on hand"))
    schema = MagicMock()
    schema.name = "find_product"
    schema.description = "Find a product"
    schema.parameters = {}
    mock_tool.to_schema.return_value = schema

    import odoopilot.agent.core as core_module

    original_registry = core_module.TOOL_REGISTRY.copy()
    core_module.TOOL_REGISTRY["find_product"] = mock_tool

    try:
        agent = AgentCore(llm=llm, odoo=odoo, audit=audit)
        await agent.handle_message(msg=_make_message(), channel=channel, identity=_make_identity())
    finally:
        core_module.TOOL_REGISTRY.clear()
        core_module.TOOL_REGISTRY.update(original_registry)

    assert llm.chat.call_count == 2
    channel.send_message.assert_called_once()
    assert "Found Widget Pro" in channel.send_message.call_args[0][1]


@pytest.mark.asyncio
async def test_handle_message_tool_raises_confirmation() -> None:
    llm = AsyncMock()
    llm.chat.return_value = LLMResponse(
        text=None,
        tool_calls=[
            ToolCallRequest(id="tc1", name="confirm_sale_order", arguments={"name": "SO001"})
        ],
    )
    odoo = AsyncMock()
    audit = AsyncMock()
    audit.log = AsyncMock()
    channel = AsyncMock()

    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(
        side_effect=ConfirmationRequired(
            question="Confirm SO001 for Acme — 1,200.00?",
            payload="confirm_sale_order:1",
        )
    )
    schema = MagicMock()
    schema.name = "confirm_sale_order"
    schema.description = "Confirm a sale order"
    schema.parameters = {}
    mock_tool.to_schema.return_value = schema

    import odoopilot.agent.core as core_module

    original_registry = core_module.TOOL_REGISTRY.copy()
    core_module.TOOL_REGISTRY["confirm_sale_order"] = mock_tool

    try:
        agent = AgentCore(llm=llm, odoo=odoo, audit=audit)
        await agent.handle_message(
            msg=_make_message("Confirm SO001"), channel=channel, identity=_make_identity()
        )
    finally:
        core_module.TOOL_REGISTRY.clear()
        core_module.TOOL_REGISTRY.update(original_registry)

    # Must have sent a confirmation prompt, not a regular message
    channel.send_confirmation_prompt.assert_called_once()
    args = channel.send_confirmation_prompt.call_args
    assert "SO001" in args.kwargs.get("question", "") or "SO001" in str(args)


@pytest.mark.asyncio
async def test_handle_confirmation_cancelled() -> None:
    llm = AsyncMock()
    odoo = AsyncMock()
    audit = AsyncMock()
    audit.log = AsyncMock()
    channel = AsyncMock()

    agent = AgentCore(llm=llm, odoo=odoo, audit=audit)
    msg = ChannelMessage(
        channel="telegram",
        chat_id="12345",
        user_display_name="Test User",
        text="",
        confirmation_payload="confirm_sale_order:1",
        confirmed=False,
    )
    await agent.handle_confirmation(
        msg=msg,
        channel=channel,
        identity=_make_identity(),
        pending_tool_name="confirm_sale_order",
        pending_tool_args={"name": "SO001"},
    )

    channel.send_message.assert_called_once()
    assert "Cancelled" in channel.send_message.call_args[0][1]

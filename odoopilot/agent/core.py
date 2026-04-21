from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from odoopilot.agent.providers.base import BaseLLMProvider, Message, ToolCallRequest
from odoopilot.agent.tools import TOOL_REGISTRY
from odoopilot.agent.tools.base import ConfirmationRequired, ToolResult
from odoopilot.audit.log import AuditLogger
from odoopilot.channels.base import Channel, ChannelMessage
from odoopilot.odoo.client import OdooClient

if TYPE_CHECKING:
    from odoopilot.storage.models import UserIdentity

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are OdooPilot, an AI assistant that helps employees interact with their company's Odoo ERP system through Telegram.

You have access to tools that can read and write Odoo data. Use them to answer the user's questions accurately.

Guidelines:
- Be concise and direct. Employees are busy.
- For reads, execute the tool and summarise the result clearly.
- For writes, you must use the write tool which will prompt the user for confirmation before any data is changed.
- If you don't have a tool for what the user is asking, say so clearly.
- Never make up data. If a tool returns no results, say so.
- Format numbers with commas and 2 decimal places for currency.
"""


class AgentCore:
    """The main agent loop: receives a message, calls LLM + tools, returns a reply."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        odoo: OdooClient,
        audit: AuditLogger,
    ) -> None:
        self._llm = llm
        self._odoo = odoo
        self._audit = audit
        self._tool_schema_dicts = [
            {
                "name": t.to_schema().name,
                "description": t.to_schema().description,
                "parameters": t.to_schema().parameters,
            }
            for t in TOOL_REGISTRY.values()
        ]

    async def handle_message(
        self,
        msg: ChannelMessage,
        channel: Channel,
        identity: UserIdentity,
    ) -> None:
        """Process an inbound user message end-to-end."""
        messages: list[Message] = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=msg.text),
        ]

        for _ in range(5):  # max tool-call iterations
            response = await self._llm.chat(messages, self._tool_schema_dicts)

            if not response.has_tool_calls:
                # Final text response — send it back
                await channel.send_message(msg.chat_id, response.text or "(no response)")
                return

            # Append assistant turn with tool calls
            messages.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=response.tool_calls,
                )
            )

            # Execute each tool call
            for tc in response.tool_calls:
                tool_result = await self._dispatch_tool(
                    tc=tc,
                    msg=msg,
                    channel=channel,
                    identity=identity,
                )
                if tool_result is None:
                    # ConfirmationRequired was raised — agent is paused, reply already sent
                    return

                messages.append(
                    Message(
                        role="tool",
                        content=tool_result.text,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

        # Fallback if max iterations hit without a final response
        await channel.send_message(
            msg.chat_id, "I wasn't able to complete that request. Please try again."
        )

    async def handle_confirmation(
        self,
        msg: ChannelMessage,
        channel: Channel,
        identity: UserIdentity,
        pending_tool_name: str,
        pending_tool_args: dict[str, Any],
    ) -> None:
        """Resume a write tool after the user taps confirm/cancel."""
        if not msg.confirmed:
            await channel.send_message(msg.chat_id, "Cancelled.")
            return

        tool = TOOL_REGISTRY.get(pending_tool_name)
        if not tool:
            await channel.send_message(
                msg.chat_id, "Could not find the pending action. Please try again."
            )
            return

        try:
            result = await tool.execute(
                odoo=self._odoo,
                user_id=identity.odoo_user_id,
                password=identity.odoo_password,
                **pending_tool_args,
            )
            await self._audit.log(
                user_id=identity.odoo_user_id,
                tool=pending_tool_name,
                arguments=pending_tool_args,
                result=result.text,
                confirmed=True,
            )
            await channel.send_message(msg.chat_id, result.text)
        except Exception as exc:
            logger.exception("Error executing confirmed tool %s", pending_tool_name)
            await channel.send_message(msg.chat_id, f"Something went wrong: {exc}")

    async def _dispatch_tool(
        self,
        tc: ToolCallRequest,
        msg: ChannelMessage,
        channel: Channel,
        identity: UserIdentity,
    ) -> ToolResult | None:
        tool = TOOL_REGISTRY.get(tc.name)
        if not tool:
            return ToolResult(text=f"Unknown tool: {tc.name}", error=True)

        try:
            result = await tool.execute(
                odoo=self._odoo,
                user_id=identity.odoo_user_id,
                password=identity.odoo_password,
                **tc.arguments,
            )
            await self._audit.log(
                user_id=identity.odoo_user_id,
                tool=tc.name,
                arguments=tc.arguments,
                result=result.text,
            )
            return result

        except ConfirmationRequired as cr:
            await self._audit.log(
                user_id=identity.odoo_user_id,
                tool=tc.name,
                arguments=tc.arguments,
                result="awaiting_confirmation",
            )
            await channel.send_confirmation_prompt(
                chat_id=msg.chat_id,
                question=cr.question,
                payload=cr.payload,
            )
            return None

        except Exception as exc:
            logger.exception("Tool %s raised an error", tc.name)
            await self._audit.log(
                user_id=identity.odoo_user_id,
                tool=tc.name,
                arguments=tc.arguments,
                result=f"error: {exc}",
            )
            return ToolResult(text=f"Error running {tc.name}: {exc}", error=True)

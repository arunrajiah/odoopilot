from __future__ import annotations

import logging
from typing import Any

import anthropic as anthropic_sdk

from odoopilot.agent.providers.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolSchemaDict,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider using the official anthropic Python SDK."""

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._client = anthropic_sdk.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def chat(self, messages: list[Message], tools: list[ToolSchemaDict]) -> LLMResponse:
        system_parts = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        system_text = "\n\n".join(m.content for m in system_parts) if system_parts else None
        anthropic_messages = _build_anthropic_messages(non_system)
        anthropic_tools = [_to_anthropic_tool(t) for t in tools] if tools else []

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "messages": anthropic_messages,
        }
        if system_text:
            kwargs["system"] = system_text
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        logger.debug("Anthropic chat: model=%s tools=%d", self._model, len(anthropic_tools))
        response = await self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
        )


def _build_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "tool":
            # Tool results go as user messages with a tool_result content block
            result.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                }
            )
        elif msg.role == "assistant" and msg.tool_calls:
            # Assistant messages with tool calls use the tool_use content block
            content: list[dict[str, Any]] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            result.append({"role": "assistant", "content": content})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _to_anthropic_tool(schema: ToolSchemaDict) -> dict[str, Any]:
    return {
        "name": schema["name"],
        "description": schema["description"],
        "input_schema": schema["parameters"],
    }

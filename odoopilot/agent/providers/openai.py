from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from odoopilot.agent.providers.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolSchemaDict,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider using the official openai Python SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def chat(self, messages: list[Message], tools: list[ToolSchemaDict]) -> LLMResponse:
        oai_messages = [_to_oai_message(m) for m in messages]
        oai_tools = [_to_oai_tool(t) for t in tools] if tools else []

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
        }
        if oai_tools:
            kwargs["tools"] = oai_tools
            kwargs["tool_choice"] = "auto"

        logger.debug("OpenAI chat: model=%s tools=%d", self._model, len(oai_tools))
        response = await self._client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[ToolCallRequest] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCallRequest(id=tc.id, name=tc.function.name, arguments=args))

        return LLMResponse(text=msg.content, tool_calls=tool_calls)


def _to_oai_message(msg: Message) -> dict[str, Any]:
    if msg.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
            "content": msg.content,
        }
    if msg.role == "assistant" and msg.tool_calls:
        return {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in msg.tool_calls
            ],
        }
    result: dict[str, Any] = {"role": msg.role, "content": msg.content}
    return result


def _to_oai_tool(schema: ToolSchemaDict) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["parameters"],
        },
    }

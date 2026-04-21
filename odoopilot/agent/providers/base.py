from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCallRequest] | None = None
    name: str | None = None


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface.

    Each implementation converts internal Message/ToolSchema types to the
    provider's native format, calls the API, and normalises the response back.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchemaDict],
    ) -> LLMResponse:
        """Send a chat request and return the normalised response."""


ToolSchemaDict = dict[str, Any]  # JSON-Schema dict with name/description/parameters

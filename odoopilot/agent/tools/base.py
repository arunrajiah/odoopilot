from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from odoopilot.odoo.client import OdooClient


class ConfirmationRequired(Exception):
    """Raised by write tools to pause execution pending user confirmation."""

    def __init__(self, question: str, payload: str) -> None:
        super().__init__(question)
        self.question = question
        self.payload = payload


@dataclass
class ToolResult:
    text: str
    data: Any = field(default=None, repr=False)
    error: bool = False


@dataclass
class ToolSchema:
    """JSON-Schema representation of a tool for LLM providers."""

    name: str
    description: str
    parameters: dict[str, Any]


class BaseTool(ABC):
    """Abstract base for all Odoo intent tools."""

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[type[BaseModel]]

    @abstractmethod
    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, **kwargs: Any
    ) -> ToolResult:
        """Execute the tool and return a result.

        Write tools must call `await self.require_confirmation(question, payload)`
        before mutating Odoo data.
        """

    async def require_confirmation(self, question: str, payload: str) -> None:
        """Raise ConfirmationRequired to pause and ask the user for an explicit tap."""
        raise ConfirmationRequired(question=question, payload=payload)

    def to_schema(self) -> ToolSchema:
        schema = self.parameters.model_json_schema()
        # Remove title from the top-level schema — LLMs don't need it
        schema.pop("title", None)
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=schema,
        )

    @classmethod
    def build_error_result(cls, message: str) -> ToolResult:
        return ToolResult(text=message, error=True)

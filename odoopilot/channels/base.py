from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """Normalised inbound message from any channel."""

    channel: str
    chat_id: str
    user_display_name: str
    text: str
    raw: Any = field(default=None, repr=False)
    # Set when the message is a confirmation button tap
    confirmation_payload: str | None = None
    confirmed: bool | None = None


@dataclass
class ConfirmationButton:
    label: str
    payload: str


class Channel(ABC):
    """Abstract base class for messaging channel adapters."""

    name: str  # e.g. "telegram", "whatsapp"

    @abstractmethod
    async def send_message(self, chat_id: str, text: str) -> None:
        """Send a plain-text message to chat_id."""

    @abstractmethod
    async def send_confirmation_prompt(
        self,
        chat_id: str,
        question: str,
        payload: str,
    ) -> None:
        """Send an inline button prompt for a write confirmation.

        Implementations should render two buttons: confirm and cancel,
        each carrying the payload so the agent can resume after the tap.
        """

    @abstractmethod
    async def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        """Acknowledge a button tap (required by some platforms)."""

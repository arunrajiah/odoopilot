"""WhatsApp Cloud API channel adapter — Phase 2 stub.

The interface is fully defined here so phase 2 implementation is additive only.
"""

from __future__ import annotations

from odoopilot.channels.base import Channel


class WhatsAppChannel(Channel):
    """WhatsApp Cloud API adapter (not yet implemented — planned for v0.3)."""

    name = "whatsapp"

    async def send_message(self, chat_id: str, text: str) -> None:
        raise NotImplementedError("WhatsApp adapter is not yet implemented (planned for v0.3)")

    async def send_confirmation_prompt(self, chat_id: str, question: str, payload: str) -> None:
        raise NotImplementedError("WhatsApp adapter is not yet implemented (planned for v0.3)")

    async def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        raise NotImplementedError("WhatsApp adapter is not yet implemented (planned for v0.3)")

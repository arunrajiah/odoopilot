"""WhatsApp Cloud API client for OdooPilot."""

from __future__ import annotations

import logging
import re

import requests

_logger = logging.getLogger(__name__)

_GRAPH_API_VERSION = "v19.0"
_MESSAGES_URL = (
    f"https://graph.facebook.com/{_GRAPH_API_VERSION}/{{phone_number_id}}/messages"
)
# WhatsApp interactive button title limit
_BUTTON_TITLE_MAX = 20
# WhatsApp interactive body text limit
_BODY_MAX = 1024


def _strip_html(text: str) -> str:
    """Remove HTML tags for WhatsApp plain-text messages."""
    return re.sub(r"<[^>]+>", "", text).strip()


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Cloud API (no SDK required)."""

    def __init__(self, phone_number_id: str, access_token: str):
        self._url = _MESSAGES_URL.format(phone_number_id=phone_number_id)
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _call(self, payload: dict) -> dict:
        try:
            resp = requests.post(
                self._url, json=payload, headers=self._headers, timeout=15
            )
            data = resp.json()
            if resp.status_code >= 400:
                _logger.error("WhatsApp API error: %s", data)
            return data
        except Exception as e:
            _logger.error("WhatsApp API request failed: %s", e)
            return {}

    def send_message(self, to: str, text: str) -> dict:
        """Send a plain-text message. Strips HTML tags automatically."""
        return self._call(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": _strip_html(text)[:4096]},
            }
        )

    def send_confirmation(self, to: str, question: str) -> dict:
        """Send an interactive Yes/No button message for write-action confirmation."""
        body_text = _strip_html(question)[:_BODY_MAX]
        return self._call(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body_text},
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {"id": "confirm:yes", "title": "✅ Yes"},
                            },
                            {
                                "type": "reply",
                                "reply": {"id": "confirm:no", "title": "❌ No"},
                            },
                        ]
                    },
                },
            }
        )

    def mark_read(self, message_id: str) -> dict:
        """Mark an incoming message as read (shows double blue tick)."""
        return self._call(
            {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            }
        )

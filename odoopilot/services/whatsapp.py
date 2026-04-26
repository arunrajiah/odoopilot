"""WhatsApp Cloud API client for OdooPilot."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re

import requests

_logger = logging.getLogger(__name__)


def verify_signature(app_secret: str, raw_body: bytes, header_value: str) -> bool:
    """Verify Meta's X-Hub-Signature-256 webhook signature.

    Meta signs every WhatsApp webhook POST with HMAC-SHA256 over the raw
    request body using the App Secret. The signature is sent as the header
    ``X-Hub-Signature-256: sha256=<hex>``. Reject any request that does not
    carry a valid signature.

    Args:
        app_secret: The Meta App Secret (from App Dashboard -> Settings -> Basic).
        raw_body: The raw request body bytes (must be the exact bytes Meta sent;
            re-encoding JSON breaks the signature).
        header_value: The full value of the ``X-Hub-Signature-256`` header
            (e.g. ``"sha256=abc123..."``).

    Returns:
        True iff the signature is present, well-formed, and matches.
    """
    if not app_secret or not header_value:
        return False
    if not header_value.startswith("sha256="):
        return False
    received = header_value[len("sha256="):].strip()
    if not received:
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    # Constant-time comparison to avoid timing attacks.
    return hmac.compare_digest(received.lower(), expected.lower())

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

    def send_confirmation(self, to: str, question: str, nonce: str = "") -> dict:
        """Send an interactive Yes/No button message for write-action confirmation.

        The ``nonce`` is embedded in the button payload as ``confirm:yes:<nonce>``
        so the controller can verify the click is bound to the staged write
        currently held by the session (defends against prompt-injection swap).
        """
        body_text = _strip_html(question)[:_BODY_MAX]
        yes_payload = f"confirm:yes:{nonce}" if nonce else "confirm:yes"
        no_payload = f"confirm:no:{nonce}" if nonce else "confirm:no"
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
                                "reply": {"id": yes_payload, "title": "✅ Yes"},
                            },
                            {
                                "type": "reply",
                                "reply": {"id": no_payload, "title": "❌ No"},
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

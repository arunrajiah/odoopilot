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
    received = header_value[len("sha256=") :].strip()
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


_GRAPH_BASE = f"https://graph.facebook.com/{_GRAPH_API_VERSION}"


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Cloud API (no SDK required)."""

    def __init__(self, phone_number_id: str, access_token: str):
        self._url = _MESSAGES_URL.format(phone_number_id=phone_number_id)
        self._access_token = access_token
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

    def download_media(self, media_id: str, max_bytes: int = 25 * 1024 * 1024):
        """Download a WhatsApp media attachment (audio / voice / image / etc).

        WhatsApp's media model is two-step: the webhook gives us a
        ``media_id``; we exchange it for a temporary ``url`` via
        ``graph.facebook.com/<version>/<media_id>`` (Bearer auth), then
        download the binary from that URL with the same Bearer header.

        Returns ``(bytes, mime_type)`` on success, ``(None, "")`` on
        any failure. The ``url`` returned by Meta has its own auth
        requirement -- the same access token must be presented in the
        Authorization header on the second request, which is why we
        can't naively redirect through it.

        ``max_bytes`` matches our STT cap (25 MB) and Meta's own caps
        for audio (16 MB) and video (16 MB), with a small margin.
        """
        if not media_id or not self._access_token:
            return None, ""
        meta_url = f"{_GRAPH_BASE}/{media_id}"
        auth_header = {"Authorization": f"Bearer {self._access_token}"}
        try:
            meta_resp = requests.get(meta_url, headers=auth_header, timeout=15)
        except Exception as e:
            _logger.error(
                "WhatsApp media-id lookup failed: %s: %s",
                type(e).__name__,
                str(e),
            )
            return None, ""
        if meta_resp.status_code != 200:
            _logger.warning(
                "WhatsApp media-id lookup HTTP %s for id=%s",
                meta_resp.status_code,
                media_id,
            )
            return None, ""
        try:
            meta = meta_resp.json()
        except Exception:
            return None, ""
        download_url = meta.get("url")
        mime = meta.get("mime_type") or ""
        if not download_url:
            return None, ""
        try:
            blob_resp = requests.get(
                download_url, headers=auth_header, stream=True, timeout=30
            )
        except Exception as e:
            _logger.error(
                "WhatsApp media download failed: %s: %s",
                type(e).__name__,
                str(e),
            )
            return None, ""
        if blob_resp.status_code != 200:
            _logger.warning(
                "WhatsApp media download HTTP %s for id=%s",
                blob_resp.status_code,
                media_id,
            )
            return None, ""
        buf = bytearray()
        for chunk in blob_resp.iter_content(chunk_size=64 * 1024):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                _logger.warning(
                    "WhatsApp media id=%s exceeded %d bytes; truncating download",
                    media_id,
                    max_bytes,
                )
                return None, ""
        # Strip codec parameter from MIME (e.g. "audio/ogg; codecs=opus"
        # -> "audio/ogg") so the STT provider's filename heuristics work.
        if ";" in mime:
            mime = mime.split(";", 1)[0].strip()
        if not mime.startswith("audio/"):
            mime = "audio/ogg"  # safe default for WhatsApp voice notes
        return bytes(buf), mime

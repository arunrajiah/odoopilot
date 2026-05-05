import logging

import requests

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramClient:
    def __init__(self, token: str):
        self._token = token

    def _scrub(self, message: str) -> str:
        """Redact the bot token if it appears anywhere in a string.

        Telegram bot URLs include the bot token (``…/bot<TOKEN>/sendMessage``).
        When ``requests`` raises an exception, its ``str()`` often includes
        the request URL — which would write the bot token straight to the
        Odoo log. Scrubbing here catches that case for any path that logs
        an exception or response we built from the URL.
        """
        if not self._token or not message:
            return message
        return message.replace(self._token, "***")

    def _call(self, method: str, payload: dict) -> dict:
        url = BASE_URL.format(token=self._token, method=method)
        try:
            resp = requests.post(url, json=payload, timeout=15)
            return resp.json()
        except Exception as e:
            # Log only the exception type and a scrubbed message — never the
            # raw exception, whose ``str()`` may include the bot token URL.
            _logger.error(
                "Telegram API error (%s): %s: %s",
                method,
                type(e).__name__,
                self._scrub(str(e)),
            )
            return {}

    def send_message(self, chat_id: str, text: str, reply_markup=None) -> dict:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def send_confirmation(self, chat_id: str, question: str, nonce: str = "") -> dict:
        """Send a yes/no inline keyboard for write-action confirmation.

        The ``nonce`` is embedded in the callback_data as ``confirm:yes:<nonce>``
        so the controller can verify the click is bound to the staged write
        currently held by the session (defends against prompt-injection swap).
        Telegram callback_data is capped at 64 bytes — keep nonce short.
        """
        yes_payload = f"confirm:yes:{nonce}" if nonce else "confirm:yes"
        no_payload = f"confirm:no:{nonce}" if nonce else "confirm:no"
        markup = {
            "inline_keyboard": [
                [
                    {"text": "Yes", "callback_data": yes_payload},
                    {"text": "No", "callback_data": no_payload},
                ]
            ]
        }
        return self.send_message(chat_id, question, reply_markup=markup)

    def answer_callback_query(self, callback_query_id: str) -> dict:
        return self._call(
            "answerCallbackQuery", {"callback_query_id": callback_query_id}
        )

    # ------------------------------------------------------------------
    # Voice / audio download
    # ------------------------------------------------------------------

    def download_voice(self, file_id: str, max_bytes: int = 25 * 1024 * 1024):
        """Download a Telegram voice or audio file.

        Telegram's media model is two-step: the webhook gives us an
        opaque ``file_id``; we exchange it for a temporary
        ``file_path`` via ``getFile``, then download the audio from
        ``api.telegram.org/file/bot<token>/<file_path>``.

        Returns ``(audio_bytes, mime_type)`` on success, ``(None, "")``
        on any failure (network, missing token, oversize file, etc.).
        The caller is responsible for falling back to a polite reply.

        ``max_bytes`` caps the download as a defence-in-depth against a
        misbehaving client claiming a small file but streaming a huge
        one. The ``audio/transcriptions`` endpoint also caps at 25 MB,
        so this matches.
        """
        if not file_id or not self._token:
            return None, ""
        meta = self._call("getFile", {"file_id": file_id})
        if not meta or not meta.get("ok"):
            _logger.warning(
                "Telegram getFile failed for file_id=%s: %s",
                file_id,
                self._scrub(str(meta)[:200]),
            )
            return None, ""
        file_path = meta.get("result", {}).get("file_path")
        if not file_path:
            return None, ""
        url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        try:
            resp = requests.get(url, stream=True, timeout=30)
        except Exception as e:
            _logger.error(
                "Telegram file download failed: %s: %s",
                type(e).__name__,
                self._scrub(str(e)),
            )
            return None, ""
        if resp.status_code != 200:
            _logger.warning(
                "Telegram file download HTTP %s for path=%s",
                resp.status_code,
                file_path,
            )
            return None, ""
        # Read incrementally up to the cap; bail if oversize.
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                _logger.warning(
                    "Telegram file_id=%s exceeded %d bytes; truncating download",
                    file_id,
                    max_bytes,
                )
                return None, ""
        # Telegram voice notes are OGG/Opus; audio attachments may be
        # other types. The HTTP layer doesn't always send a useful
        # Content-Type header, so we infer from the file_path
        # extension as a fallback.
        mime = resp.headers.get("Content-Type") or ""
        if not mime.startswith("audio/"):
            if file_path.endswith(".oga") or file_path.endswith(".ogg"):
                mime = "audio/ogg"
            elif file_path.endswith(".mp3"):
                mime = "audio/mpeg"
            elif file_path.endswith(".m4a"):
                mime = "audio/m4a"
            else:
                mime = "audio/ogg"  # safe default for Telegram voice notes
        return bytes(buf), mime

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

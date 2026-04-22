import json
import logging

import requests

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramClient:
    def __init__(self, token: str):
        self._token = token

    def _call(self, method: str, payload: dict) -> dict:
        url = BASE_URL.format(token=self._token, method=method)
        try:
            resp = requests.post(url, json=payload, timeout=15)
            return resp.json()
        except Exception as e:
            _logger.error("Telegram API error (%s): %s", method, e)
            return {}

    def send_message(self, chat_id: str, text: str, reply_markup=None) -> dict:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def send_confirmation(self, chat_id: str, question: str) -> dict:
        """Send a yes/no inline keyboard for write-action confirmation."""
        markup = {
            "inline_keyboard": [[
                {"text": "Yes", "callback_data": "confirm:yes"},
                {"text": "No", "callback_data": "confirm:no"},
            ]]
        }
        return self.send_message(chat_id, question, reply_markup=markup)

    def answer_callback_query(self, callback_query_id: str) -> dict:
        return self._call("answerCallbackQuery", {"callback_query_id": callback_query_id})

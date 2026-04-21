from __future__ import annotations

import json
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from odoopilot.channels.base import Channel, ChannelMessage

logger = logging.getLogger(__name__)

# Callback data prefixes
_CONFIRM = "confirm:"
_CANCEL = "cancel:"


class TelegramChannel(Channel):
    """Telegram channel adapter using python-telegram-bot v20+."""

    name = "telegram"

    def __init__(self, token: str) -> None:
        self._bot = Bot(token=token)
        self._app = (
            Application.builder()
            .token(token)
            .updater(None)  # webhook mode — no polling
            .build()
        )
        self._message_handler: _MessageHandlerCallable | None = None
        self._confirmation_handler: _ConfirmationHandlerCallable | None = None
        self._register_handlers()

    def set_message_handler(self, handler: _MessageHandlerCallable) -> None:
        self._message_handler = handler

    def set_confirmation_handler(self, handler: _ConfirmationHandlerCallable) -> None:
        self._confirmation_handler = handler

    async def send_message(self, chat_id: str, text: str) -> None:
        await self._bot.send_message(
            chat_id=int(chat_id),
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2 if _needs_markdown(text) else None,
        )

    async def send_confirmation_prompt(
        self,
        chat_id: str,
        question: str,
        payload: str,
    ) -> None:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes \u2713", callback_data=f"{_CONFIRM}{payload}"),
                    InlineKeyboardButton("No \u2717", callback_data=f"{_CANCEL}{payload}"),
                ]
            ]
        )
        await self._bot.send_message(
            chat_id=int(chat_id),
            text=f"\u26a0\ufe0f {question}",
            reply_markup=keyboard,
        )

    async def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        await self._bot.answer_callback_query(callback_query_id=callback_query_id, text=text)

    def get_ptb_application(self) -> Application:
        return self._app

    async def process_update(self, update_data: bytes) -> None:
        update = Update.de_json(json.loads(update_data), self._bot)
        if update is None:
            return
        await self._app.process_update(update)

    # ------------------------------------------------------------------
    # Internal PTB handler registration
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("link", self._handle_link))
        self._app.add_handler(CommandHandler("help", self._handle_help))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))

    async def _handle_start(self, update: Update, context: object) -> None:
        assert update.effective_chat and update.effective_user
        await update.effective_chat.send_message(
            "Hello! I'm OdooPilot \U0001f916\n\n"
            "I can help you query and act on your Odoo data from Telegram.\n\n"
            "First, link your Odoo account with /link\n"
            "Then just send me a message like:\n"
            "  \u2022 What's the stock level for product REF-1042?\n"
            "  \u2022 Show me my open tasks\n"
            "  \u2022 List overdue invoices"
        )

    async def _handle_link(self, update: Update, context: object) -> None:
        assert update.effective_chat and update.effective_user
        chat_id = str(update.effective_chat.id)
        if self._message_handler:
            msg = ChannelMessage(
                channel=self.name,
                chat_id=chat_id,
                user_display_name=_display_name(update),
                text="/link",
                raw=update,
            )
            await self._message_handler(msg, self)
        else:
            await update.effective_chat.send_message(
                "Link flow not yet configured. Please contact your administrator."
            )

    async def _handle_help(self, update: Update, context: object) -> None:
        assert update.effective_chat
        await update.effective_chat.send_message(
            "*OdooPilot commands*\n\n"
            "/start \u2014 Introduction\n"
            "/link \u2014 Link your Odoo account\n"
            "/help \u2014 This message\n\n"
            "After linking, just type naturally:\n"
            "  \u2022 Find product widget\n"
            "  \u2022 Show my leave balance\n"
            "  \u2022 List my open tasks"
        )

    async def _handle_text(self, update: Update, context: object) -> None:
        assert update.effective_chat and update.effective_user and update.message
        if not self._message_handler:
            logger.warning("No message handler registered")
            return
        msg = ChannelMessage(
            channel=self.name,
            chat_id=str(update.effective_chat.id),
            user_display_name=_display_name(update),
            text=update.message.text or "",
            raw=update,
        )
        await self._message_handler(msg, self)

    async def _handle_callback(self, update: Update, context: object) -> None:
        assert update.callback_query and update.effective_chat
        query = update.callback_query
        await query.answer()

        data = query.data or ""
        chat_id = str(update.effective_chat.id)

        if data.startswith(_CONFIRM):
            payload = data[len(_CONFIRM) :]
            confirmed = True
        elif data.startswith(_CANCEL):
            payload = data[len(_CANCEL) :]
            confirmed = False
        else:
            return

        if not self._confirmation_handler:
            return

        msg = ChannelMessage(
            channel=self.name,
            chat_id=chat_id,
            user_display_name=_display_name(update),
            text="",
            raw=update,
            confirmation_payload=payload,
            confirmed=confirmed,
        )
        await self._confirmation_handler(msg, self)


# ------------------------------------------------------------------
# Type aliases (avoid circular imports)
# ------------------------------------------------------------------

from collections.abc import Awaitable, Callable  # noqa: E402

_MessageHandlerCallable = Callable[[ChannelMessage, "TelegramChannel"], Awaitable[None]]
_ConfirmationHandlerCallable = Callable[[ChannelMessage, "TelegramChannel"], Awaitable[None]]


def _display_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "Unknown"
    parts = [user.first_name or "", user.last_name or ""]
    return " ".join(p for p in parts if p) or user.username or str(user.id)


def _needs_markdown(text: str) -> bool:
    return any(c in text for c in ("*", "_", "`", "["))

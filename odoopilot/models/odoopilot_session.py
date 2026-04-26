import hmac
import json
import secrets
from datetime import timedelta

from odoo import api, fields, models

# Keep the last N messages per session (30 exchanges = 60 messages)
_MAX_MESSAGES = 60

# Session TTL in hours — inactive sessions older than this are garbage-collected
_SESSION_TTL_HOURS = 72


class OdooPilotSession(models.Model):
    """Conversation history per chat."""

    _name = "odoopilot.session"
    _description = "OdooPilot Conversation Session"

    channel = fields.Char(required=True)
    chat_id = fields.Char(required=True, index=True)
    messages_json = fields.Text(default="[]")
    updated_at = fields.Datetime(default=fields.Datetime.now)
    pending_tool = fields.Char()  # tool name awaiting confirmation
    pending_args = fields.Text()  # JSON args awaiting confirmation
    # Random per-write nonce embedded in the Yes/No button payload.
    # The controller verifies the click carries this exact nonce before
    # executing the staged write. Defends against prompt-injection attacks
    # that try to swap the staged tool between staging and confirmation.
    pending_nonce = fields.Char()

    _sql_constraints = [
        ("unique_channel_chat", "UNIQUE(channel, chat_id)", "One session per chat."),
    ]

    @api.model
    def get_or_create(self, channel, chat_id):
        session = self.search(
            [("channel", "=", channel), ("chat_id", "=", chat_id)], limit=1
        )
        if not session:
            session = self.create({"channel": channel, "chat_id": chat_id})
        return session

    def get_messages(self):
        return json.loads(self.messages_json or "[]")

    def append_message(self, role, content):
        msgs = self.get_messages()
        msgs.append({"role": role, "content": content})
        if len(msgs) > _MAX_MESSAGES:
            msgs = msgs[-_MAX_MESSAGES:]
        self.write(
            {"messages_json": json.dumps(msgs), "updated_at": fields.Datetime.now()}
        )

    def clear_pending(self):
        self.write(
            {"pending_tool": False, "pending_args": False, "pending_nonce": False}
        )

    def stage_pending(self, tool_name: str, args: dict) -> str:
        """Store a pending write and return a freshly generated nonce.

        Each call generates a new random nonce, overwriting any previous
        staged write. The caller (the messaging client) embeds the nonce in
        the Yes/No button payload so the confirmation handler can verify the
        click is bound to *this* specific staged write.
        """
        nonce = secrets.token_urlsafe(12)  # ~16 chars, fits Telegram's 64B limit
        self.write(
            {
                "pending_tool": tool_name,
                "pending_args": json.dumps(args),
                "pending_nonce": nonce,
            }
        )
        return nonce

    def verify_and_consume_nonce(self, candidate: str) -> bool:
        """Constant-time check that ``candidate`` matches the stored nonce.

        Returns False (and does NOT clear the pending write) if either side
        is empty or the values differ, so a forged confirmation cannot
        invalidate a legitimate one.
        """
        stored = self.pending_nonce or ""
        if not stored or not candidate:
            return False
        return hmac.compare_digest(stored, candidate)

    @api.model
    def _gc_old_sessions(self):
        """Cron: delete sessions inactive for longer than _SESSION_TTL_HOURS."""
        cutoff = fields.Datetime.now() - timedelta(hours=_SESSION_TTL_HOURS)
        self.search([("updated_at", "<", cutoff)]).unlink()

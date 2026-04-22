import json
from datetime import datetime, timedelta

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
        self.write({"pending_tool": False, "pending_args": False})

    @api.model
    def _gc_old_sessions(self):
        """Cron: delete sessions inactive for longer than _SESSION_TTL_HOURS."""
        cutoff = datetime.utcnow() - timedelta(hours=_SESSION_TTL_HOURS)
        self.search([("updated_at", "<", cutoff)]).unlink()

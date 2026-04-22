from odoo import api, fields, models


class MailGatewayAISession(models.Model):
    """Conversation history per chat (last 20 messages, 24h TTL)."""

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
        import json

        return json.loads(self.messages_json or "[]")

    def append_message(self, role, content):
        import json

        msgs = self.get_messages()
        msgs.append({"role": role, "content": content})
        # Keep last 20 exchanges
        if len(msgs) > 40:
            msgs = msgs[-40:]
        self.write(
            {"messages_json": json.dumps(msgs), "updated_at": fields.Datetime.now()}
        )

    @api.model
    def _gc_old_sessions(self):
        """Cron: delete sessions older than 24h."""
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.search([("updated_at", "<", cutoff)]).unlink()

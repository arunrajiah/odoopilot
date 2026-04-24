from odoo import api, fields, models

from ..services import notifications

# Supported languages — ISO 639-1 code → display name shown in the UI
LANGUAGE_CHOICES = [
    ("", "Auto-detect"),
    ("en", "English"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("ar", "Arabic"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ru", "Russian"),
    ("tr", "Turkish"),
    ("pl", "Polish"),
    ("hi", "Hindi"),
]


class OdooPilotIdentity(models.Model):
    """Links an Odoo user to a messaging channel (Telegram / WhatsApp)."""

    _name = "odoopilot.identity"
    _description = "OdooPilot User Identity"

    user_id = fields.Many2one(
        "res.users", string="Odoo User", required=True, ondelete="cascade"
    )
    channel = fields.Selection(
        [("telegram", "Telegram"), ("whatsapp", "WhatsApp")],
        required=True,
    )
    chat_id = fields.Char(required=True)
    display_name_channel = fields.Char(string="Channel Display Name")
    active = fields.Boolean(default=True)
    linked_at = fields.Datetime(readonly=True)
    language = fields.Selection(
        LANGUAGE_CHOICES,
        string="Language",
        default="",
        help="Preferred language for bot replies. Leave empty to auto-detect from user messages.",
    )

    _sql_constraints = [
        (
            "unique_channel_chat",
            "UNIQUE(channel, chat_id)",
            "This chat is already linked to a user.",
        ),
    ]

    @api.model
    def _cron_task_digest(self):
        """Cron entry point: send daily task digest to all linked users."""
        notifications.send_task_digest(self.env)

    @api.model
    def _cron_invoice_alerts(self):
        """Cron entry point: send overdue invoice alerts to linked users with accounting access."""
        notifications.send_invoice_alerts(self.env)

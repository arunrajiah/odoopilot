from odoo import api, fields, models

from ..services import notifications


class OdooPilotIdentity(models.Model):
    """Links an Odoo user to a Telegram chat ID."""

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

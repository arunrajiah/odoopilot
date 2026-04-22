import json
import secrets
import time

from odoo import api, fields, models


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
    def action_generate_link_url(self):
        """Generate a one-time linking token and redirect the user to the linking page."""
        token = secrets.token_urlsafe(32)
        expiry = int(time.time()) + 3600  # 1 hour
        self.env["ir.config_parameter"].sudo().set_param(
            f"odoopilot.link_token.{token}",
            json.dumps({"user_id": self.env.user.id, "exp": expiry}),
        )
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        link_url = f"{base_url.rstrip('/')}/odoopilot/link/start?token={token}"
        return {"type": "ir.actions.act_url", "url": link_url, "target": "new"}

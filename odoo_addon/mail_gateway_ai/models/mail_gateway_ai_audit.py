from odoo import fields, models


class MailGatewayAIAudit(models.Model):
    """Read-only audit log written by the OdooPilot service via JSON-RPC."""

    _name = "mail.gateway.ai.audit"
    _description = "OdooPilot Audit Log"
    _order = "timestamp desc"
    _rec_name = "tool_name"

    timestamp = fields.Datetime(string="Timestamp", readonly=True, required=True)
    user_id = fields.Many2one("res.users", string="User", readonly=True, ondelete="set null")
    channel = fields.Char(string="Channel", readonly=True)
    tool_name = fields.Char(string="Tool", readonly=True, required=True)
    tool_args = fields.Text(string="Arguments", readonly=True)
    result_summary = fields.Text(string="Result", readonly=True)
    success = fields.Boolean(string="Success", readonly=True, default=True)
    error_message = fields.Char(string="Error", readonly=True)

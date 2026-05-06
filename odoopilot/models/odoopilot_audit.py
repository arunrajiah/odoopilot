from odoo import api, fields, models


class OdooPilotAudit(models.Model):
    """Read-only audit log for every OdooPilot tool call."""

    _name = "odoopilot.audit"
    _description = "OdooPilot Audit Log"
    _order = "timestamp desc"
    _rec_name = "display_name_audit"

    # ``string=`` deliberately omitted on every field where the
    # auto-derived label is the same word capitalised. Odoo
    # generates the same label automatically; carrying the redundant
    # parameter trips pylint-odoo W8113. Where we DO override (e.g.
    # ``Tool`` for ``tool_name``, ``Result`` for ``result_summary``)
    # the override is kept because the field name has a suffix the
    # default capitalisation can't drop.
    timestamp = fields.Datetime(readonly=True, required=True)
    user_id = fields.Many2one("res.users", readonly=True, ondelete="set null")
    channel = fields.Char(readonly=True)
    tool_name = fields.Char(string="Tool", readonly=True, required=True)
    tool_args = fields.Text(string="Arguments", readonly=True)
    result_summary = fields.Text(string="Result", readonly=True)
    success = fields.Boolean(readonly=True, default=True)
    error_message = fields.Char(string="Error", readonly=True)
    display_name_audit = fields.Char(
        string="Name", compute="_compute_display_name_audit", store=False
    )

    @api.depends("tool_name", "user_id", "timestamp")
    def _compute_display_name_audit(self):
        for rec in self:
            ts = rec.timestamp.strftime("%Y-%m-%d %H:%M") if rec.timestamp else ""
            user = rec.user_id.name or "?"
            rec.display_name_audit = f"[{rec.tool_name}] {user} — {ts}"

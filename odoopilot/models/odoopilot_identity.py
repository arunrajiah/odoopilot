from datetime import timedelta

from odoo import api, fields, models

from ..services import notifications

# Window used by the activity-summary computed fields on the identity.
# Wide enough to include weekly users without dragging in stale data.
_ACTIVITY_WINDOW_DAYS = 7

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

    # ------------------------------------------------------------------
    # Activity summary (computed from odoopilot.audit)
    # ------------------------------------------------------------------
    #
    # Three live-computed fields surface the most useful "is this identity
    # actually being used?" signal without the operator having to dig into
    # the audit log. They are not stored — value is freshly read from the
    # audit table on every list-view fetch. Acceptable for typical
    # deployments (small N of identities); revisit if installs ever
    # exceed a few hundred linked users.

    last_activity = fields.Datetime(
        string="Last Activity",
        compute="_compute_activity",
        compute_sudo=True,
        help="Timestamp of the most recent audit log entry attributed to "
        "this identity, or empty if there has been no activity.",
    )
    message_count_7d = fields.Integer(
        string="Messages (7d)",
        compute="_compute_activity",
        compute_sudo=True,
        help=f"Number of audit entries in the last {_ACTIVITY_WINDOW_DAYS} days.",
    )
    success_rate_7d = fields.Integer(
        string="Success Rate (7d, %)",
        compute="_compute_activity",
        compute_sudo=True,
        help="Percentage of audit entries in the activity window that "
        "succeeded. Useful as a cheap health signal — sustained low "
        "values usually mean a misconfigured permission or LLM call.",
    )

    @api.depends("user_id", "channel")
    def _compute_activity(self):
        """Populate last_activity / message_count_7d / success_rate_7d.

        Uses one ``read_group`` per recordset to avoid the N+1 trap. The
        audit model is system-only, so we explicitly sudo() the read; the
        identity view itself is admin-gated by the menu, but a future
        portal-user view should still work without re-implementing this.
        """
        cutoff = fields.Datetime.now() - timedelta(days=_ACTIVITY_WINDOW_DAYS)
        audit = self.env["odoopilot.audit"].sudo()

        # Fast path: bail early on an empty recordset.
        if not self:
            return

        # Pull last_activity in one query, keyed by (user_id, channel).
        last_rows = audit.read_group(
            domain=[
                ("user_id", "in", self.user_id.ids),
                ("channel", "in", list({i.channel for i in self if i.channel})),
            ],
            fields=["timestamp:max"],
            groupby=["user_id", "channel"],
            lazy=False,
        )
        last_lookup: dict[tuple[int, str], object] = {
            (r["user_id"][0] if r["user_id"] else 0, r["channel"] or ""): r["timestamp"]
            for r in last_rows
        }

        # Pull window-scoped count and success-count in one query.
        window_rows = audit.read_group(
            domain=[
                ("user_id", "in", self.user_id.ids),
                ("channel", "in", list({i.channel for i in self if i.channel})),
                ("timestamp", ">=", cutoff),
            ],
            fields=["__count", "success"],
            groupby=["user_id", "channel", "success"],
            lazy=False,
        )
        # Build {(uid, channel): {"total": N, "ok": K}}
        counts: dict[tuple[int, str], dict[str, int]] = {}
        for r in window_rows:
            key = (
                r["user_id"][0] if r["user_id"] else 0,
                r["channel"] or "",
            )
            bucket = counts.setdefault(key, {"total": 0, "ok": 0})
            bucket["total"] += r["__count"]
            if r["success"]:
                bucket["ok"] += r["__count"]

        for ident in self:
            key = (ident.user_id.id, ident.channel)
            ident.last_activity = last_lookup.get(key) or False
            bucket = counts.get(key, {"total": 0, "ok": 0})
            ident.message_count_7d = bucket["total"]
            ident.success_rate_7d = (
                int(round(100 * bucket["ok"] / bucket["total"]))
                if bucket["total"]
                else 0
            )

    # ------------------------------------------------------------------
    # Action buttons (used by the identity form view)
    # ------------------------------------------------------------------

    def action_view_audit(self):
        """Open the audit log filtered to this identity's user + channel."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Activity: {self.user_id.name} ({self.channel})",
            "res_model": "odoopilot.audit",
            "view_mode": "list,form",
            "domain": [
                ("user_id", "=", self.user_id.id),
                ("channel", "=", self.channel),
            ],
            "context": {"search_default_group_by_tool": 1},
        }

    # ------------------------------------------------------------------
    # Cron entry points
    # ------------------------------------------------------------------

    @api.model
    def _cron_task_digest(self):
        """Cron entry point: send daily task digest to all linked users."""
        notifications.send_task_digest(self.env)

    @api.model
    def _cron_invoice_alerts(self):
        """Cron entry point: send overdue invoice alerts to linked users with accounting access."""
        notifications.send_invoice_alerts(self.env)

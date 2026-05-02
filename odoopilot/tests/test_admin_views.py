"""Tests for the operator-facing admin views shipped in 17.0.12.

The view XML itself is exercised by the existing ``xml-check`` CI job
(every XML file must parse). The interesting behavioural surface is
the activity-summary fields computed on ``odoopilot.identity`` from
``odoopilot.audit`` rows, which the redesigned list view exposes as
columns and the form view exposes as smart-button stat fields.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestIdentityActivitySummary(TransactionCase):
    """Computed last_activity / message_count_7d / success_rate_7d.

    The fields are non-stored ``compute=`` fields; these tests pin the
    contract so a future change to the computation can't silently regress
    the dashboard the operator looks at after install.
    """

    def setUp(self):
        super().setUp()
        # Use the admin user for the linked-user side; we only need a
        # valid res.users id.
        self.user = self.env.ref("base.user_admin")
        self.identity = self.env["odoopilot.identity"].create(
            {
                "user_id": self.user.id,
                "channel": "telegram",
                "chat_id": "100001",
            }
        )

    # ------------------------------------------------------------------
    # last_activity
    # ------------------------------------------------------------------

    def test_no_audit_yields_empty_last_activity(self):
        # Fresh identity with no audit rows: last_activity must be falsy.
        self.assertFalse(self.identity.last_activity)
        self.assertEqual(self.identity.message_count_7d, 0)
        self.assertEqual(self.identity.success_rate_7d, 0)

    def test_last_activity_picks_most_recent_audit(self):
        old = fields.Datetime.now() - timedelta(days=2)
        new = fields.Datetime.now() - timedelta(hours=1)
        self.env["odoopilot.audit"].create(
            {
                "timestamp": old,
                "user_id": self.user.id,
                "channel": "telegram",
                "tool_name": "get_my_tasks",
                "result_summary": "old call",
                "success": True,
            }
        )
        self.env["odoopilot.audit"].create(
            {
                "timestamp": new,
                "user_id": self.user.id,
                "channel": "telegram",
                "tool_name": "get_sale_orders",
                "result_summary": "new call",
                "success": True,
            }
        )
        self.identity.invalidate_recordset(["last_activity"])
        # The newer timestamp wins.
        self.assertEqual(
            self.identity.last_activity.replace(microsecond=0),
            new.replace(microsecond=0),
        )

    # ------------------------------------------------------------------
    # message_count_7d / success_rate_7d
    # ------------------------------------------------------------------

    def test_window_excludes_rows_older_than_seven_days(self):
        eight_days_ago = fields.Datetime.now() - timedelta(days=8)
        self.env["odoopilot.audit"].create(
            {
                "timestamp": eight_days_ago,
                "user_id": self.user.id,
                "channel": "telegram",
                "tool_name": "get_my_tasks",
                "result_summary": "stale",
                "success": True,
            }
        )
        self.identity.invalidate_recordset(["message_count_7d", "success_rate_7d"])
        # Outside the 7-day window: not counted.
        self.assertEqual(self.identity.message_count_7d, 0)

    def test_success_rate_rounded_correctly(self):
        # 3 of 4 successful = 75%.
        ts = fields.Datetime.now() - timedelta(hours=1)
        for ok in [True, True, True, False]:
            self.env["odoopilot.audit"].create(
                {
                    "timestamp": ts,
                    "user_id": self.user.id,
                    "channel": "telegram",
                    "tool_name": "get_my_tasks",
                    "result_summary": "x",
                    "success": ok,
                }
            )
        self.identity.invalidate_recordset(["message_count_7d", "success_rate_7d"])
        self.assertEqual(self.identity.message_count_7d, 4)
        self.assertEqual(self.identity.success_rate_7d, 75)

    def test_other_channel_not_counted(self):
        # An audit row from the same user but a different channel must
        # not roll into this Telegram identity's counters.
        ts = fields.Datetime.now() - timedelta(hours=1)
        self.env["odoopilot.audit"].create(
            {
                "timestamp": ts,
                "user_id": self.user.id,
                "channel": "whatsapp",
                "tool_name": "get_my_tasks",
                "result_summary": "wa",
                "success": True,
            }
        )
        self.identity.invalidate_recordset(["message_count_7d"])
        self.assertEqual(self.identity.message_count_7d, 0)

    def test_other_user_not_counted(self):
        # Audit rows belonging to a different Odoo user are isolated.
        other_user = self.env["res.users"].create(
            {
                "name": "Other admin",
                "login": "other_admin_test",
            }
        )
        ts = fields.Datetime.now() - timedelta(hours=1)
        self.env["odoopilot.audit"].create(
            {
                "timestamp": ts,
                "user_id": other_user.id,
                "channel": "telegram",
                "tool_name": "get_my_tasks",
                "result_summary": "other",
                "success": True,
            }
        )
        self.identity.invalidate_recordset(["message_count_7d"])
        self.assertEqual(self.identity.message_count_7d, 0)

    # ------------------------------------------------------------------
    # action_view_audit
    # ------------------------------------------------------------------

    def test_action_view_audit_returns_filtered_action(self):
        action = self.identity.action_view_audit()
        self.assertEqual(action["res_model"], "odoopilot.audit")
        # Domain must scope to this identity's user + channel.
        domain = action["domain"]
        self.assertIn(("user_id", "=", self.user.id), domain)
        self.assertIn(("channel", "=", "telegram"), domain)

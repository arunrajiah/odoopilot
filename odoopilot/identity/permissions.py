"""Permission enforcement notes.

All Odoo calls are made with the linked user's uid + password, so Odoo's
own access control (record rules, group membership) enforces permissions
server-side. OdooPilot does not reimplement access control.

This module provides helper utilities for the layer above (agent core) to
check whether an action should even be attempted before hitting Odoo.
"""

from __future__ import annotations

from odoopilot.storage.models import UserIdentity


def is_linked(identity: UserIdentity | None) -> bool:
    return identity is not None


WRITE_TOOLS = frozenset(
    {
        "confirm_sale_order",
        "log_lead_activity",
        "request_leave",
        "approve_leave",
        "submit_expense",
        "log_timesheet_entry",
        "update_ticket_status",
    }
)


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS

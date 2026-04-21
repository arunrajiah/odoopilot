from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient

_LEAVE_STATE_LABELS = {
    "draft": "To Submit",
    "confirm": "Confirmed",
    "validate1": "Second Approval",
    "validate": "Approved",
    "refuse": "Refused",
}


class MyLeaveBalanceInput(BaseModel):
    leave_type: str | None = Field(
        default=None, description="Leave type name filter, e.g. 'Annual Leave'"
    )


class RequestLeaveInput(BaseModel):
    leave_type: str = Field(description="Type of leave, e.g. 'Annual Leave', 'Sick Leave'")
    date_from: str = Field(description="Start date in YYYY-MM-DD format")
    date_to: str = Field(description="End date in YYYY-MM-DD format")
    reason: str | None = Field(default=None, description="Optional reason for the leave")


class ListTeamLeavesInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class ApproveLeaveInput(BaseModel):
    employee_name: str = Field(description="Employee name whose leave to approve")
    leave_type: str | None = Field(default=None, description="Leave type filter (optional)")


class MyLeaveBalance(BaseTool):
    """Check the current user's leave balances."""

    name = "my_leave_balance"
    description = "Check your remaining leave balance by type (e.g. Annual Leave, Sick Leave)."
    parameters = MyLeaveBalanceInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        leave_type: str | None = None,
        **_: Any,
    ) -> ToolResult:
        # Get the employee record for this user
        employees = await odoo.search_read(
            model="hr.employee",
            domain=[["user_id", "=", user_id]],
            fields=["id", "name"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not employees:
            return ToolResult(text="No employee record found for your user. Contact HR.")

        employee_id = employees[0]["id"]
        domain: list[Any] = [
            ["employee_id", "=", employee_id],
            ["state", "=", "validate"],
            ["holiday_type", "=", "employee"],
        ]
        if leave_type:
            domain.append(["holiday_status_id.name", "ilike", leave_type])

        allocations = await odoo.search_read(
            model="hr.leave.allocation",
            domain=domain,
            fields=["holiday_status_id", "number_of_days", "number_of_days_display"],
            uid=user_id,
            password=password,
        )
        if not allocations:
            return ToolResult(text="No approved leave allocations found.")

        lines = []
        for a in allocations:
            lt = a["holiday_status_id"][1] if isinstance(a["holiday_status_id"], list) else "—"
            days = a.get("number_of_days", 0)
            lines.append(f"• {lt}: {days:.1f} days allocated")

        return ToolResult(
            text=f"Leave balances for {employees[0]['name']}:\n" + "\n".join(lines),
            data=allocations,
        )


class ListTeamLeaves(BaseTool):
    """List upcoming or pending leaves for the team."""

    name = "list_team_leaves"
    description = "List confirmed and approved leaves for your team members."
    parameters = ListTeamLeavesInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, limit: int = 10, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="hr.leave",
            domain=[["state", "in", ["confirm", "validate1", "validate"]]],
            fields=[
                "employee_id",
                "holiday_status_id",
                "date_from",
                "date_to",
                "state",
                "number_of_days",
            ],
            limit=limit,
            order="date_from asc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No upcoming team leaves found.")

        lines = []
        for r in records:
            emp = r["employee_id"][1] if isinstance(r["employee_id"], list) else "—"
            lt = r["holiday_status_id"][1] if isinstance(r["holiday_status_id"], list) else "—"
            state = _LEAVE_STATE_LABELS.get(r.get("state", ""), r.get("state", ""))
            days = r.get("number_of_days", 0)
            date_from = str(r.get("date_from", ""))[:10]
            date_to = str(r.get("date_to", ""))[:10]
            lines.append(f"• {emp} | {lt} | {date_from} → {date_to} | {days:.0f}d | {state}")

        return ToolResult(text=f"{len(records)} leave(s):\n" + "\n".join(lines), data=records)


class RequestLeave(BaseTool):
    """Submit a leave request (write — requires confirmation)."""

    name = "request_leave"
    description = (
        "Submit a leave request on behalf of the current user. "
        "Requires confirmation before creating the record in Odoo."
    )
    parameters = RequestLeaveInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        leave_type: str,
        date_from: str,
        date_to: str,
        reason: str | None = None,
        **_: Any,
    ) -> ToolResult:
        # Resolve leave type id
        lt_records = await odoo.search_read(
            model="hr.leave.type",
            domain=[["name", "ilike", leave_type]],
            fields=["id", "name"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not lt_records:
            return ToolResult(text=f'Leave type "{leave_type}" not found.')

        lt = lt_records[0]
        await self.require_confirmation(
            question=f"Request {lt['name']} from {date_from} to {date_to}?",
            payload=f"request_leave:{lt['id']}:{date_from}:{date_to}",
        )
        employees = await odoo.search_read(
            model="hr.employee",
            domain=[["user_id", "=", user_id]],
            fields=["id"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not employees:
            return ToolResult(text="No employee record found for your user.")

        values: dict[str, Any] = {
            "holiday_status_id": lt["id"],
            "employee_id": employees[0]["id"],
            "date_from": f"{date_from} 08:00:00",
            "date_to": f"{date_to} 17:00:00",
            "holiday_type": "employee",
        }
        if reason:
            values["name"] = reason

        await odoo.execute_kw(
            model="hr.leave",
            method="create",
            args=[values],
            uid=user_id,
            password=password,
        )
        return ToolResult(
            text=f"Leave request submitted: {lt['name']} from {date_from} to {date_to}."
        )


class ApproveLeave(BaseTool):
    """Approve a pending leave request (write — managers only, requires confirmation)."""

    name = "approve_leave"
    description = (
        "Approve a pending leave request for an employee. "
        "Only works if your Odoo user has leave approval rights. Requires confirmation."
    )
    parameters = ApproveLeaveInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        employee_name: str,
        leave_type: str | None = None,
        **_: Any,
    ) -> ToolResult:
        domain: list[Any] = [
            ["employee_id.name", "ilike", employee_name],
            ["state", "in", ["confirm", "validate1"]],
        ]
        if leave_type:
            domain.append(["holiday_status_id.name", "ilike", leave_type])

        records = await odoo.search_read(
            model="hr.leave",
            domain=domain,
            fields=["id", "employee_id", "holiday_status_id", "date_from", "date_to"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'No pending leave found for "{employee_name}".')

        r = records[0]
        emp = r["employee_id"][1] if isinstance(r["employee_id"], list) else employee_name
        lt = r["holiday_status_id"][1] if isinstance(r["holiday_status_id"], list) else ""
        date_from = str(r.get("date_from", ""))[:10]
        date_to = str(r.get("date_to", ""))[:10]

        await self.require_confirmation(
            question=f"Approve {lt} for {emp} ({date_from} → {date_to})?",
            payload=f"approve_leave:{r['id']}",
        )
        await odoo.execute_kw(
            model="hr.leave",
            method="action_validate",
            args=[[r["id"]]],
            uid=user_id,
            password=password,
        )
        return ToolResult(text=f"Leave approved for {emp}: {lt} ({date_from} → {date_to}).")

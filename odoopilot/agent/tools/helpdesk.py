from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient

_TICKET_FIELDS = [
    "name",
    "partner_name",
    "stage_id",
    "user_id",
    "priority",
    "ticket_type_id",
    "description",
]
_PRIORITY_LABELS = {"0": "Normal", "1": "Low", "2": "High", "3": "Very High"}


class ListMyTicketsInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    open_only: bool = Field(default=True, description="Only show open (non-closed) tickets")


class GetTicketInput(BaseModel):
    name: str = Field(description="Ticket number or name (partial match)")


class UpdateTicketStatusInput(BaseModel):
    ticket_name: str = Field(description="Ticket number or name")
    new_stage: str = Field(description="New stage name, e.g. 'In Progress', 'Solved', 'Closed'")
    note: str | None = Field(
        default=None, description="Optional note to log with the status change"
    )


class ListMyTickets(BaseTool):
    """List helpdesk tickets assigned to the current user."""

    name = "list_my_tickets"
    description = "List helpdesk tickets assigned to you. Optionally include closed tickets."
    parameters = ListMyTicketsInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        limit: int = 10,
        open_only: bool = True,
        **_: Any,
    ) -> ToolResult:
        domain: list[Any] = [["user_id", "=", user_id]]
        if open_only:
            domain.append(["stage_id.is_close", "=", False])

        records = await odoo.search_read(
            model="helpdesk.ticket",
            domain=domain,
            fields=_TICKET_FIELDS,
            limit=limit,
            order="priority desc, id desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No helpdesk tickets assigned to you.")

        lines = []
        for r in records:
            stage = r["stage_id"][1] if isinstance(r["stage_id"], list) else "—"
            priority = _PRIORITY_LABELS.get(str(r.get("priority", "0")), "Normal")
            partner = r.get("partner_name") or "—"
            lines.append(f"• {r['name']} | {partner} | {stage} | {priority}")

        return ToolResult(text=f"{len(records)} ticket(s):\n" + "\n".join(lines), data=records)


class GetTicket(BaseTool):
    """Get details of a specific helpdesk ticket."""

    name = "get_ticket"
    description = "Get the details of a helpdesk ticket by its number or name."
    parameters = GetTicketInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="helpdesk.ticket",
            domain=[["name", "ilike", name]],
            fields=_TICKET_FIELDS,
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Ticket "{name}" not found.')

        r = records[0]
        stage = r["stage_id"][1] if isinstance(r["stage_id"], list) else "—"
        assigned = r["user_id"][1] if isinstance(r["user_id"], list) else "Unassigned"
        priority = _PRIORITY_LABELS.get(str(r.get("priority", "0")), "Normal")
        ticket_type = r["ticket_type_id"][1] if isinstance(r.get("ticket_type_id"), list) else "—"

        return ToolResult(
            text=(
                f"*{r['name']}*\n"
                f"Customer: {r.get('partner_name') or '—'}\n"
                f"Type: {ticket_type}\n"
                f"Stage: {stage}\n"
                f"Assigned to: {assigned}\n"
                f"Priority: {priority}"
            ),
            data=records[0],
        )


class UpdateTicketStatus(BaseTool):
    """Move a helpdesk ticket to a new stage (write — requires confirmation)."""

    name = "update_ticket_status"
    description = (
        "Move a helpdesk ticket to a new stage (e.g. In Progress, Solved, Closed). "
        "Requires user confirmation before updating."
    )
    parameters = UpdateTicketStatusInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        ticket_name: str,
        new_stage: str,
        note: str | None = None,
        **_: Any,
    ) -> ToolResult:
        tickets = await odoo.search_read(
            model="helpdesk.ticket",
            domain=[["name", "ilike", ticket_name]],
            fields=["id", "name"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not tickets:
            return ToolResult(text=f'Ticket "{ticket_name}" not found.')

        stages = await odoo.search_read(
            model="helpdesk.stage",
            domain=[["name", "ilike", new_stage]],
            fields=["id", "name"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not stages:
            return ToolResult(text=f'Stage "{new_stage}" not found.')

        ticket = tickets[0]
        stage = stages[0]

        await self.require_confirmation(
            question=f"Move ticket '{ticket['name']}' to stage '{stage['name']}'?",
            payload=f"update_ticket_status:{ticket['id']}:{stage['id']}",
        )
        await odoo.execute_kw(
            model="helpdesk.ticket",
            method="write",
            args=[[ticket["id"]], {"stage_id": stage["id"]}],
            uid=user_id,
            password=password,
        )
        if note:
            await odoo.execute_kw(
                model="helpdesk.ticket",
                method="message_post",
                args=[[ticket["id"]]],
                kwargs={"body": note, "message_type": "comment"},
                uid=user_id,
                password=password,
            )
        return ToolResult(text=f"Ticket '{ticket['name']}' moved to '{stage['name']}'.")

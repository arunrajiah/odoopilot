from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient

_LEAD_FIELDS = [
    "name",
    "partner_name",
    "stage_id",
    "user_id",
    "probability",
    "expected_revenue",
    "date_deadline",
]
_STAGE_ICONS = {"New": "🆕", "Qualified": "✅", "Proposition": "📋", "Won": "🏆", "Lost": "❌"}


class ListMyLeadsInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    stage: str | None = Field(
        default=None, description="Filter by stage name (e.g. 'New', 'Qualified')"
    )


class GetLeadInput(BaseModel):
    name: str = Field(description="Lead or opportunity name (partial match)")


class LogLeadActivityInput(BaseModel):
    lead_name: str = Field(description="Lead or opportunity name")
    note: str = Field(description="Activity note or summary to log")
    activity_type: str = Field(
        default="Note", description="Activity type: Note, Call, Email, Meeting"
    )


class ListMyLeads(BaseTool):
    """List leads and opportunities assigned to the current user."""

    name = "list_my_leads"
    description = "List CRM leads and opportunities assigned to you. Optionally filter by stage."
    parameters = ListMyLeadsInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        limit: int = 10,
        stage: str | None = None,
        **_: Any,
    ) -> ToolResult:
        domain: list[Any] = [["user_id", "=", user_id], ["type", "in", ["lead", "opportunity"]]]
        if stage:
            domain.append(["stage_id.name", "ilike", stage])

        records = await odoo.search_read(
            model="crm.lead",
            domain=domain,
            fields=_LEAD_FIELDS,
            limit=limit,
            order="date_deadline asc, probability desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No leads or opportunities found assigned to you.")

        lines = []
        for r in records:
            stage_name = r["stage_id"][1] if isinstance(r["stage_id"], list) else ""
            icon = _STAGE_ICONS.get(stage_name, "•")
            prob = f"{r.get('probability', 0):.0f}%"
            rev = f"{r.get('expected_revenue', 0):,.0f}"
            lines.append(
                f"{icon} {r['name']} | {r.get('partner_name') or '—'} | {stage_name} | {prob} | {rev}"
            )

        return ToolResult(text=f"{len(records)} lead(s):\n" + "\n".join(lines), data=records)


class GetLead(BaseTool):
    """Get details of a specific lead or opportunity."""

    name = "get_lead"
    description = "Get the details of a CRM lead or opportunity by name."
    parameters = GetLeadInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="crm.lead",
            domain=[["name", "ilike", name]],
            fields=_LEAD_FIELDS + ["description", "phone", "email_from"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Lead "{name}" not found.')

        r = records[0]
        stage_name = r["stage_id"][1] if isinstance(r["stage_id"], list) else ""
        assigned = r["user_id"][1] if isinstance(r["user_id"], list) else "Unassigned"
        return ToolResult(
            text=(
                f"*{r['name']}*\n"
                f"Customer: {r.get('partner_name') or '—'}\n"
                f"Stage: {stage_name}\n"
                f"Assigned to: {assigned}\n"
                f"Probability: {r.get('probability', 0):.0f}%\n"
                f"Expected revenue: {r.get('expected_revenue', 0):,.0f}\n"
                f"Deadline: {r.get('date_deadline') or 'None'}"
            ),
            data=records[0],
        )


class LogLeadActivity(BaseTool):
    """Log a note or activity on a lead (write — requires confirmation)."""

    name = "log_lead_activity"
    description = (
        "Log a note, call, or activity on a CRM lead or opportunity. "
        "Requires user confirmation before writing."
    )
    parameters = LogLeadActivityInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        lead_name: str,
        note: str,
        activity_type: str = "Note",
        **_: Any,
    ) -> ToolResult:
        records = await odoo.search_read(
            model="crm.lead",
            domain=[["name", "ilike", lead_name]],
            fields=["id", "name"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Lead "{lead_name}" not found.')

        lead = records[0]
        await self.require_confirmation(
            question=f'Log {activity_type} on "{lead["name"]}"?',
            payload=f"log_lead_activity:{lead['id']}",
        )
        await odoo.execute_kw(
            model="crm.lead",
            method="message_post",
            args=[[lead["id"]]],
            kwargs={"body": f"[{activity_type}] {note}", "message_type": "comment"},
            uid=user_id,
            password=password,
        )
        return ToolResult(text=f'{activity_type} logged on "{lead["name"]}".')

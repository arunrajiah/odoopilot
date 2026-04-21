from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient

_PO_FIELDS = ["name", "partner_id", "amount_total", "state", "date_order", "date_planned"]
_STATE_LABELS = {
    "draft": "RFQ",
    "sent": "RFQ Sent",
    "to approve": "To Approve",
    "purchase": "Purchase Order",
    "done": "Done",
    "cancel": "Cancelled",
}


class ListRFQsInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class GetPurchaseOrderInput(BaseModel):
    name: str = Field(description="Purchase order or RFQ number, e.g. P00042 or PO/2024/0001")


class ListRFQs(BaseTool):
    """List open Requests for Quotation."""

    name = "list_rfqs"
    description = "List open Requests for Quotation (RFQs) in Odoo."
    parameters = ListRFQsInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, limit: int = 10, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="purchase.order",
            domain=[["state", "in", ["draft", "sent", "to approve"]]],
            fields=_PO_FIELDS,
            limit=limit,
            order="date_order desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No open RFQs found.")

        lines = []
        for r in records:
            vendor = r["partner_id"][1] if isinstance(r["partner_id"], list) else "—"
            state = _STATE_LABELS.get(r.get("state", ""), r.get("state", ""))
            lines.append(f"• {r['name']} | {vendor} | {r.get('amount_total', 0):,.2f} | {state}")

        return ToolResult(text=f"{len(records)} RFQ(s):\n" + "\n".join(lines), data=records)


class GetPurchaseOrder(BaseTool):
    """Get details of a specific purchase order or RFQ."""

    name = "get_purchase_order"
    description = "Get the details of a purchase order or RFQ by its number."
    parameters = GetPurchaseOrderInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="purchase.order",
            domain=[["name", "ilike", name]],
            fields=_PO_FIELDS,
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Purchase order "{name}" not found.')

        r = records[0]
        vendor = r["partner_id"][1] if isinstance(r["partner_id"], list) else "—"
        state = _STATE_LABELS.get(r.get("state", ""), r.get("state", ""))
        return ToolResult(
            text=(
                f"*{r['name']}*\n"
                f"Vendor: {vendor}\n"
                f"Total: {r.get('amount_total', 0):,.2f}\n"
                f"Status: {state}\n"
                f"Order date: {r.get('date_order') or 'N/A'}\n"
                f"Planned date: {r.get('date_planned') or 'N/A'}"
            ),
            data=records[0],
        )

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient
from odoopilot.odoo.models import OdooSaleOrder

_SALE_ORDER_FIELDS = ["name", "partner_id", "amount_total", "state", "date_order"]
_STATE_LABELS = {
    "draft": "Quotation",
    "sent": "Sent",
    "sale": "Confirmed",
    "done": "Locked",
    "cancel": "Cancelled",
}


class ListSaleOrdersInput(BaseModel):
    state: str | None = Field(
        default=None,
        description="Filter by state: draft, sent, sale, done, cancel. Omit for all open orders.",
    )
    limit: int = Field(default=10, ge=1, le=50)


class GetSaleOrderInput(BaseModel):
    name: str = Field(description="Sale order number, e.g. S00042 or SO/2024/0001")


class ListQuotesInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class ConfirmSaleOrderInput(BaseModel):
    name: str = Field(description="Sale order number to confirm")


class ListSaleOrders(BaseTool):
    """List sale orders, optionally filtered by state."""

    name = "list_sale_orders"
    description = (
        "List sale orders from Odoo. Optionally filter by state (draft/sent/sale/done/cancel)."
    )
    parameters = ListSaleOrdersInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        state: str | None = None,
        limit: int = 10,
        **_: Any,
    ) -> ToolResult:
        domain: list[Any] = []
        if state:
            domain.append(["state", "=", state])
        else:
            domain.append(["state", "in", ["draft", "sent", "sale"]])

        records = await odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=_SALE_ORDER_FIELDS,
            limit=limit,
            order="date_order desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No sale orders found.")

        orders = [OdooSaleOrder.from_record(r) for r in records]
        lines = [
            f"• {o.name} | {o.partner_name} | {o.amount_total:,.2f} | {_STATE_LABELS.get(o.state, o.state)}"
            for o in orders
        ]
        return ToolResult(text=f"{len(orders)} order(s):\n" + "\n".join(lines), data=records)


class GetSaleOrder(BaseTool):
    """Get details of a specific sale order by its number."""

    name = "get_sale_order"
    description = "Get the full details of a sale order by its order number (e.g. SO/2024/0001)."
    parameters = GetSaleOrderInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="sale.order",
            domain=[["name", "ilike", name]],
            fields=_SALE_ORDER_FIELDS + ["order_line"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Sale order "{name}" not found.')

        o = OdooSaleOrder.from_record(records[0])
        return ToolResult(
            text=(
                f"*{o.name}*\n"
                f"Customer: {o.partner_name}\n"
                f"Total: {o.amount_total:,.2f}\n"
                f"Status: {_STATE_LABELS.get(o.state, o.state)}\n"
                f"Date: {o.date_order or 'N/A'}"
            ),
            data=records[0],
        )


class ListQuotes(BaseTool):
    """List quotations (draft/sent sale orders)."""

    name = "list_quotes"
    description = "List open quotations (draft and sent sale orders)."
    parameters = ListQuotesInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, limit: int = 10, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="sale.order",
            domain=[["state", "in", ["draft", "sent"]]],
            fields=_SALE_ORDER_FIELDS,
            limit=limit,
            order="date_order desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No open quotations found.")

        orders = [OdooSaleOrder.from_record(r) for r in records]
        lines = [
            f"• {o.name} | {o.partner_name} | {o.amount_total:,.2f} | {_STATE_LABELS.get(o.state, o.state)}"
            for o in orders
        ]
        return ToolResult(text=f"{len(orders)} quotation(s):\n" + "\n".join(lines), data=records)


class GetQuote(BaseTool):
    """Get details of a specific quotation."""

    name = "get_quote"
    description = "Get the details of a quotation by its name or number."
    parameters = GetSaleOrderInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="sale.order",
            domain=[["name", "ilike", name], ["state", "in", ["draft", "sent"]]],
            fields=_SALE_ORDER_FIELDS,
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Quotation "{name}" not found.')

        o = OdooSaleOrder.from_record(records[0])
        return ToolResult(
            text=(
                f"*{o.name}*\n"
                f"Customer: {o.partner_name}\n"
                f"Total: {o.amount_total:,.2f}\n"
                f"Status: {_STATE_LABELS.get(o.state, o.state)}"
            ),
            data=records[0],
        )


class ConfirmSaleOrder(BaseTool):
    """Confirm a quotation or sale order (write — requires user confirmation)."""

    name = "confirm_sale_order"
    description = (
        "Confirm a quotation or sale order. "
        "This is a write operation — the user must tap a confirmation button before it executes."
    )
    parameters = ConfirmSaleOrderInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="sale.order",
            domain=[["name", "ilike", name], ["state", "in", ["draft", "sent"]]],
            fields=["id", "name", "partner_id", "amount_total"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Quotation "{name}" not found or already confirmed.')

        rec = records[0]
        partner = rec["partner_id"][1] if isinstance(rec["partner_id"], list) else ""
        await self.require_confirmation(
            question=f"Confirm {rec['name']} for {partner} — {rec['amount_total']:,.2f}?",
            payload=f"confirm_sale_order:{rec['id']}",
        )
        # Execution resumes here after user taps Yes
        await odoo.execute_kw(
            model="sale.order",
            method="action_confirm",
            args=[[rec["id"]]],
            uid=user_id,
            password=password,
        )
        return ToolResult(text=f"{rec['name']} confirmed successfully.")

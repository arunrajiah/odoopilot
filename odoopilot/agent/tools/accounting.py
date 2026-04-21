from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient

_INVOICE_FIELDS = [
    "name",
    "partner_id",
    "amount_total",
    "amount_residual",
    "state",
    "invoice_date",
    "invoice_date_due",
]
_INVOICE_STATE_LABELS = {"draft": "Draft", "posted": "Posted", "cancel": "Cancelled"}


class ListOverdueInvoicesInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class GetInvoiceInput(BaseModel):
    name: str = Field(description="Invoice number, e.g. INV/2024/0001")


class ListMyExpensesInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class SubmitExpenseInput(BaseModel):
    expense_ids: list[int] | None = Field(
        default=None,
        description="Specific expense IDs to submit (optional — submits all draft expenses if omitted)",
    )


class ListOverdueInvoices(BaseTool):
    """List overdue customer invoices."""

    name = "list_overdue_invoices"
    description = "List customer invoices that are past their due date and still unpaid."
    parameters = ListOverdueInvoicesInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, limit: int = 10, **_: Any
    ) -> ToolResult:
        from datetime import date

        today = date.today().isoformat()
        records = await odoo.search_read(
            model="account.move",
            domain=[
                ["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
                ["payment_state", "in", ["not_paid", "partial"]],
                ["invoice_date_due", "<", today],
            ],
            fields=_INVOICE_FIELDS,
            limit=limit,
            order="invoice_date_due asc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No overdue invoices found.")

        lines = []
        for r in records:
            partner = r["partner_id"][1] if isinstance(r["partner_id"], list) else "—"
            due = str(r.get("invoice_date_due", ""))[:10]
            residual = r.get("amount_residual", 0)
            lines.append(f"• {r['name']} | {partner} | {residual:,.2f} due | overdue since {due}")

        return ToolResult(
            text=f"{len(records)} overdue invoice(s):\n" + "\n".join(lines), data=records
        )


class GetInvoice(BaseTool):
    """Get details of a specific invoice."""

    name = "get_invoice"
    description = "Get the details of an invoice by its number."
    parameters = GetInvoiceInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="account.move",
            domain=[
                ["name", "ilike", name],
                ["move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"]],
            ],
            fields=_INVOICE_FIELDS,
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Invoice "{name}" not found.')

        r = records[0]
        partner = r["partner_id"][1] if isinstance(r["partner_id"], list) else "—"
        state = _INVOICE_STATE_LABELS.get(r.get("state", ""), r.get("state", ""))
        return ToolResult(
            text=(
                f"*{r['name']}*\n"
                f"Partner: {partner}\n"
                f"Total: {r.get('amount_total', 0):,.2f}\n"
                f"Outstanding: {r.get('amount_residual', 0):,.2f}\n"
                f"Status: {state}\n"
                f"Invoice date: {r.get('invoice_date') or 'N/A'}\n"
                f"Due date: {r.get('invoice_date_due') or 'N/A'}"
            ),
            data=records[0],
        )


class ListMyExpenses(BaseTool):
    """List expense reports submitted by the current user."""

    name = "list_my_expenses"
    description = "List your expense reports and their approval status."
    parameters = ListMyExpensesInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, limit: int = 10, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="hr.expense",
            domain=[["employee_id.user_id", "=", user_id]],
            fields=["name", "product_id", "total_amount", "currency_id", "date", "sheet_id"],
            limit=limit,
            order="date desc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No expense records found.")

        lines = []
        for r in records:
            product = r["product_id"][1] if isinstance(r["product_id"], list) else "—"
            sheet = r["sheet_id"][1] if isinstance(r["sheet_id"], list) else "Not submitted"
            currency = r["currency_id"][1] if isinstance(r["currency_id"], list) else ""
            date = str(r.get("date", ""))[:10]
            lines.append(
                f"• {r['name']} | {product} | {r.get('total_amount', 0):,.2f} {currency} | {date} | {sheet}"
            )

        return ToolResult(text=f"{len(records)} expense(s):\n" + "\n".join(lines), data=records)


class SubmitExpense(BaseTool):
    """Submit draft expenses as an expense report (write — requires confirmation)."""

    name = "submit_expense"
    description = (
        "Submit your draft expenses as an expense report for manager approval. "
        "Requires user confirmation before creating the report."
    )
    parameters = SubmitExpenseInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        expense_ids: list[int] | None = None,
        **_: Any,
    ) -> ToolResult:
        if not expense_ids:
            # Find all unsubmitted expenses for this user
            records = await odoo.search_read(
                model="hr.expense",
                domain=[["employee_id.user_id", "=", user_id], ["sheet_id", "=", False]],
                fields=["id", "name", "total_amount"],
                uid=user_id,
                password=password,
            )
            if not records:
                return ToolResult(text="No unsubmitted expenses found.")
            expense_ids = [r["id"] for r in records]
            total = sum(r.get("total_amount", 0) for r in records)
        else:
            records = await odoo.read(
                model="hr.expense",
                ids=expense_ids,
                fields=["id", "name", "total_amount"],
                uid=user_id,
                password=password,
            )
            total = sum(r.get("total_amount", 0) for r in records)

        await self.require_confirmation(
            question=f"Submit {len(expense_ids)} expense(s) totalling {total:,.2f} for approval?",
            payload=f"submit_expense:{','.join(str(i) for i in expense_ids)}",
        )
        await odoo.execute_kw(
            model="hr.expense",
            method="action_submit_expenses",
            args=[expense_ids],
            uid=user_id,
            password=password,
        )
        return ToolResult(text=f"{len(expense_ids)} expense(s) submitted for approval.")

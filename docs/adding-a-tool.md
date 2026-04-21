# Adding a tool

Tools are the heart of OdooPilot — each one wraps a single Odoo intent. This guide walks through adding a new read or write tool from scratch.

## Checklist

- [ ] Implement the tool class in the right domain file
- [ ] Register it in `odoopilot/agent/tools/__init__.py`
- [ ] Write a test in `tests/test_tools/`
- [ ] Add one line to the table at the bottom of this doc

---

## 1. Create the tool class

Add your tool to the appropriate domain file under `odoopilot/agent/tools/`. If the domain file doesn't exist yet, create it.

```python
# odoopilot/agent/tools/inventory.py
from pydantic import BaseModel, Field
from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient


class FindProductInput(BaseModel):
    query: str = Field(description="Product name, reference, or barcode to search for")


class FindProduct(BaseTool):
    """Search for a product by name, internal reference, or barcode."""

    name = "find_product"
    description = (
        "Search for a product in Odoo by name, internal reference, or barcode. "
        "Returns matching products with stock information."
    )
    parameters = FindProductInput

    async def execute(
        self, odoo: OdooClient, user_id: int, query: str
    ) -> ToolResult:
        products = await odoo.search_read(
            model="product.product",
            domain=[
                "|", "|",
                ["name", "ilike", query],
                ["default_code", "ilike", query],
                ["barcode", "=", query],
            ],
            fields=["name", "default_code", "qty_available", "uom_id"],
            limit=10,
            uid=user_id,
        )
        if not products:
            return ToolResult(text=f'No products found matching "{query}".')
        lines = [
            f"• {p['name']} ({p.get('default_code') or 'no ref'}) — "
            f"{p['qty_available']} {p['uom_id'][1]} on hand"
            for p in products
        ]
        return ToolResult(text="\n".join(lines))
```

### Read vs write tools

**Read tools** return a `ToolResult` directly.

**Write tools** must call `await self.require_confirmation(description)` before mutating Odoo. The agent loop catches `ConfirmationRequired` and sends an inline button prompt. The user's confirmation resumes the tool.

```python
async def execute(self, odoo, user_id, order_id: int) -> ToolResult:
    order = await odoo.read("sale.order", order_id, ["name", "amount_total"], uid=user_id)
    await self.require_confirmation(
        f"Confirm {order['name']} for {order['amount_total']:.2f}?"
    )
    await odoo.execute_kw("sale.order", "action_confirm", [[order_id]], uid=user_id)
    return ToolResult(text=f"{order['name']} confirmed.")
```

---

## 2. Register the tool

In `odoopilot/agent/tools/__init__.py`, add your tool to `ALL_TOOLS`:

```python
from odoopilot.agent.tools.inventory import FindProduct

ALL_TOOLS: list[type[BaseTool]] = [
    FindProduct,
    # ... other tools
]
```

---

## 3. Write a test

```python
# tests/test_tools/test_inventory.py
import pytest
from unittest.mock import AsyncMock
from odoopilot.agent.tools.inventory import FindProduct


@pytest.mark.asyncio
async def test_find_product_returns_results():
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {"name": "Widget Pro", "default_code": "WP-001",
         "qty_available": 42.0, "uom_id": [1, "Units"]}
    ]
    tool = FindProduct()
    result = await tool.execute(odoo, user_id=2, query="Widget")
    assert "Widget Pro" in result.text
    assert "42" in result.text


@pytest.mark.asyncio
async def test_find_product_no_results():
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = FindProduct()
    result = await tool.execute(odoo, user_id=2, query="xyz-nonexistent")
    assert "No products found" in result.text
```

---

## Implemented tools

| Tool | Domain | Type | Odoo model |
|------|--------|------|-----------|
| `find_product` | Inventory | read | `product.product` |
| `check_stock` | Inventory | read | `stock.quant` |
| `list_warehouses` | Inventory | read | `stock.warehouse` |
| `list_sale_orders` | Sales | read | `sale.order` |
| `get_sale_order` | Sales | read | `sale.order` |
| `list_quotes` | Sales | read | `sale.order` |
| `get_quote` | Sales | read | `sale.order` |
| `confirm_sale_order` | Sales | write | `sale.order` |
| `list_my_leads` | CRM | read | `crm.lead` |
| `get_lead` | CRM | read | `crm.lead` |
| `log_lead_activity` | CRM | write | `mail.activity` |
| `list_rfqs` | Purchase | read | `purchase.order` |
| `get_purchase_order` | Purchase | read | `purchase.order` |
| `my_leave_balance` | HR | read | `hr.leave.allocation` |
| `list_team_leaves` | HR | read | `hr.leave` |
| `request_leave` | HR | write | `hr.leave` |
| `approve_leave` | HR | write | `hr.leave` |
| `list_overdue_invoices` | Accounting | read | `account.move` |
| `get_invoice` | Accounting | read | `account.move` |
| `list_my_expenses` | Accounting | read | `hr.expense` |
| `submit_expense` | Accounting | write | `hr.expense` |
| `list_my_tasks` | Project | read | `project.task` |
| `get_task` | Project | read | `project.task` |
| `log_timesheet_entry` | Project | write | `account.analytic.line` |
| `list_my_tickets` | Helpdesk | read | `helpdesk.ticket` |
| `get_ticket` | Helpdesk | read | `helpdesk.ticket` |
| `update_ticket_status` | Helpdesk | write | `helpdesk.ticket` |

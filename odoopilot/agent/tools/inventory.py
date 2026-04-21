from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient
from odoopilot.odoo.models import OdooProduct


class FindProductInput(BaseModel):
    query: str = Field(description="Product name, internal reference, or barcode to search for")


class CheckStockInput(BaseModel):
    product_ref: str = Field(description="Product internal reference or name")
    warehouse: str | None = Field(default=None, description="Warehouse name filter (optional)")


class ListWarehousesInput(BaseModel):
    pass


class FindProduct(BaseTool):
    """Search for a product by name, internal reference, or barcode."""

    name = "find_product"
    description = (
        "Search for a product in Odoo by name, internal reference, or barcode. "
        "Returns matching products with on-hand stock quantity."
    )
    parameters = FindProductInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, query: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="product.product",
            domain=[
                "|",
                "|",
                ["name", "ilike", query],
                ["default_code", "ilike", query],
                ["barcode", "=", query],
            ],
            fields=["name", "default_code", "qty_available", "uom_id"],
            limit=10,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'No products found matching "{query}".')

        products = [OdooProduct.from_record(r) for r in records]
        lines = [
            f"• {p.name}"
            + (f" [{p.default_code}]" if p.default_code else "")
            + f" — {p.qty_available:.0f} {p.uom_name} on hand"
            for p in products
        ]
        header = f"Found {len(products)} product(s):"
        return ToolResult(text=header + "\n" + "\n".join(lines), data=records)


class CheckStock(BaseTool):
    """Check stock levels for a specific product across warehouses."""

    name = "check_stock"
    description = (
        "Check the on-hand stock quantity for a product across warehouses. "
        "Optionally filter by warehouse name."
    )
    parameters = CheckStockInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        product_ref: str,
        warehouse: str | None = None,
        **_: Any,
    ) -> ToolResult:
        product_records = await odoo.search_read(
            model="product.product",
            domain=["|", ["name", "ilike", product_ref], ["default_code", "ilike", product_ref]],
            fields=["id", "name", "default_code"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not product_records:
            return ToolResult(text=f'Product "{product_ref}" not found.')

        product = product_records[0]
        quant_domain: list[Any] = [["product_id", "=", product["id"]]]
        if warehouse:
            quant_domain.append(["location_id.warehouse_id.name", "ilike", warehouse])

        quants = await odoo.search_read(
            model="stock.quant",
            domain=quant_domain,
            fields=["location_id", "quantity", "reserved_quantity"],
            uid=user_id,
            password=password,
        )

        if not quants:
            return ToolResult(
                text=f"{product['name']} — no stock records found"
                + (f" in warehouse '{warehouse}'" if warehouse else "")
                + "."
            )

        total = sum(q["quantity"] for q in quants)
        reserved = sum(q["reserved_quantity"] for q in quants)
        lines = [
            f"*{product['name']}* ({product.get('default_code') or 'no ref'})\n"
            f"Total on hand: {total:.0f} | Reserved: {reserved:.0f} | Available: {total - reserved:.0f}"
        ]
        for q in quants:
            loc = (
                q["location_id"][1] if isinstance(q["location_id"], list) else str(q["location_id"])
            )
            lines.append(f"  {loc}: {q['quantity']:.0f}")

        return ToolResult(text="\n".join(lines), data=quants)


class ListWarehouses(BaseTool):
    """List all warehouses configured in Odoo."""

    name = "list_warehouses"
    description = "List all warehouses in Odoo with their codes and locations."
    parameters = ListWarehousesInput

    async def execute(self, odoo: OdooClient, user_id: int, password: str, **_: Any) -> ToolResult:
        warehouses = await odoo.search_read(
            model="stock.warehouse",
            domain=[],
            fields=["name", "code", "lot_stock_id"],
            uid=user_id,
            password=password,
        )
        if not warehouses:
            return ToolResult(text="No warehouses found.")

        lines = [f"• {w['name']} ({w['code']})" for w in warehouses]
        return ToolResult(
            text=f"{len(warehouses)} warehouse(s):\n" + "\n".join(lines), data=warehouses
        )

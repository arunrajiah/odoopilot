from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from odoopilot.agent.tools.inventory import CheckStock, FindProduct, ListWarehouses


@pytest.mark.asyncio
async def test_find_product_returns_results() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {
            "id": 1,
            "name": "Widget Pro",
            "default_code": "WP-001",
            "qty_available": 42.0,
            "uom_id": [1, "Units"],
        },
        {
            "id": 2,
            "name": "Widget Lite",
            "default_code": "WL-001",
            "qty_available": 0.0,
            "uom_id": [1, "Units"],
        },
    ]
    tool = FindProduct()
    result = await tool.execute(odoo, user_id=2, password="pass", query="Widget")

    assert "Widget Pro" in result.text
    assert "WP-001" in result.text
    assert "42" in result.text
    assert "Widget Lite" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_find_product_no_results() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = FindProduct()
    result = await tool.execute(odoo, user_id=2, password="pass", query="xyz-nonexistent")

    assert "No products found" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_find_product_passes_correct_domain() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = FindProduct()
    await tool.execute(odoo, user_id=2, password="pass", query="REF-001")

    call_kwargs = odoo.search_read.call_args
    domain = call_kwargs.kwargs["domain"]
    # Domain must use ilike on name and default_code, and = on barcode
    assert any("ilike" in str(item) for item in domain)


@pytest.mark.asyncio
async def test_check_stock_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.side_effect = [
        # product lookup
        [{"id": 5, "name": "Widget Pro", "default_code": "WP-001"}],
        # quant lookup
        [
            {"location_id": [10, "WH/Stock"], "quantity": 100.0, "reserved_quantity": 10.0},
            {"location_id": [11, "WH2/Stock"], "quantity": 50.0, "reserved_quantity": 5.0},
        ],
    ]
    tool = CheckStock()
    result = await tool.execute(odoo, user_id=2, password="pass", product_ref="Widget Pro")

    assert "Widget Pro" in result.text
    assert "150" in result.text  # total
    assert "135" in result.text  # available
    assert not result.error


@pytest.mark.asyncio
async def test_check_stock_product_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = CheckStock()
    result = await tool.execute(odoo, user_id=2, password="pass", product_ref="BOGUS")

    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_list_warehouses() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {"id": 1, "name": "Main Warehouse", "code": "WH", "lot_stock_id": [5, "WH/Stock"]},
        {"id": 2, "name": "Secondary", "code": "WH2", "lot_stock_id": [8, "WH2/Stock"]},
    ]
    tool = ListWarehouses()
    result = await tool.execute(odoo, user_id=2, password="pass")

    assert "Main Warehouse" in result.text
    assert "WH" in result.text
    assert "Secondary" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_list_warehouses_empty() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = ListWarehouses()
    result = await tool.execute(odoo, user_id=2, password="pass")

    assert "No warehouses" in result.text

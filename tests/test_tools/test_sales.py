from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from odoopilot.agent.tools.base import ConfirmationRequired
from odoopilot.agent.tools.sales import (
    ConfirmSaleOrder,
    GetSaleOrder,
    ListQuotes,
    ListSaleOrders,
)

_SAMPLE_ORDER = {
    "id": 1,
    "name": "SO/2024/0001",
    "partner_id": [10, "Acme Corp"],
    "amount_total": 4320.0,
    "state": "sale",
    "date_order": "2024-01-15 09:00:00",
}

_SAMPLE_QUOTE = {
    "id": 2,
    "name": "SO/2024/0002",
    "partner_id": [11, "Beta Ltd"],
    "amount_total": 1200.0,
    "state": "draft",
    "date_order": "2024-01-16 10:00:00",
}


@pytest.mark.asyncio
async def test_list_sale_orders_returns_results() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_ORDER]
    tool = ListSaleOrders()
    result = await tool.execute(odoo, user_id=1, password="pass")

    assert "SO/2024/0001" in result.text
    assert "Acme Corp" in result.text
    assert "4,320.00" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_list_sale_orders_empty() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = ListSaleOrders()
    result = await tool.execute(odoo, user_id=1, password="pass")

    assert "No sale orders" in result.text


@pytest.mark.asyncio
async def test_get_sale_order_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_ORDER]
    tool = GetSaleOrder()
    result = await tool.execute(odoo, user_id=1, password="pass", name="SO/2024/0001")

    assert "SO/2024/0001" in result.text
    assert "Acme Corp" in result.text
    assert "Confirmed" in result.text


@pytest.mark.asyncio
async def test_get_sale_order_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = GetSaleOrder()
    result = await tool.execute(odoo, user_id=1, password="pass", name="BOGUS")

    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_list_quotes() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_QUOTE]
    tool = ListQuotes()
    result = await tool.execute(odoo, user_id=1, password="pass")

    assert "SO/2024/0002" in result.text
    assert "Beta Ltd" in result.text


@pytest.mark.asyncio
async def test_confirm_sale_order_raises_confirmation_required() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {"id": 1, "name": "SO/2024/0001", "partner_id": [10, "Acme Corp"], "amount_total": 4320.0}
    ]
    tool = ConfirmSaleOrder()

    with pytest.raises(ConfirmationRequired) as exc_info:
        await tool.execute(odoo, user_id=1, password="pass", name="SO/2024/0001")

    assert "SO/2024/0001" in exc_info.value.question
    assert "Acme Corp" in exc_info.value.question
    # execute_kw must NOT have been called — no mutation before confirmation
    odoo.execute_kw.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_sale_order_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    tool = ConfirmSaleOrder()
    result = await tool.execute(odoo, user_id=1, password="pass", name="BOGUS")

    assert "not found" in result.text.lower()
    odoo.execute_kw.assert_not_called()

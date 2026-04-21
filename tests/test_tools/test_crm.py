from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from odoopilot.agent.tools.base import ConfirmationRequired
from odoopilot.agent.tools.crm import GetLead, ListMyLeads, LogLeadActivity

_SAMPLE_LEAD = {
    "id": 1,
    "name": "New office chairs deal",
    "partner_name": "Acme Corp",
    "stage_id": [2, "Qualified"],
    "user_id": [5, "Alice"],
    "probability": 60.0,
    "expected_revenue": 5000.0,
    "date_deadline": "2024-06-30",
}


@pytest.mark.asyncio
async def test_list_my_leads_returns_results() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_LEAD]
    result = await ListMyLeads().execute(odoo, user_id=5, password="pass")
    assert "New office chairs deal" in result.text
    assert "Acme Corp" in result.text
    assert "Qualified" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_list_my_leads_empty() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await ListMyLeads().execute(odoo, user_id=5, password="pass")
    assert "No leads" in result.text


@pytest.mark.asyncio
async def test_get_lead_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {
            **_SAMPLE_LEAD,
            "description": "Big opportunity",
            "phone": "+1555",
            "email_from": "a@b.com",
        }
    ]
    result = await GetLead().execute(odoo, user_id=5, password="pass", name="office")
    assert "New office chairs deal" in result.text
    assert "Qualified" in result.text


@pytest.mark.asyncio
async def test_get_lead_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await GetLead().execute(odoo, user_id=5, password="pass", name="BOGUS")
    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_log_lead_activity_requires_confirmation() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [{"id": 1, "name": "New office chairs deal"}]
    with pytest.raises(ConfirmationRequired) as exc:
        await LogLeadActivity().execute(
            odoo,
            user_id=5,
            password="pass",
            lead_name="office chairs",
            note="Called customer",
            activity_type="Call",
        )
    assert "New office chairs deal" in exc.value.question
    odoo.execute_kw.assert_not_called()

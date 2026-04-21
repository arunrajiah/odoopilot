from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from odoopilot.agent.tools.base import ConfirmationRequired
from odoopilot.agent.tools.hr import ApproveLeave, ListTeamLeaves, MyLeaveBalance, RequestLeave


@pytest.mark.asyncio
async def test_my_leave_balance_no_employee() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await MyLeaveBalance().execute(odoo, user_id=2, password="pass")
    assert "No employee record" in result.text


@pytest.mark.asyncio
async def test_my_leave_balance_with_allocations() -> None:
    odoo = AsyncMock()
    odoo.search_read.side_effect = [
        [{"id": 10, "name": "Alice"}],  # employee lookup
        [
            {
                "holiday_status_id": [1, "Annual Leave"],
                "number_of_days": 20.0,
                "number_of_days_display": "20",
            },
            {
                "holiday_status_id": [2, "Sick Leave"],
                "number_of_days": 5.0,
                "number_of_days_display": "5",
            },
        ],
    ]
    result = await MyLeaveBalance().execute(odoo, user_id=2, password="pass")
    assert "Annual Leave" in result.text
    assert "20" in result.text
    assert "Sick Leave" in result.text


@pytest.mark.asyncio
async def test_list_team_leaves() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {
            "id": 1,
            "employee_id": [10, "Alice"],
            "holiday_status_id": [1, "Annual Leave"],
            "date_from": "2024-07-01 08:00:00",
            "date_to": "2024-07-05 17:00:00",
            "state": "validate",
            "number_of_days": 5.0,
        }
    ]
    result = await ListTeamLeaves().execute(odoo, user_id=2, password="pass")
    assert "Alice" in result.text
    assert "Annual Leave" in result.text
    assert "Approved" in result.text


@pytest.mark.asyncio
async def test_request_leave_type_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await RequestLeave().execute(
        odoo,
        user_id=2,
        password="pass",
        leave_type="Nonexistent Leave",
        date_from="2024-08-01",
        date_to="2024-08-05",
    )
    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_request_leave_requires_confirmation() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [{"id": 1, "name": "Annual Leave"}]
    with pytest.raises(ConfirmationRequired) as exc:
        await RequestLeave().execute(
            odoo,
            user_id=2,
            password="pass",
            leave_type="Annual Leave",
            date_from="2024-08-01",
            date_to="2024-08-05",
        )
    assert "Annual Leave" in exc.value.question
    odoo.execute_kw.assert_not_called()


@pytest.mark.asyncio
async def test_approve_leave_no_pending() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await ApproveLeave().execute(odoo, user_id=1, password="pass", employee_name="Bob")
    assert "No pending leave" in result.text


@pytest.mark.asyncio
async def test_approve_leave_requires_confirmation() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {
            "id": 5,
            "employee_id": [10, "Bob"],
            "holiday_status_id": [1, "Annual Leave"],
            "date_from": "2024-08-01",
            "date_to": "2024-08-03",
        }
    ]
    with pytest.raises(ConfirmationRequired) as exc:
        await ApproveLeave().execute(odoo, user_id=1, password="pass", employee_name="Bob")
    assert "Bob" in exc.value.question
    odoo.execute_kw.assert_not_called()

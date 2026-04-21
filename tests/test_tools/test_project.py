from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from odoopilot.agent.tools.base import ConfirmationRequired
from odoopilot.agent.tools.project import GetTask, ListMyTasks, LogTimesheetEntry

_SAMPLE_TASK = {
    "id": 1,
    "name": "Build login page",
    "project_id": [3, "Website Redesign"],
    "stage_id": [2, "In Progress"],
    "date_deadline": "2024-07-15",
    "description": False,
    "user_ids": [5],
}


@pytest.mark.asyncio
async def test_list_my_tasks_returns_results() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_TASK]
    result = await ListMyTasks().execute(odoo, user_id=5, password="pass")
    assert "Build login page" in result.text
    assert "Website Redesign" in result.text
    assert "In Progress" in result.text
    assert not result.error


@pytest.mark.asyncio
async def test_list_my_tasks_empty() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await ListMyTasks().execute(odoo, user_id=5, password="pass")
    assert "No open tasks" in result.text


@pytest.mark.asyncio
async def test_get_task_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [_SAMPLE_TASK]
    result = await GetTask().execute(odoo, user_id=5, password="pass", name="login")
    assert "Build login page" in result.text
    assert "Website Redesign" in result.text


@pytest.mark.asyncio
async def test_get_task_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await GetTask().execute(odoo, user_id=5, password="pass", name="BOGUS")
    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_log_timesheet_task_not_found() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = []
    result = await LogTimesheetEntry().execute(
        odoo, user_id=5, password="pass", task_name="BOGUS", hours=2.0, description="Did stuff"
    )
    assert "not found" in result.text.lower()


@pytest.mark.asyncio
async def test_log_timesheet_requires_confirmation() -> None:
    odoo = AsyncMock()
    odoo.search_read.return_value = [
        {"id": 1, "name": "Build login page", "project_id": [3, "Website Redesign"]}
    ]
    with pytest.raises(ConfirmationRequired) as exc:
        await LogTimesheetEntry().execute(
            odoo,
            user_id=5,
            password="pass",
            task_name="login page",
            hours=2.5,
            description="Implemented auth",
        )
    assert "2.5" in exc.value.question
    assert "Build login page" in exc.value.question
    odoo.execute_kw.assert_not_called()

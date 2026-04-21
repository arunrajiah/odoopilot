from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from odoopilot.agent.tools.base import BaseTool, ToolResult
from odoopilot.odoo.client import OdooClient
from odoopilot.odoo.models import OdooTask

_TASK_FIELDS = ["name", "project_id", "stage_id", "date_deadline", "description", "user_ids"]


class ListMyTasksInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    project: str | None = Field(default=None, description="Filter by project name (optional)")


class GetTaskInput(BaseModel):
    name: str = Field(description="Task name (partial match)")


class LogTimesheetInput(BaseModel):
    task_name: str = Field(description="Task name to log time against")
    hours: float = Field(description="Number of hours to log", gt=0, le=24)
    description: str = Field(description="Description of work done")
    date: str | None = Field(
        default=None, description="Date in YYYY-MM-DD format. Defaults to today."
    )


class ListMyTasks(BaseTool):
    """List tasks assigned to the current user."""

    name = "list_my_tasks"
    description = "List open tasks assigned to you. Optionally filter by project name."
    parameters = ListMyTasksInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        limit: int = 10,
        project: str | None = None,
        **_: Any,
    ) -> ToolResult:
        domain: list[Any] = [
            ["user_ids", "in", [user_id]],
            ["stage_id.fold", "=", False],  # exclude done/cancelled stages
        ]
        if project:
            domain.append(["project_id.name", "ilike", project])

        records = await odoo.search_read(
            model="project.task",
            domain=domain,
            fields=_TASK_FIELDS,
            limit=limit,
            order="date_deadline asc",
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text="No open tasks found assigned to you.")

        lines = []
        for r in records:
            task = OdooTask.from_record(r)
            deadline = f" | due {task.date_deadline[:10]}" if task.date_deadline else ""
            lines.append(f"• [{task.project_name}] {task.name} — {task.stage_name}{deadline}")

        return ToolResult(text=f"{len(records)} task(s):\n" + "\n".join(lines), data=records)


class GetTask(BaseTool):
    """Get details of a specific task."""

    name = "get_task"
    description = "Get the details of a project task by name."
    parameters = GetTaskInput

    async def execute(
        self, odoo: OdooClient, user_id: int, password: str, name: str, **_: Any
    ) -> ToolResult:
        records = await odoo.search_read(
            model="project.task",
            domain=[["name", "ilike", name]],
            fields=_TASK_FIELDS,
            limit=1,
            uid=user_id,
            password=password,
        )
        if not records:
            return ToolResult(text=f'Task "{name}" not found.')

        task = OdooTask.from_record(records[0])
        return ToolResult(
            text=(
                f"*{task.name}*\n"
                f"Project: {task.project_name}\n"
                f"Stage: {task.stage_name}\n"
                f"Deadline: {task.date_deadline[:10] if task.date_deadline else 'None'}"
            ),
            data=records[0],
        )


class LogTimesheetEntry(BaseTool):
    """Log a timesheet entry on a task (write — requires confirmation)."""

    name = "log_timesheet_entry"
    description = (
        "Log time worked on a project task. "
        "Requires confirmation before creating the timesheet entry."
    )
    parameters = LogTimesheetInput

    async def execute(
        self,
        odoo: OdooClient,
        user_id: int,
        password: str,
        task_name: str,
        hours: float,
        description: str,
        date: str | None = None,
        **_: Any,
    ) -> ToolResult:
        from datetime import date as date_cls

        log_date = date or date_cls.today().isoformat()

        tasks = await odoo.search_read(
            model="project.task",
            domain=[["name", "ilike", task_name]],
            fields=["id", "name", "project_id"],
            limit=1,
            uid=user_id,
            password=password,
        )
        if not tasks:
            return ToolResult(text=f'Task "{task_name}" not found.')

        task = tasks[0]
        project_id = task["project_id"][0] if isinstance(task["project_id"], list) else None
        project_name = task["project_id"][1] if isinstance(task["project_id"], list) else ""

        await self.require_confirmation(
            question=f"Log {hours:.1f}h on '{task['name']}' ({project_name}) for {log_date}?",
            payload=f"log_timesheet_entry:{task['id']}:{hours}:{log_date}",
        )

        employees = await odoo.search_read(
            model="hr.employee",
            domain=[["user_id", "=", user_id]],
            fields=["id"],
            limit=1,
            uid=user_id,
            password=password,
        )
        employee_id = employees[0]["id"] if employees else None

        values: dict[str, Any] = {
            "task_id": task["id"],
            "project_id": project_id,
            "name": description,
            "unit_amount": hours,
            "date": log_date,
        }
        if employee_id:
            values["employee_id"] = employee_id

        await odoo.execute_kw(
            model="account.analytic.line",
            method="create",
            args=[values],
            uid=user_id,
            password=password,
        )
        return ToolResult(text=f"Logged {hours:.1f}h on '{task['name']}' for {log_date}.")

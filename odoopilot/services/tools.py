"""ORM-based tools for OdooPilot. Each function receives `env` (scoped to the linked user)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from odoo import fields

_logger = logging.getLogger(__name__)


# ── Tool registry ──────────────────────────────────────────────────────────────

WRITE_TOOLS = {
    "mark_task_done",
    "confirm_sale_order",
    "approve_leave",
    "update_crm_stage",
    "create_crm_lead",
    # 17.0.14.0.0 — employee-self-service write tools
    "clock_in",
    "clock_out",
    "submit_expense",
    "submit_timesheet",
    "create_calendar_event",
}

TOOL_DEFINITIONS = [
    {
        "name": "get_my_tasks",
        "description": "Get open tasks assigned to the current user.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project name (optional)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_sale_orders",
        "description": "List sale orders. Filter by state.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["draft", "sent", "sale", "done", "cancel"],
                    "description": "Order state filter (optional)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_crm_leads",
        "description": "List CRM leads/opportunities for the current user.",
        "parameters": {
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "description": "Filter by stage name (optional)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_stock_products",
        "description": "Check product stock levels.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Product name search (optional)",
                },
                "low_stock_only": {
                    "type": "boolean",
                    "description": "Only show products with qty <= 0",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_invoices",
        "description": "List customer invoices.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["draft", "posted", "cancel"],
                    "description": "Invoice state (optional)",
                },
                "overdue_only": {
                    "type": "boolean",
                    "description": "Only show overdue invoices",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_purchase_orders",
        "description": "List purchase orders.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["draft", "sent", "purchase", "done", "cancel"],
                    "description": "Order state filter (optional)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_employees",
        "description": "List employees.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {
                    "type": "string",
                    "description": "Department name filter (optional)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_my_leaves",
        "description": "List leave requests — own leaves or pending approvals if the user is a manager.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["confirm", "validate1", "validate", "refuse"],
                    "description": "Filter by leave state (optional). 'confirm' = waiting approval.",
                },
                "team_leaves": {
                    "type": "boolean",
                    "description": "If true, show leaves from the user's team (for managers)",
                },
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "mark_task_done",
        "description": "Mark a task as done. REQUIRES user confirmation before executing.",
        "parameters": {
            "type": "object",
            "required": ["task_name"],
            "properties": {
                "task_name": {
                    "type": "string",
                    "description": "Name or partial name of the task",
                },
            },
        },
    },
    {
        "name": "confirm_sale_order",
        "description": "Confirm a draft/sent sale order. REQUIRES user confirmation.",
        "parameters": {
            "type": "object",
            "required": ["order_name"],
            "properties": {
                "order_name": {
                    "type": "string",
                    "description": "Sale order name e.g. S00042",
                },
            },
        },
    },
    {
        "name": "approve_leave",
        "description": "Approve a pending leave request. REQUIRES user confirmation.",
        "parameters": {
            "type": "object",
            "required": ["employee_name"],
            "properties": {
                "employee_name": {
                    "type": "string",
                    "description": "Employee whose leave to approve (partial name match)",
                },
                "leave_type": {
                    "type": "string",
                    "description": "Holiday type/name to narrow down if employee has multiple pending leaves (optional)",
                },
            },
        },
    },
    {
        "name": "update_crm_stage",
        "description": "Move a CRM lead/opportunity to a different pipeline stage. REQUIRES user confirmation.",
        "parameters": {
            "type": "object",
            "required": ["lead_name", "stage_name"],
            "properties": {
                "lead_name": {
                    "type": "string",
                    "description": "Name or partial name of the lead/opportunity",
                },
                "stage_name": {
                    "type": "string",
                    "description": "Target stage name (e.g. 'Qualified', 'Won', 'Proposition')",
                },
            },
        },
    },
    {
        "name": "create_crm_lead",
        "description": "Create a new CRM lead/opportunity. REQUIRES user confirmation.",
        "parameters": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Lead/opportunity title",
                },
                "partner_name": {
                    "type": "string",
                    "description": "Customer/company name (optional)",
                },
                "expected_revenue": {
                    "type": "number",
                    "description": "Expected revenue amount (optional)",
                },
                "stage_name": {
                    "type": "string",
                    "description": "Pipeline stage name (optional, defaults to first stage)",
                },
            },
        },
    },
    # ── 17.0.14 employee-self-service tools ────────────────────────────────
    {
        "name": "find_partner",
        "description": (
            "Look up a contact (customer, vendor, or company) in the address "
            "book by name, email, or phone. Returns name, email, phone and "
            "country for the best matches. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name, email, or phone (any partial match)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 5)",
                },
            },
        },
    },
    {
        "name": "clock_in",
        "description": (
            "Start an attendance entry for the current employee (clock in). "
            "REQUIRES user confirmation. Fails if the employee is already "
            "clocked in."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "clock_out",
        "description": (
            "End the current employee's open attendance entry (clock out). "
            "REQUIRES user confirmation. Fails if the employee is not clocked "
            "in."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "submit_expense",
        "description": (
            "Create a draft expense for the current employee (no auto-submit "
            "for approval). REQUIRES user confirmation."
        ),
        "parameters": {
            "type": "object",
            "required": ["description", "amount"],
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short description, e.g. 'Lunch with ACME'",
                },
                "amount": {
                    "type": "number",
                    "description": "Total amount including tax",
                },
                "expense_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD; defaults to today",
                },
            },
        },
    },
    {
        "name": "submit_timesheet",
        "description": (
            "Log a timesheet entry for the current employee against a project "
            "(and optionally a task). REQUIRES user confirmation."
        ),
        "parameters": {
            "type": "object",
            "required": ["project_name", "hours", "description"],
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name of the project to log time against",
                },
                "task_name": {
                    "type": "string",
                    "description": "Optional task name within the project",
                },
                "hours": {
                    "type": "number",
                    "description": "Decimal hours, e.g. 1.5",
                },
                "description": {
                    "type": "string",
                    "description": "What the time was spent on",
                },
                "entry_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD; defaults to today",
                },
            },
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a calendar event with the current user as organizer. "
            "REQUIRES user confirmation."
        ),
        "parameters": {
            "type": "object",
            "required": ["name", "start"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Event title",
                },
                "start": {
                    "type": "string",
                    "description": (
                        "Start datetime in 'YYYY-MM-DD HH:MM' (24h, the "
                        "user's local time will be assumed -- the LLM should "
                        "convert relative phrases like 'tomorrow at 10am' "
                        "before calling)."
                    ),
                },
                "duration_hours": {
                    "type": "number",
                    "description": "Duration in hours, default 1.0",
                },
            },
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────


def execute_tool(env, tool_name: str, args: dict) -> str:
    """Dispatch to the right tool function. Returns a string result."""
    fn_map = {
        "get_my_tasks": get_my_tasks,
        "get_sale_orders": get_sale_orders,
        "get_crm_leads": get_crm_leads,
        "get_stock_products": get_stock_products,
        "get_invoices": get_invoices,
        "get_purchase_orders": get_purchase_orders,
        "get_employees": get_employees,
        "get_my_leaves": get_my_leaves,
        "mark_task_done": mark_task_done,
        "confirm_sale_order": confirm_sale_order,
        "approve_leave": approve_leave,
        "update_crm_stage": update_crm_stage,
        "create_crm_lead": create_crm_lead,
        # 17.0.14 employee-self-service
        "find_partner": find_partner,
        "clock_in": clock_in,
        "clock_out": clock_out,
        "submit_expense": submit_expense,
        "submit_timesheet": submit_timesheet,
        "create_calendar_event": create_calendar_event,
    }
    fn = fn_map.get(tool_name)
    if not fn:
        return f"Unknown tool: {tool_name}"
    try:
        return fn(env, **args)
    except Exception as e:
        _logger.exception("Tool %s failed", tool_name)
        return f"Error: {e}"


def _check_model(env, model_name: str, module_hint: str) -> str | None:
    """Return a user-friendly error if an optional Odoo module isn't installed."""
    if model_name not in env.registry:
        return f"The {module_hint} module is not installed on this Odoo instance."
    return None


def _fmt_date(dt):
    if not dt:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%d %b %Y")
    return str(dt)[:10]


def _fmt_confirmation(tool_name: str, args: dict) -> str:
    """Fallback confirmation prompt — only used when preflight is bypassed.

    The agent loop now calls :func:`preflight_write` which builds a
    confirmation that references the resolved record's display_name (not the
    LLM's argument string), so this fallback is rarely hit. Kept for backward
    compatibility with any caller that stages a write directly.
    """
    if tool_name == "mark_task_done":
        return f"Mark task <b>{args.get('task_name')}</b> as done?"
    if tool_name == "confirm_sale_order":
        return f"Confirm sale order <b>{args.get('order_name')}</b>?"
    if tool_name == "approve_leave":
        msg = f"Approve leave for <b>{args.get('employee_name')}</b>"
        if args.get("leave_type"):
            msg += f" ({args['leave_type']})"
        return msg + "?"
    if tool_name == "update_crm_stage":
        return (
            f"Move lead <b>{args.get('lead_name')}</b> to "
            f"stage <b>{args.get('stage_name')}</b>?"
        )
    if tool_name == "create_crm_lead":
        msg = f"Create new lead: <b>{args.get('name')}</b>"
        if args.get("partner_name"):
            msg += f" for {args['partner_name']}"
        if args.get("expected_revenue"):
            msg += f" — revenue: {args['expected_revenue']:,.0f}"
        return msg + "?"
    if tool_name == "clock_in":
        return "Clock in now?"
    if tool_name == "clock_out":
        return "Clock out now?"
    if tool_name == "submit_expense":
        return (
            f"Submit expense <b>{args.get('description')}</b> for "
            f"<b>{args.get('amount', 0):,.2f}</b>?"
        )
    if tool_name == "submit_timesheet":
        return (
            f"Log <b>{args.get('hours')}h</b> on "
            f"<b>{args.get('project_name')}</b> "
            f'&mdash; "{args.get("description")}"?'
        )
    if tool_name == "create_calendar_event":
        return f"Create event <b>{args.get('name')}</b> at <b>{args.get('start')}</b>?"
    # Fallback
    return f"Execute <b>{tool_name}</b>?"


# ── Preflight: resolve write targets BEFORE staging confirmation ───────────────


_MIN_SEARCH_LEN = 3


def _validate_search_term(s, *, min_len: int = _MIN_SEARCH_LEN) -> str | None:
    """Reject overly-short or wildcard-only names that match too much.

    Returns ``None`` if the term is acceptable, or a user-facing error string.
    """
    if not s or not isinstance(s, str):
        return "I need a more specific name to identify the record."
    cleaned = s.strip()
    # Strip SQL ``ilike`` wildcards before measuring length so a term like
    # "%" or " " or "_" (which would match every row) is rejected.
    stripped = cleaned.replace("%", "").replace("_", "").strip()
    if len(stripped) < min_len:
        return (
            f"The name '{cleaned}' is too short or too generic. Please give "
            f"me at least {min_len} non-wildcard characters of the record name."
        )
    return None


def preflight_write(env, tool_name: str, args: dict) -> dict:
    """Resolve the target(s) of a write tool BEFORE the confirmation prompt.

    Returns either:

    * ``{"ok": True, "args": <resolved_args>, "question": <html>}`` — the
      caller should stage ``resolved_args`` (which include the resolved
      record id(s)) and send ``question`` to the user.
    * ``{"ok": False, "error": <message>}`` — short-circuit: surface the
      error to the user, do NOT stage anything.

    Why this exists:

    The previous design stored the LLM-supplied ``name`` strings in
    ``pending_args`` and resolved them via ``name ilike <s>`` at execute
    time. That left the user clicking *Yes* on a confirmation prompt that
    showed the LLM's *argument string*, while the executor could resolve a
    completely different record. A poisoned customer name like ``%`` (or any
    very short string) matches almost everything; a prompt-injection living
    in CRM lead notes could lure the LLM into supplying such a string and
    the user would unknowingly confirm a write to an unrelated record.

    Resolving up-front and storing the resolved id pins the staged write to
    a specific row; the confirmation prompt shows the resolved
    ``display_name`` so the user sees what they are actually about to mutate.
    Short / wildcard-only terms are rejected outright.
    """
    if tool_name == "mark_task_done":
        task_name = (args.get("task_name") or "").strip()
        err = _validate_search_term(task_name)
        if err:
            return {"ok": False, "error": err}
        if "project.task" not in env.registry:
            return {"ok": False, "error": "The Project module is not installed."}
        task = env["project.task"].search(
            [
                ("name", "ilike", task_name),
                ("stage_id.fold", "=", False),
                ("user_ids", "in", [env.uid]),
            ],
            limit=1,
        )
        if not task:
            return {"ok": False, "error": f"Task '{task_name}' not found."}
        proj = f" [{task.project_id.name}]" if task.project_id else ""
        return {
            "ok": True,
            "args": {"task_id": task.id, "task_name": task.name},
            "question": f"Mark task <b>{task.name}</b>{proj} as done?",
        }

    if tool_name == "confirm_sale_order":
        order_name = (args.get("order_name") or "").strip()
        err = _validate_search_term(order_name)
        if err:
            return {"ok": False, "error": err}
        if "sale.order" not in env.registry:
            return {"ok": False, "error": "The Sales module is not installed."}
        order = env["sale.order"].search(
            [("name", "ilike", order_name), ("state", "in", ["draft", "sent"])],
            limit=1,
        )
        if not order:
            return {
                "ok": False,
                "error": f"Sale order '{order_name}' not found or already confirmed.",
            }
        return {
            "ok": True,
            "args": {"order_id": order.id, "order_name": order.name},
            "question": (
                f"Confirm sale order <b>{order.name}</b> for "
                f"{order.partner_id.name} "
                f"({order.currency_id.symbol}{order.amount_total:,.2f})?"
            ),
        }

    if tool_name == "approve_leave":
        employee_name = (args.get("employee_name") or "").strip()
        err = _validate_search_term(employee_name)
        if err:
            return {"ok": False, "error": err}
        if "hr.leave" not in env.registry:
            return {
                "ok": False,
                "error": "The HR / Time Off module is not installed.",
            }
        domain = [
            ("employee_id.name", "ilike", employee_name),
            ("state", "in", ["confirm", "validate1"]),
        ]
        leave_type = (args.get("leave_type") or "").strip()
        if leave_type:
            domain.append(("holiday_status_id.name", "ilike", leave_type))
        leave = env["hr.leave"].search(domain, limit=1, order="date_from asc")
        if not leave:
            return {
                "ok": False,
                "error": f"No pending leave found for '{employee_name}'.",
            }
        return {
            "ok": True,
            "args": {
                "leave_id": leave.id,
                "employee_name": leave.employee_id.name,
            },
            "question": (
                f"Approve leave for <b>{leave.employee_id.name}</b> &mdash; "
                f"{leave.holiday_status_id.name} "
                f"({_fmt_date(leave.date_from)} &rarr; {_fmt_date(leave.date_to)})?"
            ),
        }

    if tool_name == "update_crm_stage":
        lead_name = (args.get("lead_name") or "").strip()
        stage_name = (args.get("stage_name") or "").strip()
        err = _validate_search_term(lead_name) or _validate_search_term(stage_name)
        if err:
            return {"ok": False, "error": err}
        if "crm.lead" not in env.registry:
            return {"ok": False, "error": "The CRM module is not installed."}
        lead = env["crm.lead"].search(
            [("name", "ilike", lead_name), ("type", "=", "opportunity")],
            limit=1,
        )
        if not lead:
            return {"ok": False, "error": f"Opportunity '{lead_name}' not found."}
        # Scope stage lookup to the lead's sales team (or to global stages
        # with team_id unset). Without this, the LLM could move the lead
        # into a stage that belongs to another team's pipeline entirely.
        if lead.team_id:
            stage_domain = [
                ("name", "ilike", stage_name),
                "|",
                ("team_id", "=", lead.team_id.id),
                ("team_id", "=", False),
            ]
        else:
            stage_domain = [("name", "ilike", stage_name)]
        stage = env["crm.stage"].search(stage_domain, limit=1)
        if not stage:
            return {
                "ok": False,
                "error": (
                    f"Stage '{stage_name}' not found in this lead's pipeline. "
                    "Check the stage name."
                ),
            }
        return {
            "ok": True,
            "args": {
                "lead_id": lead.id,
                "stage_id": stage.id,
                "lead_name": lead.name,
                "stage_name": stage.name,
            },
            "question": (
                f"Move lead <b>{lead.name}</b> from "
                f"<i>{lead.stage_id.name or '?'}</i> &rarr; "
                f"<b>{stage.name}</b>?"
            ),
        }

    if tool_name == "create_crm_lead":
        name = (args.get("name") or "").strip()
        if len(name) < 2:
            return {"ok": False, "error": "Lead name is too short."}
        if "crm.lead" not in env.registry:
            return {"ok": False, "error": "The CRM module is not installed."}
        partner_name = (args.get("partner_name") or "").strip()
        partner_id = None
        partner_display = ""
        if partner_name:
            partner = env["res.partner"].search(
                [("name", "ilike", partner_name)], limit=1
            )
            if partner:
                partner_id = partner.id
                partner_display = partner.name
            else:
                partner_display = partner_name
        stage_name = (args.get("stage_name") or "").strip()
        stage_id = None
        if stage_name:
            stage = env["crm.stage"].search([("name", "ilike", stage_name)], limit=1)
            if stage:
                stage_id = stage.id
        resolved = {
            "name": name,
            "partner_id": partner_id,
            "partner_name": partner_name if not partner_id else None,
            "expected_revenue": args.get("expected_revenue"),
            "stage_id": stage_id,
        }
        question = f"Create new lead: <b>{name}</b>"
        if partner_display:
            question += f" for {partner_display}"
        revenue = args.get("expected_revenue")
        if revenue:
            question += f" &mdash; revenue: {revenue:,.0f}"
        return {"ok": True, "args": resolved, "question": question + "?"}

    # ── 17.0.14 employee-self-service write tools ─────────────────────

    if tool_name == "clock_in":
        if "hr.attendance" not in env.registry:
            return {"ok": False, "error": "The Attendances module is not installed."}
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not emp:
            return {
                "ok": False,
                "error": "No HR employee record is linked to your user.",
            }
        # Reject if already clocked in (open attendance with no check_out).
        open_att = env["hr.attendance"].search(
            [("employee_id", "=", emp.id), ("check_out", "=", False)], limit=1
        )
        if open_att:
            since = _fmt_date(open_att.check_in)
            return {
                "ok": False,
                "error": (
                    f"You are already clocked in (since {since}). Clock out first."
                ),
            }
        return {
            "ok": True,
            "args": {"employee_id": emp.id},
            "question": f"Clock in <b>{emp.name}</b> now?",
        }

    if tool_name == "clock_out":
        if "hr.attendance" not in env.registry:
            return {"ok": False, "error": "The Attendances module is not installed."}
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not emp:
            return {
                "ok": False,
                "error": "No HR employee record is linked to your user.",
            }
        open_att = env["hr.attendance"].search(
            [("employee_id", "=", emp.id), ("check_out", "=", False)],
            limit=1,
            order="check_in desc",
        )
        if not open_att:
            return {"ok": False, "error": "You are not currently clocked in."}
        return {
            "ok": True,
            "args": {"attendance_id": open_att.id, "employee_name": emp.name},
            "question": (
                f"Clock out <b>{emp.name}</b>? "
                f"(working since {_fmt_date(open_att.check_in)})"
            ),
        }

    if tool_name == "submit_expense":
        if "hr.expense" not in env.registry:
            return {"ok": False, "error": "The Expenses module is not installed."}
        description = (args.get("description") or "").strip()
        if len(description) < 3:
            return {"ok": False, "error": "Expense description is too short."}
        try:
            amount = float(args.get("amount") or 0)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Amount must be a number."}
        if amount <= 0:
            return {"ok": False, "error": "Amount must be greater than zero."}
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not emp:
            return {
                "ok": False,
                "error": "No HR employee record is linked to your user.",
            }
        expense_date = (
            args.get("expense_date") or ""
        ).strip() or fields.Date.today().isoformat()
        return {
            "ok": True,
            "args": {
                "employee_id": emp.id,
                "description": description,
                "amount": amount,
                "expense_date": expense_date,
            },
            "question": (
                f"Submit expense <b>{description}</b> for "
                f"<b>{amount:,.2f}</b> dated {expense_date}? "
                "(Will be saved as draft for HR approval.)"
            ),
        }

    if tool_name == "submit_timesheet":
        if "account.analytic.line" not in env.registry:
            return {
                "ok": False,
                "error": "The Timesheets module is not installed.",
            }
        project_name = (args.get("project_name") or "").strip()
        err = _validate_search_term(project_name)
        if err:
            return {"ok": False, "error": err}
        description = (args.get("description") or "").strip()
        if len(description) < 3:
            return {
                "ok": False,
                "error": "Please give a short description of the work.",
            }
        try:
            hours = float(args.get("hours") or 0)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Hours must be a number."}
        if hours <= 0 or hours > 24:
            return {
                "ok": False,
                "error": "Hours must be between 0 and 24 for a single entry.",
            }
        project = env["project.project"].search(
            [("name", "ilike", project_name)], limit=1
        )
        if not project:
            return {"ok": False, "error": f"Project '{project_name}' not found."}
        task_name = (args.get("task_name") or "").strip()
        task_id = None
        task_label = ""
        if task_name:
            task = env["project.task"].search(
                [("project_id", "=", project.id), ("name", "ilike", task_name)],
                limit=1,
            )
            if task:
                task_id = task.id
                task_label = task.name
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not emp:
            return {
                "ok": False,
                "error": "No HR employee record is linked to your user.",
            }
        entry_date = (
            args.get("entry_date") or ""
        ).strip() or fields.Date.today().isoformat()
        suffix = f" / <b>{task_label}</b>" if task_label else ""
        return {
            "ok": True,
            "args": {
                "project_id": project.id,
                "task_id": task_id,
                "employee_id": emp.id,
                "hours": hours,
                "description": description,
                "entry_date": entry_date,
            },
            "question": (
                f"Log <b>{hours}h</b> on <b>{project.name}</b>{suffix} "
                f'for {entry_date} &mdash; "{description}"?'
            ),
        }

    if tool_name == "create_calendar_event":
        if "calendar.event" not in env.registry:
            return {"ok": False, "error": "The Calendar module is not installed."}
        name = (args.get("name") or "").strip()
        if len(name) < 2:
            return {"ok": False, "error": "Event name is too short."}
        start = (args.get("start") or "").strip()
        if not start:
            return {"ok": False, "error": "Start datetime is required."}
        # Parse the LLM-provided datetime. We accept either a plain
        # 'YYYY-MM-DD HH:MM' (most common from LLMs) or a full ISO
        # 'YYYY-MM-DDTHH:MM:SS' string. Anything else is rejected up
        # front rather than by the ORM at execute time.
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(start, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return {
                "ok": False,
                "error": (
                    f"Could not parse start time '{start}'. Use "
                    "YYYY-MM-DD HH:MM (24-hour clock)."
                ),
            }
        try:
            duration = float(args.get("duration_hours") or 1.0)
        except (TypeError, ValueError):
            duration = 1.0
        if duration <= 0 or duration > 24:
            return {
                "ok": False,
                "error": "Duration must be between 0 and 24 hours.",
            }
        stop = parsed + timedelta(hours=duration)
        return {
            "ok": True,
            "args": {
                "name": name,
                "start": parsed.strftime("%Y-%m-%d %H:%M:%S"),
                "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_hours": duration,
            },
            "question": (
                f"Create event <b>{name}</b> on "
                f"<b>{parsed.strftime('%a %d %b, %H:%M')}</b> "
                f"for {duration:.1f}h?"
            ),
        }

    return {"ok": False, "error": f"Unknown write tool: {tool_name}"}


# ── Read tools ─────────────────────────────────────────────────────────────────


def get_my_tasks(env, project=None, limit=10, **_):
    err = _check_model(env, "project.task", "Project")
    if err:
        return err
    domain = [("user_ids", "in", [env.uid]), ("stage_id.fold", "=", False)]
    if project:
        domain.append(("project_id.name", "ilike", project))
    tasks = env["project.task"].search(
        domain, limit=int(limit), order="date_deadline asc"
    )
    if not tasks:
        return "No open tasks found."
    lines = [
        f"- {t.name}"
        + (f" [{t.project_id.name}]" if t.project_id else "")
        + (f" — due {_fmt_date(t.date_deadline)}" if t.date_deadline else "")
        for t in tasks
    ]
    return f"Open tasks ({len(tasks)}):\n" + "\n".join(lines)


def get_sale_orders(env, state=None, limit=10, **_):
    err = _check_model(env, "sale.order", "Sales")
    if err:
        return err
    domain = []
    if state:
        domain.append(("state", "=", state))
    orders = env["sale.order"].search(domain, limit=int(limit), order="date_order desc")
    if not orders:
        return "No sale orders found."
    lines = [
        f"- {o.name} | {o.partner_id.name} | {o.state} | {o.currency_id.symbol}{o.amount_total:,.2f}"
        for o in orders
    ]
    return f"Sale orders ({len(orders)}):\n" + "\n".join(lines)


def get_crm_leads(env, stage=None, limit=10, **_):
    err = _check_model(env, "crm.lead", "CRM")
    if err:
        return err
    domain = [("user_id", "=", env.uid)]
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    leads = env["crm.lead"].search(domain, limit=int(limit), order="priority desc")
    if not leads:
        return "No leads or opportunities found."
    lines = [
        f"- {lead.name} | {lead.partner_id.name or 'No contact'} | {lead.stage_id.name} | {lead.expected_revenue:,.0f}"
        for lead in leads
    ]
    return f"CRM leads/opportunities ({len(leads)}):\n" + "\n".join(lines)


def get_stock_products(env, name=None, low_stock_only=False, limit=10, **_):
    err = _check_model(env, "product.product", "Inventory")
    if err:
        return err
    domain = []
    if name:
        domain.append(("name", "ilike", name))
    if low_stock_only:
        domain.append(("qty_available", "<=", 0))
    products = env["product.product"].search(domain, limit=int(limit))
    if not products:
        return "No products found."
    lines = [
        f"- {p.display_name} — {p.qty_available} {p.uom_id.name}" for p in products
    ]
    return f"Products ({len(lines)}):\n" + "\n".join(lines)


def get_invoices(env, state=None, overdue_only=False, limit=10, **_):
    err = _check_model(env, "account.move", "Accounting")
    if err:
        return err
    domain = [("move_type", "=", "out_invoice")]
    if overdue_only:
        # overdue_only implies posted + unpaid + past due; ignore any separate state filter
        domain += [
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("invoice_date_due", "<", datetime.today().strftime("%Y-%m-%d")),
        ]
    elif state:
        domain.append(("state", "=", state))
    invoices = env["account.move"].search(
        domain, limit=int(limit), order="invoice_date_due asc"
    )
    if not invoices:
        return "No invoices found."
    lines = [
        f"- {i.name} | {i.partner_id.name} | {i.currency_id.symbol}{i.amount_residual:,.2f} | due {_fmt_date(i.invoice_date_due)}"
        for i in invoices
    ]
    return f"Invoices ({len(invoices)}):\n" + "\n".join(lines)


def get_purchase_orders(env, state=None, limit=10, **_):
    err = _check_model(env, "purchase.order", "Purchase")
    if err:
        return err
    domain = []
    if state:
        domain.append(("state", "=", state))
    orders = env["purchase.order"].search(
        domain, limit=int(limit), order="date_order desc"
    )
    if not orders:
        return "No purchase orders found."
    lines = [
        f"- {o.name} | {o.partner_id.name} | {o.state} | {o.currency_id.symbol}{o.amount_total:,.2f}"
        for o in orders
    ]
    return f"Purchase orders ({len(orders)}):\n" + "\n".join(lines)


def get_employees(env, department=None, limit=10, **_):
    err = _check_model(env, "hr.employee", "Human Resources")
    if err:
        return err
    domain = [("active", "=", True)]
    if department:
        domain.append(("department_id.name", "ilike", department))
    employees = env["hr.employee"].search(domain, limit=int(limit))
    if not employees:
        return "No employees found."
    lines = [
        f"- {e.name} | {e.job_id.name or 'No job'} | {e.department_id.name or 'No dept'}"
        for e in employees
    ]
    return f"Employees ({len(employees)}):\n" + "\n".join(lines)


def get_my_leaves(env, state=None, team_leaves=False, limit=10, **_):
    err = _check_model(env, "hr.leave", "Human Resources / Time Off")
    if err:
        return err
    _STATE_LABELS = {
        "confirm": "Waiting approval",
        "validate1": "2nd approval needed",
        "validate": "Approved",
        "refuse": "Refused",
    }
    if team_leaves:
        # Show leaves from direct reports (manager view)
        employee = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not employee:
            return "No employee record found for your account."
        domain = [("employee_id.parent_id", "=", employee.id)]
    else:
        domain = [("employee_id.user_id", "=", env.uid)]

    if state:
        domain.append(("state", "=", state))
    else:
        # Default: show pending + upcoming approved
        domain.append(("state", "in", ["confirm", "validate1", "validate"]))

    leaves = env["hr.leave"].search(domain, limit=int(limit), order="date_from asc")
    if not leaves:
        return "No leave requests found."
    lines = [
        f"- {leave.employee_id.name} | {leave.holiday_status_id.name} | "
        f"{_fmt_date(leave.date_from)} → {_fmt_date(leave.date_to)} | "
        f"{_STATE_LABELS.get(leave.state, leave.state)}"
        for leave in leaves
    ]
    return f"Leave requests ({len(leaves)}):\n" + "\n".join(lines)


# ── Write tools ────────────────────────────────────────────────────────────────


def mark_task_done(env, task_id=None, task_name: str = "", **_):
    """Mark a task done.

    Prefers ``task_id`` (set by :func:`preflight_write` at staging time).
    Falls back to a name-based search only if no id was supplied — kept for
    backward compatibility with any direct call path that bypasses preflight.
    """
    err = _check_model(env, "project.task", "Project")
    if err:
        return err
    if task_id:
        task = env["project.task"].browse(int(task_id)).exists()
        # Re-check ownership at execute time: the staged write was authorised
        # for this user when staged, but we re-verify so a record-rule change
        # between staging and confirmation cannot let the write slip through.
        if not task or env.uid not in task.user_ids.ids:
            return "That task is no longer available."
    else:
        if not (task_name or "").strip():
            return "I need a task name."
        task = env["project.task"].search(
            [
                ("name", "ilike", task_name),
                ("stage_id.fold", "=", False),
                ("user_ids", "in", [env.uid]),
            ],
            limit=1,
        )
        if not task:
            return f"Task '{task_name}' not found."
    done_stage = env["project.task.type"].search([("fold", "=", True)], limit=1)
    if not done_stage:
        return "No 'done' stage found in your project configuration."
    task.write({"stage_id": done_stage.id})
    return f"✅ Task '{task.name}' marked as done."


def confirm_sale_order(env, order_id=None, order_name: str = "", **_):
    err = _check_model(env, "sale.order", "Sales")
    if err:
        return err
    if order_id:
        order = env["sale.order"].browse(int(order_id)).exists()
        if not order or order.state not in ("draft", "sent"):
            return "That sale order is no longer in a confirmable state."
    else:
        if not (order_name or "").strip():
            return "I need an order name."
        order = env["sale.order"].search(
            [("name", "ilike", order_name), ("state", "in", ["draft", "sent"])],
            limit=1,
        )
        if not order:
            return f"Sale order '{order_name}' not found or already confirmed."
    order.action_confirm()
    return f"✅ Sale order {order.name} confirmed."


def approve_leave(
    env,
    leave_id=None,
    employee_name: str = "",
    leave_type: str | None = None,
    **_,
):
    err = _check_model(env, "hr.leave", "Human Resources / Time Off")
    if err:
        return err
    if leave_id:
        leave = env["hr.leave"].browse(int(leave_id)).exists()
        if not leave or leave.state not in ("confirm", "validate1"):
            return "That leave request is no longer pending approval."
    else:
        if not (employee_name or "").strip():
            return "I need an employee name."
        domain = [
            ("employee_id.name", "ilike", employee_name),
            ("state", "in", ["confirm", "validate1"]),
        ]
        if leave_type:
            domain.append(("holiday_status_id.name", "ilike", leave_type))
        leave = env["hr.leave"].search(domain, limit=1, order="date_from asc")
        if not leave:
            return f"No pending leave found for '{employee_name}'."
    employee = leave.employee_id.name
    leave_name = leave.holiday_status_id.name
    date_from = _fmt_date(leave.date_from)
    date_to = _fmt_date(leave.date_to)
    leave.action_approve()
    return f"✅ Leave approved: {employee} — {leave_name} ({date_from} → {date_to})."


def update_crm_stage(
    env,
    lead_id=None,
    stage_id=None,
    lead_name: str = "",
    stage_name: str = "",
    **_,
):
    err = _check_model(env, "crm.lead", "CRM")
    if err:
        return err
    if lead_id and stage_id:
        lead = env["crm.lead"].browse(int(lead_id)).exists()
        stage = env["crm.stage"].browse(int(stage_id)).exists()
        if not lead:
            return "That opportunity no longer exists."
        if not stage:
            return "That stage no longer exists."
    else:
        if not (lead_name or "").strip() or not (stage_name or "").strip():
            return "I need both a lead name and a stage name."
        lead = env["crm.lead"].search(
            [("name", "ilike", lead_name), ("type", "=", "opportunity")],
            limit=1,
        )
        if not lead:
            return f"Opportunity '{lead_name}' not found."
        if lead.team_id:
            stage_domain = [
                ("name", "ilike", stage_name),
                "|",
                ("team_id", "=", lead.team_id.id),
                ("team_id", "=", False),
            ]
        else:
            stage_domain = [("name", "ilike", stage_name)]
        stage = env["crm.stage"].search(stage_domain, limit=1)
        if not stage:
            return f"Stage '{stage_name}' not found in this lead's pipeline."
    old_stage = lead.stage_id.name
    lead.write({"stage_id": stage.id})
    return f"✅ '{lead.name}' moved from {old_stage} → {stage.name}."


def create_crm_lead(
    env,
    name: str,
    partner_name: str | None = None,
    partner_id=None,
    expected_revenue: float | None = None,
    stage_name: str | None = None,
    stage_id=None,
    **_,
):
    err = _check_model(env, "crm.lead", "CRM")
    if err:
        return err
    vals = {
        "name": name,
        "type": "opportunity",
        "user_id": env.uid,
    }
    if partner_id:
        # Resolved by preflight — verify it still exists and is a real partner
        # under the user's read access.
        partner = env["res.partner"].browse(int(partner_id)).exists()
        if partner:
            vals["partner_id"] = partner.id
        elif partner_name:
            vals["partner_name"] = partner_name
    elif partner_name:
        partner = env["res.partner"].search([("name", "ilike", partner_name)], limit=1)
        if partner:
            vals["partner_id"] = partner.id
        else:
            vals["partner_name"] = partner_name
    if expected_revenue is not None:
        vals["expected_revenue"] = expected_revenue
    if stage_id:
        stage = env["crm.stage"].browse(int(stage_id)).exists()
        if stage:
            vals["stage_id"] = stage.id
    elif stage_name:
        stage = env["crm.stage"].search([("name", "ilike", stage_name)], limit=1)
        if stage:
            vals["stage_id"] = stage.id
    lead = env["crm.lead"].create(vals)
    return f"✅ Lead created: '{lead.name}' (ID {lead.id})."


# ── 17.0.14 employee-self-service tools ───────────────────────────────────────


_FIND_PARTNER_MAX_LIMIT = 25


def find_partner(env, name: str = "", limit: int = 5, **_):
    """Look up contacts by name, email or phone (read-only).

    Returns the best matches as a short bullet list. Searches three
    fields with a single ``OR`` domain so a phone-like or email-like
    query lands on the right column without the LLM having to specify.

    The ``limit`` parameter is hard-capped at ``_FIND_PARTNER_MAX_LIMIT``
    regardless of what the LLM passes. Without the cap, a chat-mediated
    address-book scrape would be one ``find_partner(name='%', limit=999999)``
    call away. Record rules already filter what the linked user can see,
    but the cap keeps any single response from accidentally returning
    the whole partner table.
    """
    if not (name or "").strip():
        return "Please give me a name, email or phone to search for."
    term = name.strip()
    domain = [
        "|",
        "|",
        ("name", "ilike", term),
        ("email", "ilike", term),
        ("phone", "ilike", term),
    ]
    try:
        requested = int(limit) or 5
    except (TypeError, ValueError):
        requested = 5
    capped_limit = max(1, min(requested, _FIND_PARTNER_MAX_LIMIT))
    partners = env["res.partner"].search(domain, limit=capped_limit)
    if not partners:
        return f"No contact matched '{term}'."
    lines = []
    for p in partners:
        bits = [p.name or "(no name)"]
        if p.email:
            bits.append(p.email)
        if p.phone:
            bits.append(p.phone)
        if p.country_id:
            bits.append(p.country_id.name)
        lines.append("- " + " | ".join(bits))
    return f"Contacts matching '{term}' ({len(partners)}):\n" + "\n".join(lines)


def clock_in(env, employee_id=None, **_):
    """Open a new attendance entry for the linked employee."""
    err = _check_model(env, "hr.attendance", "Attendances")
    if err:
        return err
    if employee_id:
        emp = env["hr.employee"].browse(int(employee_id)).exists()
    else:
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
    if not emp:
        return "No HR employee record is linked to your user."
    # Re-check at execute time: someone may have clocked in via the web
    # UI between staging and confirmation.
    open_att = env["hr.attendance"].search(
        [("employee_id", "=", emp.id), ("check_out", "=", False)], limit=1
    )
    if open_att:
        return f"You are already clocked in (since {_fmt_date(open_att.check_in)})."
    att = env["hr.attendance"].create(
        {"employee_id": emp.id, "check_in": fields.Datetime.now()}
    )
    return f"✅ Clocked in {emp.name} at {_fmt_date(att.check_in)}."


def clock_out(env, attendance_id=None, employee_name: str = "", **_):
    """Close the linked employee's open attendance entry."""
    err = _check_model(env, "hr.attendance", "Attendances")
    if err:
        return err
    att = None
    if attendance_id:
        att = env["hr.attendance"].browse(int(attendance_id)).exists()
        if not att or att.check_out:
            return "That attendance entry is no longer open."
    else:
        emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
        if not emp:
            return "No HR employee record is linked to your user."
        att = env["hr.attendance"].search(
            [("employee_id", "=", emp.id), ("check_out", "=", False)],
            limit=1,
            order="check_in desc",
        )
        if not att:
            return "You are not currently clocked in."
    att.write({"check_out": fields.Datetime.now()})
    # worked_hours is computed by hr.attendance and reflects the just-
    # written check_out without us having to re-read.
    hours = getattr(att, "worked_hours", None)
    summary = f"({hours:.2f}h)" if hours else ""
    return f"✅ Clocked out {att.employee_id.name} {summary}."


def submit_expense(
    env,
    employee_id=None,
    description: str = "",
    amount: float = 0.0,
    expense_date: str = "",
    **_,
):
    """Create a draft expense for the linked employee.

    Created in the default draft state (``state='draft'``) so the
    employee or HR can review it in Odoo before submission for approval.
    Auto-submitting from chat would skip a deliberate human checkpoint.
    """
    err = _check_model(env, "hr.expense", "Expenses")
    if err:
        return err
    # Defence-in-depth: re-resolve employee_id from env.uid at execute
    # time, ignoring whatever was in the staged args. Today the agent
    # loop always populates employee_id correctly via preflight_write,
    # but binding to env.uid here means a future code path that stages
    # a write with a different shape (or a future bug that lets a user
    # influence pending_args) cannot trick us into writing as somebody
    # else's hr.employee. Same pattern as mark_task_done's
    # ownership re-check.
    actual_emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
    if not actual_emp:
        return "No HR employee record is linked to your user."
    if employee_id and int(employee_id) != actual_emp.id:
        _logger.warning(
            "OdooPilot: submit_expense ignoring staged employee_id=%s "
            "(does not match env.uid's employee=%s); writing as %s",
            employee_id,
            actual_emp.id,
            actual_emp.name,
        )
    vals = {
        "name": description or "Expense submitted via OdooPilot",
        "employee_id": actual_emp.id,
        "total_amount": float(amount),
    }
    if expense_date:
        vals["date"] = expense_date
    expense = env["hr.expense"].create(vals)
    return (
        f"✅ Draft expense '{expense.name}' for {expense.total_amount:,.2f} "
        f"created (ID {expense.id}). Review and submit in Odoo when ready."
    )


def submit_timesheet(
    env,
    project_id=None,
    task_id=None,
    employee_id=None,
    hours: float = 0.0,
    description: str = "",
    entry_date: str = "",
    project_name: str = "",
    task_name: str = "",
    **_,
):
    """Log hours against a project (and optionally a task)."""
    err = _check_model(env, "account.analytic.line", "Timesheets")
    if err:
        return err
    if not project_id:
        proj = env["project.project"].search([("name", "ilike", project_name)], limit=1)
        if not proj:
            return f"Project '{project_name}' not found."
        project_id = proj.id
    # Defence-in-depth: same pattern as submit_expense -- re-resolve
    # employee_id from env.uid at execute time and ignore any incoming
    # value. A timesheet entry written under the wrong employee would
    # corrupt billing.
    actual_emp = env["hr.employee"].search([("user_id", "=", env.uid)], limit=1)
    if not actual_emp:
        return "No HR employee record is linked to your user."
    if employee_id and int(employee_id) != actual_emp.id:
        _logger.warning(
            "OdooPilot: submit_timesheet ignoring staged employee_id=%s "
            "(does not match env.uid's employee=%s); writing as %s",
            employee_id,
            actual_emp.id,
            actual_emp.name,
        )
    vals = {
        "project_id": int(project_id),
        "employee_id": actual_emp.id,
        "unit_amount": float(hours),
        "name": description or "Logged via OdooPilot",
    }
    if task_id:
        vals["task_id"] = int(task_id)
    if entry_date:
        vals["date"] = entry_date
    line = env["account.analytic.line"].create(vals)
    proj_name = line.project_id.name if line.project_id else "?"
    return (
        f"✅ Logged {line.unit_amount}h on '{proj_name}' "
        f"({line.date}). Entry ID {line.id}."
    )


def create_calendar_event(
    env, name: str, start: str, stop: str = "", duration_hours: float = 1.0, **_
):
    """Create a calendar event with the current user as organizer.

    ``start`` and ``stop`` are pre-validated YYYY-MM-DD HH:MM:SS strings
    produced by :func:`preflight_write`. We don't re-parse here.
    """
    err = _check_model(env, "calendar.event", "Calendar")
    if err:
        return err
    if not stop:
        # Defensive: preflight already computes stop, but accept a
        # direct call without stop.
        try:
            parsed = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return f"Invalid start datetime '{start}'."
        stop = (parsed + timedelta(hours=float(duration_hours))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    vals = {
        "name": name,
        "start": start,
        "stop": stop,
        "user_id": env.uid,
    }
    event = env["calendar.event"].create(vals)
    return f"✅ Event '{event.name}' created for {event.start} (ID {event.id})."

"""ORM-based tools for OdooPilot. Each function receives `env` (scoped to the linked user)."""
from __future__ import annotations
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


# ── Tool registry ──────────────────────────────────────────────────────────────

WRITE_TOOLS = {"mark_task_done", "create_crm_activity", "confirm_sale_order"}

TOOL_DEFINITIONS = [
    {
        "name": "get_my_tasks",
        "description": "Get open tasks assigned to the current user.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Filter by project name (optional)"},
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
                "stage": {"type": "string", "description": "Filter by stage name (optional)"},
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
                "name": {"type": "string", "description": "Product name search (optional)"},
                "low_stock_only": {"type": "boolean", "description": "Only show products with qty <= 0"},
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
                "overdue_only": {"type": "boolean", "description": "Only show overdue invoices"},
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
                "department": {"type": "string", "description": "Department name filter (optional)"},
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
                "task_name": {"type": "string", "description": "Name or partial name of the task"},
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
                "order_name": {"type": "string", "description": "Sale order name e.g. S00042"},
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
        "mark_task_done": mark_task_done,
        "confirm_sale_order": confirm_sale_order,
    }
    fn = fn_map.get(tool_name)
    if not fn:
        return f"Unknown tool: {tool_name}"
    try:
        return fn(env, **args)
    except Exception as e:
        _logger.exception("Tool %s failed", tool_name)
        return f"Error: {e}"


def _fmt_date(dt):
    if not dt:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%d %b")
    return str(dt)[:10]


def get_my_tasks(env, project=None, limit=10, **_):
    domain = [("user_ids", "in", [env.uid]), ("stage_id.fold", "=", False)]
    if project:
        domain.append(("project_id.name", "ilike", project))
    tasks = env["project.task"].search(domain, limit=int(limit), order="date_deadline asc")
    if not tasks:
        return "No open tasks found."
    lines = [
        f"- {t.name}" + (f" [{t.project_id.name}]" if t.project_id else "") + (f" - due {_fmt_date(t.date_deadline)}" if t.date_deadline else "")
        for t in tasks
    ]
    return f"Open tasks ({len(tasks)}):\n" + "\n".join(lines)


def get_sale_orders(env, state=None, limit=10, **_):
    domain = []
    if state:
        domain.append(("state", "=", state))
    orders = env["sale.order"].search(domain, limit=int(limit), order="date_order desc")
    if not orders:
        return "No sale orders found."
    lines = [f"- {o.name} | {o.partner_id.name} | {o.state} | {o.currency_id.symbol}{o.amount_total:,.2f}" for o in orders]
    return f"Sale orders ({len(orders)}):\n" + "\n".join(lines)


def get_crm_leads(env, stage=None, limit=10, **_):
    domain = [("user_id", "=", env.uid), ("type", "=", "opportunity")]
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    leads = env["crm.lead"].search(domain, limit=int(limit), order="priority desc")
    if not leads:
        return "No opportunities found."
    lines = [f"- {l.name} | {l.partner_id.name or 'No contact'} | {l.stage_id.name} | {l.expected_revenue:,.0f}" for l in leads]
    return f"Opportunities ({len(leads)}):\n" + "\n".join(lines)


def get_stock_products(env, name=None, low_stock_only=False, limit=10, **_):
    domain = []
    if name:
        domain.append(("name", "ilike", name))
    products = env["product.product"].search(domain, limit=int(limit))
    lines = []
    for p in products:
        qty = p.qty_available
        if low_stock_only and qty > 0:
            continue
        lines.append(f"- {p.display_name} - {qty} {p.uom_id.name}")
    if not lines:
        return "No products found."
    return f"Products ({len(lines)}):\n" + "\n".join(lines)


def get_invoices(env, state=None, overdue_only=False, limit=10, **_):
    domain = [("move_type", "=", "out_invoice")]
    if state:
        domain.append(("state", "=", state))
    if overdue_only:
        domain += [("state", "=", "posted"), ("payment_state", "!=", "paid"), ("invoice_date_due", "<", datetime.today().strftime("%Y-%m-%d"))]
    invoices = env["account.move"].search(domain, limit=int(limit), order="invoice_date_due asc")
    if not invoices:
        return "No invoices found."
    lines = [
        f"- {i.name} | {i.partner_id.name} | {i.currency_id.symbol}{i.amount_residual:,.2f} | due {_fmt_date(i.invoice_date_due)}"
        for i in invoices
    ]
    return f"Invoices ({len(invoices)}):\n" + "\n".join(lines)


def get_purchase_orders(env, state=None, limit=10, **_):
    domain = []
    if state:
        domain.append(("state", "=", state))
    orders = env["purchase.order"].search(domain, limit=int(limit), order="date_order desc")
    if not orders:
        return "No purchase orders found."
    lines = [f"- {o.name} | {o.partner_id.name} | {o.state} | {o.currency_id.symbol}{o.amount_total:,.2f}" for o in orders]
    return f"Purchase orders ({len(orders)}):\n" + "\n".join(lines)


def get_employees(env, department=None, limit=10, **_):
    domain = [("active", "=", True)]
    if department:
        domain.append(("department_id.name", "ilike", department))
    employees = env["hr.employee"].search(domain, limit=int(limit))
    if not employees:
        return "No employees found."
    lines = [f"- {e.name} | {e.job_id.name or 'No job'} | {e.department_id.name or 'No dept'}" for e in employees]
    return f"Employees ({len(employees)}):\n" + "\n".join(lines)


def mark_task_done(env, task_name: str, **_):
    """Write tool - agent should call send_confirmation before this runs."""
    tasks = env["project.task"].search([("name", "ilike", task_name), ("stage_id.fold", "=", False)], limit=1)
    if not tasks:
        return f"Task '{task_name}' not found."
    done_stage = env["project.task.type"].search([("fold", "=", True)], limit=1)
    if not done_stage:
        return "No 'done' stage found in your project."
    tasks.write({"stage_id": done_stage.id})
    return f"Task '{tasks.name}' marked as done."


def confirm_sale_order(env, order_name: str, **_):
    """Write tool - agent should call send_confirmation before this runs."""
    order = env["sale.order"].search([("name", "=", order_name), ("state", "in", ["draft", "sent"])], limit=1)
    if not order:
        return f"Sale order '{order_name}' not found or already confirmed."
    order.action_confirm()
    return f"Sale order {order.name} confirmed."

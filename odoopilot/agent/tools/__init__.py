from __future__ import annotations

from odoopilot.agent.tools.accounting import (
    GetInvoice,
    ListMyExpenses,
    ListOverdueInvoices,
    SubmitExpense,
)
from odoopilot.agent.tools.base import BaseTool
from odoopilot.agent.tools.crm import GetLead, ListMyLeads, LogLeadActivity
from odoopilot.agent.tools.helpdesk import GetTicket, ListMyTickets, UpdateTicketStatus
from odoopilot.agent.tools.hr import ApproveLeave, ListTeamLeaves, MyLeaveBalance, RequestLeave
from odoopilot.agent.tools.inventory import CheckStock, FindProduct, ListWarehouses
from odoopilot.agent.tools.project import GetTask, ListMyTasks, LogTimesheetEntry
from odoopilot.agent.tools.purchase import GetPurchaseOrder, ListRFQs
from odoopilot.agent.tools.sales import (
    ConfirmSaleOrder,
    GetQuote,
    GetSaleOrder,
    ListQuotes,
    ListSaleOrders,
)

ALL_TOOLS: list[BaseTool] = [
    # Inventory
    FindProduct(),
    CheckStock(),
    ListWarehouses(),
    # Sales
    ListSaleOrders(),
    GetSaleOrder(),
    ListQuotes(),
    GetQuote(),
    ConfirmSaleOrder(),
    # CRM
    ListMyLeads(),
    GetLead(),
    LogLeadActivity(),
    # Purchase
    ListRFQs(),
    GetPurchaseOrder(),
    # HR
    MyLeaveBalance(),
    ListTeamLeaves(),
    RequestLeave(),
    ApproveLeave(),
    # Accounting
    ListOverdueInvoices(),
    GetInvoice(),
    ListMyExpenses(),
    SubmitExpense(),
    # Project
    ListMyTasks(),
    GetTask(),
    LogTimesheetEntry(),
    # Helpdesk
    ListMyTickets(),
    GetTicket(),
    UpdateTicketStatus(),
]

TOOL_REGISTRY: dict[str, BaseTool] = {tool.name: tool for tool in ALL_TOOLS}

__all__ = ["ALL_TOOLS", "TOOL_REGISTRY", "BaseTool"]

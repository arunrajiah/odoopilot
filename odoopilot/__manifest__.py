{
    "name": "OdooPilot — AI Chatbot for Odoo | Telegram & WhatsApp",
    "summary": "AI agent for Odoo: query & act on live ERP data via Telegram and WhatsApp. Natural language, write actions, push alerts, audit trail. Free & open-source (LGPL-3).",
    "version": "17.0.8.0.0",
    "development_status": "Beta",
    "category": "Discuss",
    "license": "LGPL-3",
    "author": "OdooPilot Contributors",
    "website": "https://github.com/arunrajiah/odoopilot",
    "description": """
OdooPilot — AI Chatbot & Agent for Odoo (Telegram + WhatsApp)
==============================================================

The free, self-hosted AI assistant that connects your Odoo ERP to Telegram and WhatsApp.
Ask questions in plain language. Get live Odoo data. Take real actions — all with a
safety confirmation before every write operation. No external service. No SaaS fees.

Keywords: Odoo AI chatbot, Odoo AI agent, Odoo AI copilot, Telegram bot Odoo,
WhatsApp bot Odoo, ChatGPT Odoo, Claude AI Odoo, GPT-4 Odoo, Groq Odoo,
natural language ERP, Odoo NLQ, Odoo chatbot, Odoo copilot, Odoo 17 AI,
Odoo 17 Community AI, free AI Odoo, ERP chatbot, Odoo AI assistant,
employee chatbot Odoo, Odoo automation, Odoo push notifications, Odoo audit log,
multi-language Odoo bot, Odoo Telegram integration, Odoo WhatsApp integration

Key Features
------------
* **AI Agent loop**: multi-turn conversational AI agent with tool-use, powered by
  Anthropic Claude, OpenAI GPT-4, Groq (free tier), or any OpenAI-compatible endpoint
* **Natural language queries (NLQ)**: 8 Odoo domains — Projects & Tasks, CRM & Leads,
  Sales Orders, Invoices & Accounting, Inventory & Stock, Purchase Orders, HR & Employees,
  Leaves & Time Off — ask anything in plain language
* **Write actions with confirmation gate**: mark tasks done, confirm sale orders,
  approve leave requests, move CRM pipeline stages, create CRM leads — every write
  triggers an inline Yes/No confirmation before touching Odoo data
* **Dual-channel**: Telegram Bot + WhatsApp Cloud API — full feature parity on both channels
* **Multi-language support**: 15 languages — users set preferred language with /language command
  (English, French, Spanish, German, Italian, Portuguese, Dutch, Arabic, Chinese, Japanese,
  Korean, Russian, Turkish, Polish, Hindi)
* **Proactive push alerts**: daily task digest at 08:00 UTC + overdue invoice alerts at
  09:00 UTC — delivered to each user's Telegram or WhatsApp automatically
* **Full audit trail**: immutable log of every AI action — timestamp, user, tool, args,
  result, success flag — for compliance and review
* **Self-hosted / on-premise**: pure Odoo addon — no external service, no Docker,
  no cloud backend. Your data stays on your server.
* **Odoo 17 Community** compatible — no Enterprise licence required
* **5-minute setup**: install → create bot → paste API keys → Register Webhook → done

Supported AI Providers
-----------------------
* Anthropic Claude (claude-3-5-haiku, claude-opus-4, claude-sonnet-4) — best accuracy
* OpenAI GPT (gpt-4o-mini, gpt-4o, gpt-4-turbo) — widest ecosystem
* Groq free tier (llama-3.3-70b-versatile) — zero API cost to start
* Any OpenAI-compatible API endpoint (Ollama for 100% local/private AI, Together AI, etc.)

Business Domains Covered
------------------------
1. Project Tasks — list, filter, deadlines, mark done
2. CRM & Opportunities — pipeline, stages, create leads, update stage
3. Sales Orders — list, filter, confirm orders, revenue
4. Invoices & Accounting — overdue invoices, balances, payment status
5. Inventory & Stock — stock levels, locations, availability
6. Purchase Orders — RFQs, supplier orders, delivery status
7. HR & Employees — employee list, department, headcount
8. Leaves & Time Off — balances, pending approvals, approve leave

Write Tools (with Yes/No Confirmation)
---------------------------------------
* mark_task_done — mark a project task as completed
* confirm_sale_order — confirm a draft sale order in Odoo
* approve_leave — approve a pending employee leave request
* update_crm_stage — move a CRM opportunity to a different stage
* create_crm_lead — create a new CRM lead/opportunity

Security Model
--------------
* Each user's AI session inherits their Odoo access rights — no privilege escalation
* Write actions require explicit channel confirmation (inline Yes/No) before any record changes
* API keys stored in Odoo system parameters; HMAC webhook validation for Telegram
* Immutable audit log — cannot be deleted by regular users; timestamps every AI action
* Magic-link identity flow — one-time token, HTTPS only, 1-hour expiry

License: LGPL-3 | Free & Open-Source | GitHub: https://github.com/arunrajiah/odoopilot
    """,
    "depends": ["mail", "base_setup", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/odoopilot_identity_views.xml",
        "views/odoopilot_audit_views.xml",
        "views/link_pages.xml",
        "data/ir_cron.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
}

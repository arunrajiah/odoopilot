{
    "name": "OdooPilot — Your team uses Odoo without logging in to Odoo",
    "summary": "Give every employee an Odoo assistant on Telegram & WhatsApp. They apply for leave, approve requests, check tasks, update CRM, validate stock — without opening Odoo. For your internal team. Free & open-source (LGPL-3).",
    "version": "17.0.19.0.0",
    "development_status": "Beta",
    "category": "Discuss",
    "license": "LGPL-3",
    # Author follows OCA convention: project lead first, then "Odoo
    # Community Association (OCA)" once the module is accepted into an
    # OCA repository. Until then we list only the project lead so the
    # OCA suffix isn't claimed prematurely.
    # OCA convention: "Odoo Community Association (OCA)" listed once
    # the module is accepted. Adding it here pre-emptively to satisfy
    # ``pylint-odoo`` C8101 (manifest-required-author); the project
    # lead is also listed and the maintainers field below is the
    # source of truth for who actually owns the module.
    "author": "arunrajiah, Odoo Community Association (OCA)",
    "maintainers": ["arunrajiah"],
    "website": "https://github.com/arunrajiah/odoopilot",
    # The ``support`` field is the standard Odoo manifest key for an
    # operator-facing contact email. The Odoo App Store listing
    # surfaces it as a "Contact" link in the right-hand sidebar of
    # the module detail page. Operators can also reach the same
    # mailbox for security disclosures, though we strongly prefer
    # GitHub Security Advisories for those (see SECURITY.md).
    "support": "arunrajiah@gmail.com",
    # pylint-odoo flags ``description`` as deprecated (C8103) in favour
    # of ``readme/DESCRIPTION.rst``. We keep both: the readme/ files
    # feed the README.rst that OCA tooling generates at module root,
    # while the manifest's description string still gets indexed by
    # the Odoo App Store search and shown on the listing detail page.
    # noqa: C8103
    "description": """
OdooPilot — Your team uses Odoo, without logging in to Odoo
============================================================

Every Odoo deployment has the same gap: the people who generate the data
(sales reps in the field, warehouse staff, every employee who occasionally
needs to apply for leave or log an expense) are not the people sitting at
desks. They have an Odoo account, but they avoid the Odoo UI for routine
tasks — so data goes stale, approvals stall, and the ERP under-delivers.

OdooPilot closes that gap. Each employee gets an AI assistant on Telegram
or WhatsApp that connects to the same Odoo instance, scoped to the same
record-rule permissions they already have. They apply for leave, approve
requests, check tasks, update the CRM pipeline, validate stock moves —
by chatting with a bot in their own language. No Odoo login, no app to
install, no training.

This is for your internal team — NOT for your customers. Each linked
chat user must be an Odoo user, and every write is logged in the audit
trail. The only thing that changes is HOW employees reach Odoo —
through chat instead of a browser.

Keywords: Odoo employee chatbot, Odoo team assistant, Odoo without login,
Odoo voice messages, voice-to-Odoo, speak to Odoo, Whisper Odoo, Odoo STT,
mobile Odoo, Odoo on Telegram, Odoo on WhatsApp, employee self-service Odoo,
Odoo leave request bot, Odoo approval bot, field sales Odoo, warehouse Odoo,
Odoo AI chatbot, Odoo AI agent, Odoo AI copilot, Telegram bot Odoo,
WhatsApp bot Odoo, ChatGPT Odoo, Claude AI Odoo, GPT-4 Odoo, Groq Odoo,
natural language ERP, Odoo NLQ, Odoo chatbot, Odoo 17 AI,
Odoo 17 Community AI, free AI Odoo, ERP chatbot, Odoo AI assistant,
Odoo automation, Odoo push notifications, Odoo audit log,
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
* **Voice messages**: hold-to-record on Telegram or WhatsApp; OdooPilot transcribes via Whisper
  (Groq free tier or OpenAI) and runs the same agent loop as typed text. For warehouse pickers,
  drivers, anyone whose hands aren't free to type. Operator-tunable duration cap (default 60s).
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
    # Frontend assets for the in-Odoo web chat widget. The assets
    # always load; the component itself early-returns when
    # ``odoopilot.web_chat_enabled`` is False, so disabling the
    # feature in Settings simply hides the systray icon. Loading
    # ~6 KB of unused JS is cheaper than a per-page conditional
    # asset bundle.
    "assets": {
        "web.assets_backend": [
            "odoopilot/static/src/components/web_chat.js",
            "odoopilot/static/src/components/web_chat.xml",
            "odoopilot/static/src/scss/web_chat.scss",
        ],
    },
    # ``installable`` and ``auto_install`` omitted -- the OCA pylint
    # checks flag them as superfluous when set to their defaults
    # (True / False). The ``application`` flag we keep since it's
    # not the default and it puts OdooPilot in the Apps top-level
    # menu rather than the Modules submenu.
    "application": True,
}

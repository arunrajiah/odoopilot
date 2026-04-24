{
    "name": "OdooPilot — AI Telegram Bot for Odoo",
    "summary": "Chat with your Odoo ERP via Telegram using Claude AI, GPT-4 or Groq. Natural language queries, write actions, push alerts. Free & open-source.",
    "version": "17.0.6.0.0",
    "development_status": "Beta",
    "category": "Discuss",
    "license": "LGPL-3",
    "author": "OdooPilot Contributors",
    "website": "https://github.com/arunrajiah/odoopilot",
    "description": """
OdooPilot — AI Telegram Bot for Odoo
=====================================

**The free, self-hosted AI assistant that connects your Odoo ERP to Telegram.**

Ask questions in plain language. Get live Odoo data. Take real actions — with a
safety confirmation before every write operation.

Key Features
------------
* **Natural language queries** across 8 Odoo domains: Projects, CRM, Sales,
  Invoices, Inventory, Purchase, HR, and Time Off
* **Write actions**: mark tasks done, confirm sale orders, approve leaves,
  move CRM stages — all with an inline Yes/No confirmation gate
* **Multi-LLM**: Anthropic Claude, OpenAI GPT-4, Groq (free tier), or any
  OpenAI-compatible endpoint (Ollama for 100% local AI)
* **Proactive push alerts**: daily task digest + overdue invoice alerts
  delivered directly to each user's Telegram
* **Self-hosted**: pure Odoo addon — no external service, no SaaS fees,
  no data leaves your server except to your chosen LLM API
* **Full audit trail**: immutable log of every AI action for compliance
* **Odoo 17 Community** compatible — no Enterprise licence required
* **5-minute setup**: install → create Telegram bot → paste API keys → done

Supported AI Providers
-----------------------
* Anthropic Claude (claude-3-5-haiku, claude-opus-4, claude-sonnet-4)
* OpenAI (gpt-4o-mini, gpt-4o, gpt-4-turbo)
* Groq free tier (llama-3.3-70b-versatile)
* Any OpenAI-compatible API (Ollama, Together AI, etc.)

How It Works
------------
1. User sends a Telegram message to the bot
2. Odoo matches the Telegram chat ID to the linked Odoo user
3. The LLM selects and calls the right Odoo ORM tools
4. The answer is sent back to Telegram; every action is audit-logged

Security
--------
* Each user's session inherits their Odoo access rights — no privilege escalation
* Write actions require explicit Telegram confirmation before any record changes
* API keys stored in Odoo system parameters; HMAC webhook validation
* Immutable audit log with timestamp, user, tool, args, and result

License: LGPL-3 | Open-source | GitHub: https://github.com/arunrajiah/odoopilot
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

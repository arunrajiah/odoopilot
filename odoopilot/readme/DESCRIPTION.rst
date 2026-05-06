OdooPilot gives every employee an AI assistant on Telegram or WhatsApp
that connects to the same Odoo instance, scoped to the same permissions
they already have. They apply for leave, approve requests, check tasks,
update the CRM pipeline, validate stock moves -- by **typing or
speaking** to a bot in their own language. No Odoo login, no app to
install, no training.

For your **internal team**, not for your customers. Each linked chat
user is an Odoo user, sees only the data they are already authorised
to see, and every write is recorded in an immutable audit trail.

The Odoo adoption problem this solves: data goes stale because the
people who generate it (field sales, warehouse staff, anyone who
occasionally needs HR or Project) avoid the desktop UI for routine
tasks. OdooPilot meets them where they already are -- their phone,
in chat, in their language.

Key capabilities
----------------

* **19 ORM-backed tools** across 8 Odoo domains: Project, Sales, CRM,
  Invoicing, Inventory, Purchase, HR, Leaves -- read 8, write 10
  (every write goes through a Yes/No confirmation gate),
  plus contact lookup.
* **Two channels with full feature parity**: Telegram Bot API and
  Meta WhatsApp Cloud API.
* **Voice messages** via Whisper (Groq free tier or OpenAI), feeding
  the same agent loop typed text uses.
* **15 UI languages** with per-user preference.
* **Choice of LLM**: Anthropic Claude, OpenAI GPT-4o, Groq (free tier),
  or Ollama (100% local, no third-party API calls).
* **Proactive notifications**: daily task digest, overdue invoice
  alerts.
* **Self-hosted**: pure Odoo addon, no separate Python service, no
  Docker container. Your business data and prompts stay on your
  infrastructure.

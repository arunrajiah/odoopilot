# OdooPilot

**AI-powered messaging bridge for Odoo Community.** Let your team query and act on Odoo data from Telegram — in plain language, without opening a browser.

```
Employee: "What's the stock level for product REF-1042?"
OdooPilot: "Product Widget Pro (REF-1042): 247 units on hand across 2 warehouses."

Employee: "Confirm sale order SO/2024/0198"
OdooPilot: "⚠️ Confirm SO/2024/0198 for Acme Corp — €4,320.00?  [Yes ✓] [No ✗]"
```

> Think **Atomicwork for Odoo**: an AI agent that meets employees in the messaging app they already use.

---

## Why OdooPilot?

| | OdooPilot | Paid chatbot modules | OCA mail_gateway |
|---|---|---|---|
| Open-source | ✅ LGPL-3 | ❌ | ✅ |
| Employee-facing | ✅ | ❌ customer-facing | — |
| Model-agnostic | ✅ OpenAI / Anthropic / Ollama / Groq | ❌ OpenAI only | — |
| Telegram | ✅ v0.1 | rarely | ✅ transport only |
| WhatsApp | 🔜 v0.3 | ✅ | ✅ transport only |
| AI layer | ✅ | ✅ | ❌ |
| Odoo Community | ✅ | mixed | ✅ |

---

## Architecture

```
┌─────────────────────────────────┐
│  Channel adapters               │
│  Telegram (v1) · WhatsApp (v2)  │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  Identity & permission layer    │
│  (channel, chat_id) → Odoo user │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  Agent core  (LLM + tool-router)│
│  OpenAI · Anthropic · Ollama    │
│  Reads: instant  Writes: confirm│
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  Odoo adapter (JSON-RPC)        │
│  Works with any Odoo v17+       │
└─────────────────────────────────┘
```

---

## Quickstart

### Prerequisites
- Python 3.11+
- A running Odoo 17+ Community instance
- A Telegram Bot token ([@BotFather](https://t.me/BotFather))
- An API key for your chosen LLM provider

### 1. Clone and install

```bash
git clone https://github.com/arunrajiah/odoopilot.git
cd odoopilot
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Odoo URL, Telegram token, and LLM API key
```

### 3. Run with Docker (recommended)

```bash
cd examples
docker-compose up
```

### 4. Link a user

In Odoo, open **Settings → OdooPilot → Link Account** and follow the `/link` flow in Telegram.

### 5. Start chatting

Send `/start` to your bot. Ask anything about your Odoo data.

---

## Supported Odoo modules (v0.1)

| Domain | Read tools | Write tools |
|---|---|---|
| Sales | list_quotes, get_quote, list_sale_orders, get_sale_order | confirm_sale_order |
| CRM | list_my_leads, get_lead | log_lead_activity |
| Purchase | list_rfqs, get_purchase_order | — |
| Inventory | check_stock, list_warehouses, **find_product** | — |
| HR | my_leave_balance, list_team_leaves | request_leave, approve_leave |
| Accounting | list_overdue_invoices, get_invoice, list_my_expenses | submit_expense |
| Project | list_my_tasks, get_task | log_timesheet_entry |
| Helpdesk | list_my_tickets, get_ticket | update_ticket_status |

---

## LLM providers

Configure `LLM_PROVIDER` in `.env`:

| Value | Provider | Notes |
|---|---|---|
| `openai` | OpenAI | GPT-4o recommended |
| `anthropic` | Anthropic | Claude 3.5 Sonnet recommended |
| `ollama` | Ollama | Self-hosted, fully private |
| `groq` | Groq | Fast inference |

---

## Roadmap

- **v0.1** — Telegram + OpenAI/Anthropic + inventory reads. _← you are here_
- **v0.2** — All 8 domains (reads + guided writes). Ollama + Groq. Audit log UI in Odoo.
- **v0.3** — WhatsApp Cloud API adapter. i18n framework.
- **v0.4** — OCA submission. PyPI release. GitHub Sponsors launch.
- **v1.0** — Production-hardened. Rate limiting, retries, observability. Case study.

---

## Contributing

We welcome contributions! The fastest path to a merged PR:

1. Pick an unimplemented tool from the table above
2. Follow the guide in [docs/adding-a-tool.md](docs/adding-a-tool.md)
3. Open a PR — CI must be green (ruff + mypy + pytest)

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

---

## Sponsor

OdooPilot is free, open-source, and community-maintained. If it saves your team time, consider sponsoring:

**[Sponsor on GitHub →](https://github.com/sponsors/arunrajiah)**

Sponsors get:
- Priority issue responses
- Input on the roadmap
- Recognition in the README

---

## License

[LGPL-3.0-or-later](LICENSE) — same as Odoo Community and OCA modules.

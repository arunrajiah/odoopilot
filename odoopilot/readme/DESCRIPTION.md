# OdooPilot — AI Telegram Bot for Odoo

**The free, self-hosted AI assistant that connects your Odoo 17 ERP to Telegram.**

Chat with your live Odoo data in plain language. Ask about tasks, invoices, sales orders,
CRM leads, inventory, and HR — then take real write-back actions, all from a single
Telegram message. Powered by Anthropic Claude, OpenAI GPT-4, or Groq (free tier).
100% self-hosted. No SaaS fees. No external service. Just an Odoo addon.

## Why OdooPilot?

| | OdooPilot | Paid AI chatbots (€150–€360) |
|---|---|---|
| Price | **Free — LGPL-3** | €150 – €360 per install |
| Odoo Community support | ✓ Yes | ✗ Enterprise only |
| Telegram integration | ✓ Native | ✗ Not supported |
| Write actions with confirmation | ✓ 5 write tools | ✗ Read-only |
| Proactive push alerts | ✓ Tasks + invoices | ✗ No |
| Multi-LLM (Claude · GPT · Groq) | ✓ 3+ providers | ✗ OpenAI only |
| Self-hosted, no cloud backend | ✓ Pure Odoo addon | ~ Requires cloud service |
| Immutable audit trail | ✓ | ~ Basic only |

## Features

**8 Odoo business domains covered:**
- 📋 Projects & Tasks — list tasks, deadlines, mark complete
- 💼 CRM & Opportunities — pipeline, stages, create leads
- 🛒 Sales Orders — list, filter by state, confirm orders
- 🧾 Invoices & Accounting — overdue invoices, outstanding balances
- 📦 Inventory & Stock — stock levels, low-stock alerts
- 🚚 Purchase Orders — pending RFQs, supplier deliveries
- 👥 HR & Employees — employee list, department lookup
- 🏖️ Leaves & Time Off — leave requests, approvals, balances

**Write actions (all require Yes/No confirmation before execution):**
- Mark project tasks as done
- Confirm draft sale orders
- Approve employee leave requests
- Move CRM leads between pipeline stages
- Create new CRM leads / opportunities

**Proactive push alerts:**
- Daily task digest: overdue + today's tasks sent every morning
- Overdue invoice alerts: daily summary for users with accounting access

**Multi-LLM support:**
- Anthropic Claude (claude-3-5-haiku · claude-sonnet-4 · claude-opus-4)
- OpenAI (gpt-4o-mini · gpt-4o · gpt-4-turbo)
- Groq free tier (llama-3.3-70b-versatile)
- Any OpenAI-compatible endpoint (Ollama for fully local AI)

## Requirements

- Odoo 17.0 Community Edition (self-hosted or Odoo.sh)
- A Telegram Bot token — free via @BotFather
- An API key from Anthropic, OpenAI, or Groq (Groq has a free tier)
- Odoo instance reachable from the internet for webhook delivery

No additional Python packages — all API calls use `requests`, which Odoo already ships.

## Setup in 5 minutes

1. Install this addon
2. Create a Telegram bot via @BotFather → copy the token
3. Get an API key from Anthropic, OpenAI, or Groq
4. Go to **Settings → OdooPilot** → paste keys → click **Register Webhook**
5. Each team member sends `/link` to the bot → clicks the magic link → done

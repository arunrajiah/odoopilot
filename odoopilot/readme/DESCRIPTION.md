OdooPilot is an open-source AI assistant that lets your team query and act on Odoo data from **Telegram**, in plain language — without opening a browser.

Unlike other AI integrations, **everything runs inside this single Odoo addon**. There is no external service to host, no Docker container to manage, and no per-seat SaaS fees.

## What it does

- **Telegram webhook** — receives messages directly inside Odoo's HTTP layer
- **LLM tool-use loop** — calls Anthropic, OpenAI, or Groq to understand intent and select the right Odoo tool
- **Read tools** — project tasks, sales orders, CRM pipeline, invoices, inventory, HR, purchase orders
- **Write tools** — mark tasks done, confirm sale orders; all writes require inline Yes/No confirmation
- **Identity linking** — employees send `/link` to the bot, click a magic link inside Odoo, and are linked in seconds
- **Audit log** — every AI action is recorded: who asked, which tool ran, and whether it succeeded
- **Settings UI** — configure bot token, LLM provider, API key, and webhook from **Settings → OdooPilot**

## Requirements

- Odoo 17.0 Community (self-hosted or Odoo.sh)
- A Telegram Bot token (free, via @BotFather)
- An API key from Anthropic, OpenAI, or Groq
- Odoo reachable from the internet for webhook delivery

No additional Python packages required — all external API calls use `requests`, which Odoo already ships.

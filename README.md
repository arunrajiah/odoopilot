# OdooPilot

**Free, open-source AI agent for Odoo — query live ERP data and take real actions via Telegram and WhatsApp, in plain language.**

```
You:        "What tasks are assigned to me today?"
OdooPilot:  "You have 3 open tasks: Update product catalogue (due today ⚠️),
             Review Q2 report (Thu), Onboard new supplier (Fri)."

You:        "Mark the first one as done."
OdooPilot:  "✅ Update product catalogue marked as done in Odoo."
```

No external service to host. No per-seat SaaS fees. Everything runs inside your Odoo instance.  
Powered by **Claude AI**, **ChatGPT / GPT-4**, **Groq** (free tier), or **Ollama** (100% local).  
Works on **Telegram** and **WhatsApp**. Supports **15 languages**. LGPL-3 open-source.

---

## What it does

- **Conversational queries on live Odoo data** — Tasks, CRM, Sales, Invoices, Inventory, Purchase, HR, Leaves
- **Write actions with a confirmation gate** — Yes/No button required before any record changes
- **Two channels, full parity** — Telegram bot and WhatsApp Cloud API
- **Choice of LLM** — Anthropic Claude, OpenAI GPT-4o, Groq (free tier), or Ollama (100% local)
- **15 UI languages** — per-user `/language` command
- **Proactive notifications** — daily task digest and overdue-invoice alerts
- **Self-hosted** — pure Odoo addon, runs entirely inside your instance, no separate service
- **Auditable** — immutable log of every AI action (timestamp, user, tool, args, result)
- **Open source** — LGPL-3, free to install, fork, and extend

---

## Architecture

Everything runs inside the Odoo addon — no separate Python service, no Docker container, no cloud deployment.

```
Telegram
    │  HTTPS webhook
    ▼
┌─────────────────────────────────────────────┐
│  OdooPilot Odoo Addon (odoopilot/)          │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  HTTP Controller  /odoopilot/webhook │   │
│  │  Validates secret · spawns thread   │   │
│  └──────────────┬──────────────────────┘   │
│                 │                           │
│  ┌──────────────▼──────────────────────┐   │
│  │  Agent  (services/agent.py)         │   │
│  │  Loads session · runs LLM loop      │   │
│  │  Gates writes behind confirmation   │   │
│  └──────┬──────────────────────────────┘   │
│         │                    │              │
│  ┌──────▼──────┐    ┌────────▼──────────┐  │
│  │  LLM Client │    │  ORM Tools        │  │
│  │  Anthropic  │    │  project / sales  │  │
│  │  OpenAI     │    │  crm / inventory  │  │
│  │  Groq       │    │  invoices / hr    │  │
│  └─────────────┘    │  purchase         │  │
│                     └───────────────────┘  │
│                                             │
│  Models: odoopilot.session                  │
│           odoopilot.identity                │
│           odoopilot.audit                   │
└─────────────────────────────────────────────┘
```

---

## Quickstart

### Prerequisites

- Odoo **17.0 Community** (self-hosted or Odoo.sh)
- A Telegram Bot token — create one via [@BotFather](https://t.me/BotFather)
- An API key from [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), or [Groq](https://console.groq.com) (Groq has a free tier)
- Odoo must be reachable from the internet (for Telegram webhook delivery)

### 1. Install the addon

Copy the `odoopilot/` directory into your Odoo addons path, then:

```bash
# Restart Odoo and update the module list
./odoo-bin -c odoo.conf -u odoopilot
```

Or install from the [Odoo App Store](https://apps.odoo.com/apps/modules/17.0/odoopilot).

### 2. Configure in Odoo Settings

Go to **Settings → OdooPilot** and fill in:

| Field | Value |
|-------|-------|
| Telegram Bot Token | Paste the token from @BotFather |
| Webhook Secret | Any random string (keep it secret) |
| LLM Provider | `anthropic`, `openai`, or `groq` |
| LLM API Key | Your key from the provider |
| LLM Model | e.g. `claude-opus-4-5`, `gpt-4o`, `llama3-70b-8192` |

Click **Register Webhook** — OdooPilot will call Telegram's `setWebhook` API automatically.

### 3. Link employee accounts

Each employee sends `/link` to the bot. They receive a magic link, click it while logged into Odoo, and they're linked. Done.

### 4. Start chatting

Send any natural-language question to the bot. OdooPilot answers from live Odoo data.

---

## Supported domains

| Domain | Read | Write (with confirmation) |
|--------|------|--------------------------|
| Project & Tasks | ✅ list, filter, deadlines | ✅ mark task done |
| Sales & CRM | ✅ pipeline, orders, revenue | ✅ confirm sale order · update CRM stage · create lead |
| Invoices & Accounting | ✅ overdue, balances, bills | — |
| Inventory | ✅ stock levels, locations | — |
| HR & Leaves | ✅ leave balances, pending requests, employees | ✅ approve leave |
| Purchase | ✅ purchase orders, RFQs | — |

Write tools always show an inline Yes/No confirmation before touching data.

---

## LLM providers

| Provider | `llm_provider` value | Recommended model |
|----------|----------------------|-------------------|
| Anthropic | `anthropic` | `claude-opus-4-5` |
| OpenAI | `openai` | `gpt-4o` |
| Groq | `groq` | `llama3-70b-8192` |

No SDKs installed — OdooPilot calls the provider APIs directly via `requests`, so there are no extra Python dependencies beyond what Odoo already ships.

---

## Security

OdooPilot is designed so the messaging webhooks cannot be forged and so the
write-action confirmation cannot be tricked. The current model:

- **Telegram webhook** verifies Telegram's `X-Telegram-Bot-Api-Secret-Token`
  header on every POST. The secret is auto-generated when you click
  *Register webhook* in Settings. Requests without a matching secret are
  rejected with HTTP 403.
- **WhatsApp webhook** verifies Meta's `X-Hub-Signature-256` header
  (HMAC-SHA256 of the raw body) on every POST. The Meta App Secret is
  required in Settings; without it the endpoint refuses all traffic.
- **Confirmation gate.** Every write tool stages a fresh per-write nonce on
  the session. The Yes/No button payload carries `confirm:yes:<nonce>`, and
  the controller verifies it in constant time before executing. A prompt
  injection that tries to swap the staged tool between "send confirmation"
  and "user clicks Yes" rotates the nonce and the click is rejected.
- **Magic-link tokens** are stored as SHA-256 digests, single-use, and
  expire after one hour. Re-issuing a token for the same chat invalidates
  the previous one.
- **User scoping.** The webhook dispatcher resolves the chat to an
  `odoopilot.identity` and runs the agent under that Odoo user — every
  query and write is filtered by the user's existing Odoo access rights.
- **Audit trail.** Every tool call writes an immutable
  `odoopilot.audit` record (timestamp, user, tool, args, result, success).

If you find a vulnerability, please open a *private* security advisory on
GitHub or email arunrajiah at gmail. Do not disclose publicly until a fix
is released.

---

## Roadmap

| Version | Status | What's in it |
|---------|--------|--------------|
| **17.0.4.0.0** | ✅ Released | Proactive notifications — daily task digest at 08:00 UTC · overdue invoice alerts at 09:00 UTC |
| **17.0.5.0.0** | ✅ Released | WhatsApp Cloud API channel — full parity with Telegram (webhook verify, /link flow, agent, Yes/No confirmations, proactive notifications) |
| **17.0.6.0.0** | ✅ Released | Multi-language support · `/language` command · 15 languages · per-user preference stored in identity |
| **17.0.7.0.0** | ✅ **Released** | **Security release** — WhatsApp HMAC verification · mandatory Telegram secret · per-write nonce on confirmations · hashed one-shot link tokens · regression tests |
| **18.0.1.0.0** | 📋 Planned | Odoo 18 port · OCA submission |

---

## Contributing

Pull requests welcome. The fastest path to a merged PR:

1. Pick an unimplemented tool or domain from the table above
2. Add it to `odoopilot/services/tools.py` following the existing pattern
3. Register the tool schema in `odoopilot/services/agent.py`
4. Open a PR — CI must be green (ruff format + lint + XML check)

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

---

## Sponsor

OdooPilot is free, open-source, and solo-maintained. If it saves your team time, please consider sponsoring:

**[♥ Sponsor on GitHub →](https://github.com/sponsors/arunrajiah)**

---

## License

[LGPL-3.0-or-later](LICENSE) — same as Odoo Community and OCA modules.

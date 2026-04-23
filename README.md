# OdooPilot

**AI assistant for Odoo — query and act on your business data from Telegram, in plain language.**

```
You:        "What tasks are assigned to me today?"
OdooPilot:  "You have 3 open tasks: Update product catalogue (due today ⚠️),
             Review Q2 report (Thu), Onboard new supplier (Fri)."

You:        "Mark the first one as done."
OdooPilot:  "✅ Update product catalogue marked as done in Odoo."
```

No external service to host. No per-seat SaaS fees. Everything runs inside your Odoo instance.

---

## Why OdooPilot?

| | OdooPilot | Paid chatbot modules | OCA mail_gateway |
|---|---|---|---|
| Open-source | ✅ LGPL-3 | ❌ | ✅ |
| All-in-one Odoo addon | ✅ | ❌ external service | — |
| Employee-facing AI | ✅ | ❌ customer-facing | — |
| Multi-provider LLM | ✅ Anthropic / OpenAI / Groq | ❌ OpenAI only | — |
| Telegram | ✅ | rarely | ✅ transport only |
| Odoo Community | ✅ | mixed | ✅ |
| No extra infrastructure | ✅ | ❌ | ✅ |

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

## Roadmap

| Version | Status | What's in it |
|---------|--------|--------------|
| **17.0.2.0.0** | ✅ Released | All-in-one addon · Telegram webhook · 3 LLM providers · 7 domains · magic link identity · audit log |
| **17.0.3.0.0** | ✅ Released | New write tools (approve leave, update CRM stage, create lead) · get_my_leaves · 72h session TTL · human-readable confirmations · per-tool audit logging |
| **17.0.4.0.0** | ✅ **Released** | Proactive notifications — daily task digest at 08:00 UTC · overdue invoice alerts at 09:00 UTC · notification toggles in Settings |
| **17.0.5.0.0** | 🔜 Next | WhatsApp Cloud API channel |
| **17.0.6.0.0** | 📋 Planned | Multi-language support · per-user language preference |
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

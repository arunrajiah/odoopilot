# Contributing to OdooPilot

Thank you for helping make OdooPilot better. This guide gets you from zero to a merged PR.

---

## Architecture overview

OdooPilot is a single Odoo addon — no external service, no Docker container.

```
odoopilot/
├── controllers/main.py      # Telegram webhook + identity link routes
├── models/                  # Odoo ORM models (session, identity, audit, settings)
├── services/
│   ├── agent.py             # LLM tool-use loop
│   ├── llm.py               # Anthropic / OpenAI / Groq client (raw requests)
│   ├── telegram.py          # Telegram API helpers
│   └── tools.py             # ORM tool definitions + implementations
├── views/                   # XML views and link page templates
└── data/ir_cron.xml         # Session GC cron job
```

---

## Setting up a dev environment

### What you need

| Requirement | Notes |
|---|---|
| Odoo 17.0 Community | Self-hosted or [Odoo.sh](https://www.odoo.sh) |
| Telegram bot token | [@BotFather](https://t.me/BotFather) → `/newbot` |
| LLM API key | Anthropic / OpenAI / Groq (Groq has a free tier) |
| Public HTTPS URL | [ngrok](https://ngrok.com) free tier works for local testing |

### 1. Install the addon into your Odoo

Copy the `odoopilot/` directory into your Odoo addons path, then:

```bash
./odoo-bin -c odoo.conf -i odoopilot
```

Or for development with auto-reload, add the parent directory to `--addons-path`.

### 2. Expose Odoo publicly (for Telegram webhook)

```bash
ngrok http 8069
# → https://abc123.ngrok.io  ← Telegram will send webhooks here
```

### 3. Configure OdooPilot

Go to **Settings → OdooPilot** in your Odoo instance and fill in:
- Telegram Bot Token
- Webhook Secret (any random string)
- LLM Provider + API Key + Model

Click **Register Webhook** — done.

### 4. Link your account and test

Send `/link` to your bot → click the link → log in to Odoo → you're linked.

```
You: What tasks are assigned to me?
Bot: You have 3 open tasks: …
```

---

## Adding a new Odoo tool

The fastest contribution path — each business domain can always use more tools.

1. Open `odoopilot/services/tools.py`
2. Add a new entry to `TOOL_DEFINITIONS` (name, description, parameters schema)
3. If it mutates data, add the tool name to `WRITE_TOOLS` — confirmation is automatic
4. Add a `_fmt_confirmation()` branch for a human-readable confirmation prompt
5. Implement the function — receives `env` (scoped to the linked Odoo user) + kwargs
6. Register in the `fn_map` dict inside `execute_tool()`

See `mark_task_done` or `approve_leave` for a complete write tool example.
See `get_my_tasks` for a read tool example.

---

## Code guidelines

- **Linting / formatting**: `ruff` — run `ruff format odoopilot/ && ruff check odoopilot/` before committing
- **No new Python dependencies** — only stdlib + what Odoo already ships (`requests` is available)
- **Comments**: only the *why*, never the *what*
- **XML**: all views must be well-formed — the CI XML check will catch parse errors

## Commit format

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(tools): add approve_purchase_order write tool
fix(webhook): handle Telegram edited_message updates gracefully
docs: update contributing guide
```

## CI checks

Every PR must pass:
- `ruff format --check odoopilot/` — formatting
- `ruff check odoopilot/` — lint
- XML well-formed check — all `*.xml` files under `odoopilot/`

---

## Getting help

Open a [GitHub Discussion](https://github.com/arunrajiah/odoopilot/discussions) — we're friendly.

## Licensing

All contributions are LGPL-3.0-or-later. By submitting a PR you confirm you have the right to contribute under this license.

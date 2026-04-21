# Contributing to OdooPilot

Thank you for helping make OdooPilot better. This guide gets you from zero to a merged PR.

---

## Quick start

```bash
git clone https://github.com/arunrajiah/odoopilot.git
cd odoopilot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite (no external services needed):

```bash
pytest           # 43 tests, all mocked — passes without Odoo or Telegram
ruff check .
ruff format --check .
mypy odoopilot/
```

---

## End-to-end testing (optional but appreciated)

To test the full bot flow against a real Odoo instance and Telegram:

### What you need

| Requirement | How to get it |
|---|---|
| Odoo 17 Community | Docker locally (see below) or any self-hosted instance |
| Telegram bot token | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| LLM API key | OpenAI / Anthropic / Groq (free tier works) or local Ollama |
| Public HTTPS URL | [ngrok](https://ngrok.com) free tier, or deploy to Fly.io |

### 1. Run Odoo locally

```bash
docker run -d --name odoo17 \
  -p 8069:8069 -p 5432:5432 \
  -e POSTGRES_PASSWORD=odoo \
  odoo:17.0
```

Visit http://localhost:8069, create a database, note the DB name.

### 2. Expose it publicly (ngrok)

```bash
ngrok http 8069
# → https://abc123.ngrok.io  ← use this as ODOO_URL
```

Also expose the OdooPilot service:

```bash
ngrok http 8080
# → https://xyz789.ngrok.io  ← use this as TELEGRAM_WEBHOOK_URL
```

### 3. Configure your `.env`

```bash
cp .env.example .env
```

Fill in `.env`:

```env
ODOO_URL=https://abc123.ngrok.io
ODOO_DB=your_db_name
ODOO_ADMIN_USER=admin
ODOO_ADMIN_PASSWORD=admin

TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_WEBHOOK_URL=https://xyz789.ngrok.io

LLM_PROVIDER=groq          # groq has a generous free tier
GROQ_API_KEY=gsk_...

SECRET_KEY=any-random-string
DATABASE_URL=sqlite+aiosqlite:///./odoopilot.db
```

### 4. Run OdooPilot

```bash
uvicorn odoopilot.main:app --reload --port 8080
```

### 5. Link your Telegram account

Send `/link` to your bot → click the link → log in to Odoo → done.

### 6. Test a query

```
You: What tasks are assigned to me?
Bot: You have 3 open tasks: …
```

---

## Adding a new Odoo tool

The fastest contribution path. Each domain file (inventory, sales, CRM…) can always use more tools.

1. Add to the relevant file under `odoopilot/agent/tools/`
2. Subclass `BaseTool`, set `name`, `description`, `parameters` (Pydantic model)
3. Implement `async def execute(self, odoo, user_id, password, **kwargs)`
4. Read tools → return `ToolResult` directly
5. Write tools → call `await self.require_confirmation(question=..., payload=...)` before mutating
6. Register in `odoopilot/agent/tools/__init__.py`
7. Write a test in `tests/test_tools/` (mock `odoo.search_read`)

See any existing tool for the full pattern — [`odoopilot/agent/tools/project.py`](odoopilot/agent/tools/project.py) is a good example.

---

## Code guidelines

- **Linting**: `ruff` (no black, no isort separately)
- **Types**: strict `mypy` — annotate everything
- **Comments**: only the *why*, never the *what*
- **Tests**: every tool needs at least one happy-path and one not-found test
- **Providers**: no OpenAI-only code paths — test with at least two providers

## Commit format

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(tools): add update_sale_order write tool
fix(telegram): handle edited messages gracefully
docs: improve end-to-end testing guide
```

## Licensing

All contributions are LGPL-3.0-or-later. By submitting a PR you confirm you have the right to contribute under this license.

---

## Getting help

Open a [GitHub Discussion](https://github.com/arunrajiah/odoopilot/discussions) — we're friendly.

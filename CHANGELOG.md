# Changelog

All notable changes to OdooPilot are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [17.0.4.0.0] — 2026-04-23

### Added

- **`services/notifications.py`** — proactive notification service with two functions:
  - `send_task_digest(env)` — sends each linked user their overdue + today's tasks every morning
  - `send_invoice_alerts(env)` — sends users with `account.group_account_invoice` access a daily overdue invoice summary
- **Two new cron jobs** in `data/ir_cron.xml`:
  - `ir_cron_task_digest` — fires daily at 08:00 UTC
  - `ir_cron_invoice_alerts` — fires daily at 09:00 UTC
- **Two new settings toggles** (`Settings → OdooPilot → Proactive Notifications`):
  - *Daily task digest* (`odoopilot.notify_task_digest`)
  - *Overdue invoice alerts* (`odoopilot.notify_invoice_alerts`)
- Notifications section in the settings view (hidden when Telegram is disabled)
- Both notification types are opt-in (off by default); cron timing adjustable via Scheduled Actions

---

## [17.0.3.0.0] — 2026-04-22

### Added

- **`get_my_leaves`** — read pending/approved leave requests (own or team)
- **`approve_leave`** — approve a pending leave request (write, confirmation required)
- **`update_crm_stage`** — move a CRM opportunity to a different stage (write, confirmation required)
- **`create_crm_lead`** — create a new CRM opportunity (write, confirmation required)
- Human-readable inline confirmation messages (e.g. "Approve leave for John Smith?") — replaced raw JSON display
- Per-tool audit log entries — every tool call is individually logged with name, args, result, and success flag

### Changed

- Session class renamed `MailGatewayAISession` → `OdooPilotSession`
- Session TTL extended 24h → 72h
- Session message history cap raised 40 → 60 messages (30 exchanges)
- Write tool responses prefixed with ✅ for clarity

---

## [17.0.2.0.0] — 2026-04-22

### Architecture pivot — all logic now lives inside the Odoo addon

The project has been restructured from a two-component system (FastAPI service + thin Odoo addon) into a single self-contained Odoo addon. Users no longer need to host or configure any external service.

### Added

- Telegram webhook handler inside Odoo HTTP controllers
- LLM client supporting Anthropic, OpenAI, and Groq via raw `requests` (no SDKs)
- Multi-turn agent loop with tool-use and per-session conversation history
- 7 read tools: project tasks, sale orders, CRM leads, inventory, invoices, purchase orders, employees
- 2 write tools (mark task done, confirm sale order) with inline Yes/No confirmation
- Telegram client helpers: send message, send confirmation keyboard, answer callback query, set webhook
- Session model (`odoopilot.session`) with 24-hour garbage collection via `ir.cron`
- Full settings page: bot token, webhook secret, LLM provider/key/model, Register Webhook button, Test Connection button
- Magic link identity flow: `/link` → one-time token → `/odoopilot/link/start`
- Standalone link success/error pages (no `website` module dependency)
- Audit log for every tool call

### Changed

- Module technical name: `mail_gateway_ai` → `odoopilot`
- App Store URL: `/apps/modules/17.0/mail_gateway_ai` → `/apps/modules/17.0/odoopilot`
- CI simplified to ruff lint/format + XML well-formed check (removed FastAPI-specific mypy/pytest/build steps)

### Removed

- FastAPI service, Dockerfile, `pyproject.toml`, Docker Compose examples
- Fly.io deployment (`fly.toml`)
- External service URL setting
- All `mail_gateway_ai` identifiers

---

## [17.0.1.0.0] — 2026-04-01

### Added

- Initial scaffold: bot configuration settings (`service_url`, channel toggles), user identity model, audit log model
- User linking flow with one-time token generation
- `ir.model.access.csv` for base access control
- CI workflow: ruff, mypy, pytest, hatchling build

---

## Roadmap

| Version | Target | Description |
|---------|--------|-------------|
| **17.0.3.0.0** | ✅ Released | New write tools · get_my_leaves · 72h session TTL · human-readable confirmations · per-tool audit log |
| **17.0.4.0.0** | ✅ Released | Proactive notifications — daily task digest (08:00 UTC) · overdue invoice alerts (09:00 UTC) |
| **17.0.5.0.0** | Q3 2026 | WhatsApp Cloud API channel |
| **17.0.6.0.0** | Q4 2026 | Multi-language support · per-user language preference |
| **18.0.1.0.0** | Q4 2026 | Odoo 18 port · OCA submission |

# Changelog

## 17.0.3.0.0 (2026-04-22)

### Added

- **`get_my_leaves`** read tool — list own or team leave requests filtered by state
- **`approve_leave`** write tool — approve a pending leave request (with confirmation)
- **`update_crm_stage`** write tool — move a CRM opportunity to a different pipeline stage (with confirmation)
- **`create_crm_lead`** write tool — create a new CRM opportunity with optional partner, revenue, and stage (with confirmation)
- `_fmt_confirmation()` — human-readable confirmation prompts (replaces raw JSON display)
- Per-tool audit log entries — every tool call is now logged individually, not just the top-level chat turn
- `clear_pending()` helper on session model

### Changed

- Session class renamed from `MailGatewayAISession` → `OdooPilotSession`
- Session TTL extended from 24h → 72h (`_SESSION_TTL_HOURS`)
- Session message cap increased from 40 → 60 (`_MAX_MESSAGES`, 30 exchanges)
- `json` import moved to module level in session model
- Write tools now return `✅` prefixed success messages

---

## 17.0.2.0.0 (2026-04-22)

### Changed — Architecture pivot

Complete rewrite. The addon now contains **all** bot logic — no external FastAPI service required.

### Added

- **Telegram webhook controller** (`/odoopilot/webhook/telegram`) — receives and validates Telegram updates inside Odoo's HTTP layer; background thread handles processing to respect Telegram's 5-second timeout
- **LLM service** (`services/llm.py`) — raw-`requests` client supporting Anthropic, OpenAI, and Groq; no third-party SDKs required
- **Agent loop** (`services/agent.py`) — multi-turn tool-use loop with per-session conversation history; write tools gated behind inline Yes/No confirmation
- **ORM tools** (`services/tools.py`) — 7 read tools (tasks, sale orders, CRM leads, stock, invoices, purchase orders, employees) and 2 write tools (mark task done, confirm sale order)
- **Telegram client** (`services/telegram.py`) — `send_message`, `send_confirmation` (inline keyboard), `answer_callback_query`, `set_webhook`
- **Session model** (`odoopilot.session`) — per-chat conversation history with 24-hour TTL garbage collection via `ir.cron`
- **Settings** — bot token, webhook secret, LLM provider/key/model; **Register Webhook** and **Test Connection** action buttons
- **Identity linking** — `/link` command generates a one-time token; magic link flow at `/odoopilot/link/start`
- **Standalone link pages** — success/error templates with no dependency on the `website` module

### Removed

- Dependency on external OdooPilot FastAPI service
- `service_url` field from identity model
- All references to `mail_gateway_ai` (former module technical name)

---

## 17.0.1.0.0 (2026-04-01)

### Added

- Initial scaffold: bot configuration settings (`service_url`, channel toggles), user identity model, audit log model
- User linking flow with one-time token generation
- `ir.model.access.csv` for base access control

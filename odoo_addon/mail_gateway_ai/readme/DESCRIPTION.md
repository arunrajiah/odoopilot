**AI Mail Gateway** bridges Odoo Community with external messaging apps (Telegram first, WhatsApp in v0.3) via an AI agent. It is the companion Odoo addon for the [OdooPilot](https://github.com/your-org/odoopilot) standalone service.

## Features

- **User linking** — Generate one-time tokens so employees can link their Telegram account to their Odoo identity in one click.
- **Bot configuration** — Set the OdooPilot service URL and enable/disable channels from Odoo Settings.
- **Audit log viewer** — See every tool call made on behalf of each user, with timestamps and results.
- **Per-user preferences** — (planned v0.2) per-user language and notification preferences.

## Architecture

This addon does **not** contain the AI logic. That lives in the standalone `odoopilot` Python service (FastAPI + python-telegram-bot). This addon provides:

1. The admin UI inside Odoo for bot configuration.
2. The user-linking flow (token generation + Odoo-side identity storage).
3. An audit log model and viewer.

See the [OdooPilot documentation](https://github.com/your-org/odoopilot/blob/main/docs/architecture.md) for the full architecture.

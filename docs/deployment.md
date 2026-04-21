# Deployment

## Docker Compose (recommended)

The fastest way to run OdooPilot alongside Odoo:

```bash
git clone https://github.com/arunrajiah/odoopilot.git
cd odoopilot/examples
cp .env.example .env
# Edit .env
docker-compose up -d
```

See [examples/docker-compose.yml](../examples/docker-compose.yml) for the full spec.

## Bare metal

```bash
pip install odoopilot
cp .env.example .env
# Edit .env
odoopilot migrate     # run Alembic migrations
odoopilot serve       # start the FastAPI server
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ODOO_URL` | ✅ | Base URL of your Odoo instance, e.g. `https://odoo.example.com` |
| `ODOO_DB` | ✅ | Odoo database name |
| `ODOO_ADMIN_USER` | ✅ | Odoo admin username (for token generation only) |
| `ODOO_ADMIN_PASSWORD` | ✅ | Odoo admin password |
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_WEBHOOK_URL` | ✅ | Public HTTPS URL where Telegram sends updates |
| `LLM_PROVIDER` | ✅ | `openai`, `anthropic`, `ollama`, or `groq` |
| `OPENAI_API_KEY` | if openai | OpenAI API key |
| `ANTHROPIC_API_KEY` | if anthropic | Anthropic API key |
| `OLLAMA_BASE_URL` | if ollama | e.g. `http://localhost:11434` |
| `GROQ_API_KEY` | if groq | Groq API key |
| `DATABASE_URL` | | SQLAlchemy URL. Defaults to `sqlite:///./odoopilot.db` |
| `SECRET_KEY` | | Random secret for token signing. Auto-generated if unset. |
| `LOG_LEVEL` | | `DEBUG`, `INFO`, `WARNING`. Defaults to `INFO`. |

## Webhook setup

OdooPilot uses Telegram's webhook mode (not polling). The `TELEGRAM_WEBHOOK_URL` must be reachable by Telegram's servers over HTTPS on port 443, 80, 88, or 8443.

For local development, use [ngrok](https://ngrok.com/):

```bash
ngrok http 8000
# Copy the https URL to TELEGRAM_WEBHOOK_URL in .env
```

## Adding the companion Odoo addon

1. Copy `mail_gateway_ai/` into your Odoo addons path
2. Update your Odoo addon list and install `mail_gateway_ai`
3. Go to **Settings → OdooPilot** to configure the bot URL and manage user links

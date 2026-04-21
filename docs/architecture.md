# Architecture

OdooPilot is built as four clean, independently testable layers stacked vertically.

## Layer 1 — Channel adapters

**Location:** `odoopilot/channels/`

Responsible for all messaging-platform I/O. Each adapter implements the abstract `Channel` interface:

- `receive_message(update)` — parse an incoming platform event into a `ChannelMessage`
- `send_message(chat_id, text)` — send a plain text reply
- `send_confirmation_prompt(chat_id, question, payload)` — send an inline keyboard/button prompt for write confirmations

**Telegram** (`channels/telegram.py`) uses `python-telegram-bot` v20+ in async webhook mode, mounted inside the FastAPI app.

**WhatsApp** (`channels/whatsapp.py`) is a stub in v1. The interface is fully defined so adding the Cloud API implementation in v0.3 requires no changes to any other layer.

## Layer 2 — Identity & permission layer

**Location:** `odoopilot/identity/`

Maps `(channel_name, chat_id)` pairs to Odoo `res.users` records. All Odoo API calls are made with the **linked user's credentials**, so Odoo's built-in record rules and group membership do the permission work — OdooPilot does not reimplement access control.

The linking flow:
1. User sends `/link` to the bot
2. Bot sends back a one-time token URL pointing to the companion Odoo addon
3. User clicks the link while logged into Odoo — the addon writes `(channel, chat_id, user_id)` to its model
4. Subsequent messages from that chat ID are executed as that Odoo user

## Layer 3 — Agent core

**Location:** `odoopilot/agent/`

The agent loop (`agent/core.py`):

1. Receives a `ChannelMessage` from the channel adapter
2. Looks up the linked Odoo user (or sends a link prompt)
3. Builds a system prompt with user context
4. Calls the configured `LLMProvider.chat()` with the message history and tool schemas
5. If the LLM returns a tool call, dispatches to the tool registry
6. Write tools pause here — they call `send_confirmation_prompt()` and wait for the user's button tap
7. Logs the tool call to the audit log
8. Returns the final text response to the channel adapter

### LLM providers (`agent/providers/`)

Each provider implements `BaseLLMProvider`:

```python
async def chat(
    self,
    messages: list[Message],
    tools: list[ToolSchema],
) -> LLMResponse:
    ...
```

The internal `ToolCall` and `ToolResult` schemas normalise differences between OpenAI function-calling, Anthropic tool use, and Ollama's tool schema.

### Tools (`agent/tools/`)

Each tool subclasses `BaseTool`:

```python
class FindProduct(BaseTool):
    name = "find_product"
    description = "..."
    parameters = FindProductInput  # Pydantic model

    async def execute(self, odoo: OdooClient, user_id: int, **kwargs) -> ToolResult:
        ...
```

Read tools return a result immediately. Write tools call `self.require_confirmation()` which raises `ConfirmationRequired` — the agent core catches this and issues the inline button prompt.

## Layer 4 — Odoo adapter

**Location:** `odoopilot/odoo/`

A thin async JSON-RPC client that wraps Odoo's `/web/dataset/call_kw` endpoint. All calls are authenticated per-user (session-less, using `xmlrpc`-style `uid` + `password` or API key). Typed Pydantic wrappers in `odoo/models.py` surface common Odoo record shapes.

## Storage

SQLAlchemy 2.x with Alembic migrations. SQLite by default (zero-config for self-hosters); Postgres via `DATABASE_URL` env var.

Tables:
- `channel_identity` — `(channel, chat_id)` → `odoo_user_id` mapping
- `audit_log` — every tool call with user, tool, args, result, timestamp
- `pending_confirmation` — write operations awaiting user confirmation

## Companion Odoo addon (`mail_gateway_ai`)

An OCA-style Odoo module providing:
- Admin UI for bot configuration (URL, token, LLM provider)
- User linking screen (generates one-time tokens)
- Audit log viewer inside Odoo
- Optional: `res.users` extension for per-user OdooPilot preferences

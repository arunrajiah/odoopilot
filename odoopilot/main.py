from __future__ import annotations

import json
import logging
import secrets

from fastapi import FastAPI, HTTPException, Request, Response, status

from odoopilot.agent.core import AgentCore
from odoopilot.agent.providers import build_llm_provider
from odoopilot.audit.log import AuditLogger
from odoopilot.channels.base import Channel, ChannelMessage
from odoopilot.channels.telegram import TelegramChannel
from odoopilot.config import get_settings
from odoopilot.identity.linking import IdentityStore
from odoopilot.odoo.client import OdooClient
from odoopilot.storage.db import close_db, create_tables, get_session_factory, init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App construction
# ---------------------------------------------------------------------------

app = FastAPI(title="OdooPilot", version="0.1.0")

# Module-level singletons initialised in lifespan
_telegram: TelegramChannel | None = None
_odoo: OdooClient | None = None
_agent: AgentCore | None = None
_identity_store: IdentityStore | None = None


@app.on_event("startup")
async def startup() -> None:
    global _telegram, _odoo, _agent, _identity_store

    settings = get_settings()

    logging.basicConfig(level=settings.log_level)

    # Storage
    init_db(settings.database_url)
    await create_tables()
    session_factory = get_session_factory()

    # Odoo client
    _odoo = OdooClient(url=settings.odoo_url, db=settings.odoo_db)

    # Audit + identity
    audit = AuditLogger(session_factory)
    _identity_store = IdentityStore(
        session_factory=session_factory,
        secret_key=settings.secret_key.get_secret_value(),
    )

    # LLM provider
    llm = build_llm_provider(settings)

    # Agent core
    _agent = AgentCore(llm=llm, odoo=_odoo, audit=audit)

    # Telegram channel
    _telegram = TelegramChannel(token=settings.telegram_bot_token.get_secret_value())
    _telegram.set_message_handler(_handle_message)
    _telegram.set_confirmation_handler(_handle_confirmation)

    await _telegram.get_ptb_application().initialize()

    # Register webhook with Telegram
    bot = _telegram.get_ptb_application().bot
    webhook_url = f"{settings.telegram_webhook_url.rstrip('/')}/webhook/telegram"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.telegram_webhook_secret.get_secret_value()
        if settings.telegram_webhook_secret
        else None,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Telegram webhook registered at %s", webhook_url)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _telegram:
        await _telegram.get_ptb_application().shutdown()
    if _odoo:
        await _odoo.close()
    await close_db()


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> Response:
    settings = get_settings()
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secrets.compare_digest(secret, settings.telegram_webhook_secret.get_secret_value()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret"
            )

    body = await request.body()
    if _telegram:
        await _telegram.process_update(body)
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "odoopilot"}


# ---------------------------------------------------------------------------
# Linking endpoint (called from companion Odoo addon)
# ---------------------------------------------------------------------------


@app.get("/link/{token}")
async def link_account(token: str) -> dict:
    """Validates a linking token and returns the channel/chat_id to the Odoo addon."""
    if not _identity_store:
        raise HTTPException(status_code=503, detail="Service not ready")
    result = await _identity_store.consume_linking_token(token)
    if result is None:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    channel, chat_id = result
    return {"channel": channel, "chat_id": chat_id}


@app.post("/link/complete")
async def complete_link(request: Request) -> dict:
    """Called by the Odoo addon after successfully validating the token."""
    if not _identity_store:
        raise HTTPException(status_code=503, detail="Service not ready")
    body = await request.json()
    await _identity_store.link_user(
        channel=body["channel"],
        chat_id=body["chat_id"],
        odoo_user_id=body["odoo_user_id"],
        odoo_username=body["odoo_username"],
        odoo_password=body["odoo_password"],
        display_name=body.get("display_name", ""),
    )
    return {"status": "linked"}


# ---------------------------------------------------------------------------
# Message handlers (called by channel adapters)
# ---------------------------------------------------------------------------


async def _handle_message(msg: ChannelMessage, channel: Channel) -> None:
    if not _agent or not _identity_store:
        await channel.send_message(
            msg.chat_id, "Service is starting up — please try again in a moment."
        )
        return

    if msg.text.strip() == "/link":
        token = await _identity_store.create_linking_token(msg.channel, msg.chat_id)
        settings = get_settings()
        link_url = f"{settings.odoo_url}/web#action=mail_gateway_ai.action_link&token={token}"
        await channel.send_message(
            msg.chat_id,
            f"Click this link to connect your Odoo account (expires in 1 hour):\n{link_url}",
        )
        return

    identity = await _identity_store.get_identity(msg.channel, msg.chat_id)
    if not identity:
        await channel.send_message(
            msg.chat_id,
            "Your Odoo account is not linked yet. Use /link to connect it.",
        )
        return

    await _agent.handle_message(msg=msg, channel=channel, identity=identity)


async def _handle_confirmation(msg: ChannelMessage, channel: Channel) -> None:
    if not _agent or not _identity_store or not msg.confirmation_payload:
        return

    identity = await _identity_store.get_identity(msg.channel, msg.chat_id)
    if not identity:
        await channel.send_message(
            msg.chat_id, "Could not verify your identity. Please re-link with /link."
        )
        return

    # Payload format: "tool_name:json_args"
    try:
        tool_name, args_json = msg.confirmation_payload.split(":", 1)
        tool_args = json.loads(args_json) if args_json else {}
    except (ValueError, json.JSONDecodeError):
        # Simple payload with no args (e.g. "confirm_sale_order:42")
        parts = msg.confirmation_payload.split(":")
        tool_name = parts[0]
        tool_args = {"id": int(parts[1])} if len(parts) > 1 else {}

    await _agent.handle_confirmation(
        msg=msg,
        channel=channel,
        identity=identity,
        pending_tool_name=tool_name,
        pending_tool_args=tool_args,
    )

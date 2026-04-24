import hmac
import json
import logging
import secrets
import threading
import time

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class OdooPilotController(http.Controller):
    # ------------------------------------------------------------------
    # Telegram webhook
    # ------------------------------------------------------------------

    @http.route(
        "/odoopilot/webhook/telegram",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def telegram_webhook(self, **kwargs):
        """Receive Telegram updates. Validate secret, then process async."""
        # Validate webhook secret if configured
        cfg = request.env["ir.config_parameter"].sudo()
        secret = cfg.get_param("odoopilot.telegram_webhook_secret")
        if secret:
            received = request.httprequest.headers.get(
                "X-Telegram-Bot-Api-Secret-Token", ""
            )
            if not hmac.compare_digest(received, secret):
                return request.make_response("Forbidden", status=403)

        enabled = cfg.get_param("odoopilot.telegram_enabled")
        if not enabled:
            return request.make_response("", status=200)

        try:
            body = request.httprequest.get_data(as_text=True)
            update = json.loads(body)
        except Exception:
            return request.make_response("Bad request", status=400)

        # Grab DB name and registry for use in background thread
        db = request.env.cr.dbname
        registry = request.env.registry

        thread = threading.Thread(
            target=self._process_update_async,
            args=(db, registry, update),
            daemon=True,
        )
        thread.start()

        return request.make_response("", status=200)

    def _process_update_async(self, db, registry, update):
        """Process the Telegram update in a background thread with its own cursor."""
        import odoo

        try:
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                self._dispatch_update(env, update)
        except Exception:
            _logger.exception("OdooPilot: unhandled error processing Telegram update")

    def _dispatch_update(self, env, update):
        from ..services.telegram import TelegramClient
        from ..services.agent import OdooPilotAgent

        cfg = env["ir.config_parameter"].sudo()
        token = cfg.get_param("odoopilot.telegram_bot_token")
        if not token:
            return

        tg = TelegramClient(token)

        # Handle callback queries (inline keyboard button presses)
        if "callback_query" in update:
            cq = update["callback_query"]
            chat_id = str(cq["message"]["chat"]["id"])
            payload = cq.get("data", "")
            tg.answer_callback_query(cq["id"])
            self._handle_confirmation(env, tg, chat_id, payload)
            return

        # Handle regular messages
        message = update.get("message")
        if not message or "text" not in message:
            return

        chat_id = str(message["chat"]["id"])
        text = message["text"].strip()

        # /link command — generate and send a linking URL
        if text.startswith("/link"):
            self._handle_link_command(env, tg, chat_id)
            return

        # /start command
        if text.startswith("/start"):
            tg.send_message(
                chat_id,
                "Hi! I'm OdooPilot - your Odoo AI assistant.\n\n"
                "Use /link to connect your Odoo account, then ask me anything about your data.",
            )
            return

        # Regular message — check identity and route to agent
        identity = env["odoopilot.identity"].search(
            [
                ("channel", "=", "telegram"),
                ("chat_id", "=", chat_id),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            tg.send_message(
                chat_id,
                "Your Odoo account is not linked yet. Use /link to connect it.",
            )
            return

        # Run agent as the linked user
        user_env = env(user=identity.user_id.id)
        agent = OdooPilotAgent(user_env, tg)
        agent.handle_message(chat_id, text)

    def _handle_link_command(self, env, tg, chat_id):
        """Generate a one-time linking token and send the link to the user."""
        cfg = env["ir.config_parameter"].sudo()
        base_url = cfg.get_param("web.base.url", "").rstrip("/")
        if not base_url:
            tg.send_message(
                chat_id,
                "⚠️ OdooPilot is not fully configured: web.base.url is missing. "
                "Ask your Odoo admin to set it in Settings → Technical → System Parameters.",
            )
            return

        # Clean up any expired tokens for this chat_id before issuing a new one
        self._cleanup_expired_link_tokens(env)

        token = secrets.token_urlsafe(32)
        expiry = int(time.time()) + 3600
        cfg.set_param(
            f"odoopilot.link_token.{token}",
            json.dumps({"channel": "telegram", "chat_id": chat_id, "exp": expiry}),
        )
        link_url = f"{base_url}/odoopilot/link/start?token={token}"
        tg.send_message(
            chat_id,
            f"Click the link below to connect your Odoo account (expires in 1 hour):\n\n{link_url}",
        )

    def _cleanup_expired_link_tokens(self, env):
        """Remove all expired OdooPilot link tokens from ir.config_parameter."""
        now = int(time.time())
        params = (
            env["ir.config_parameter"]
            .sudo()
            .search([("key", "like", "odoopilot.link_token.")])
        )
        for param in params:
            try:
                data = json.loads(param.value or "{}")
                if not data or now > data.get("exp", 0):
                    param.unlink()
            except Exception:
                param.unlink()

    def _handle_confirmation(self, env, tg, chat_id, payload):
        """Handle yes/no confirmation from inline keyboard."""
        from ..services.agent import OdooPilotAgent

        identity = env["odoopilot.identity"].search(
            [
                ("channel", "=", "telegram"),
                ("chat_id", "=", chat_id),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            return

        session = env["odoopilot.session"].search(
            [("channel", "=", "telegram"), ("chat_id", "=", chat_id)], limit=1
        )

        if payload == "confirm:no":
            tg.send_message(chat_id, "Cancelled.")
            if session:
                session.clear_pending()
                # Record decline in history so LLM has context next turn
                session.append_message("user", "(I declined the action)")
                session.append_message(
                    "assistant", "Understood, the action was cancelled."
                )
            return

        if payload.startswith("confirm:yes"):
            if not session or not session.pending_tool:
                tg.send_message(chat_id, "Nothing to confirm.")
                return
            tool_name = session.pending_tool
            args = json.loads(session.pending_args or "{}")
            session.clear_pending()  # Clear before executing to avoid double-run on retry
            user_env = env(user=identity.user_id.id)
            agent = OdooPilotAgent(user_env, tg)
            agent.execute_confirmed(chat_id, tool_name, args)

    # ------------------------------------------------------------------
    # Account linking pages
    # ------------------------------------------------------------------

    @http.route("/odoopilot/link/start", type="http", auth="user")
    def link_start(self, token=None, **kwargs):
        """User lands here after clicking the link in Telegram. They must be logged in."""
        if not token:
            return request.render("odoopilot.link_error", {"error": "Missing token."})

        cfg = request.env["ir.config_parameter"].sudo()
        raw = cfg.get_param(f"odoopilot.link_token.{token}")
        if not raw:
            return request.render(
                "odoopilot.link_error", {"error": "Invalid or expired link."}
            )

        try:
            data = json.loads(raw)
        except Exception:
            return request.render("odoopilot.link_error", {"error": "Corrupt token."})

        if int(time.time()) > data.get("exp", 0):
            cfg.search([("key", "=", f"odoopilot.link_token.{token}")]).unlink()
            return request.render(
                "odoopilot.link_error",
                {"error": "This link has expired. Use /link again."},
            )

        channel = data.get("channel", "telegram")
        chat_id = data.get("chat_id", "")

        # Check if already linked
        existing = request.env["odoopilot.identity"].search(
            [("channel", "=", channel), ("chat_id", "=", chat_id)], limit=1
        )
        if existing:
            existing.write(
                {
                    "user_id": request.env.user.id,
                    "linked_at": fields.Datetime.now(),
                    "active": True,
                }
            )
        else:
            request.env["odoopilot.identity"].create(
                {
                    "user_id": request.env.user.id,
                    "channel": channel,
                    "chat_id": chat_id,
                    "linked_at": fields.Datetime.now(),
                }
            )

        # Consume token
        cfg.search([("key", "=", f"odoopilot.link_token.{token}")]).unlink()

        # Notify user on Telegram
        bot_token = cfg.get_param("odoopilot.telegram_bot_token")
        if bot_token and channel == "telegram":
            from ..services.telegram import TelegramClient

            tg = TelegramClient(bot_token)
            tg.send_message(
                chat_id,
                f"Account linked! Welcome, {request.env.user.name}. You can now ask me anything about your Odoo data.",
            )

        return request.render("odoopilot.link_success", {"user": request.env.user})

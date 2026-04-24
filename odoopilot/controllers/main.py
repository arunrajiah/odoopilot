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
    # WhatsApp webhook
    # ------------------------------------------------------------------

    @http.route(
        "/odoopilot/webhook/whatsapp",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
    )
    def whatsapp_verify(self, **kwargs):
        """WhatsApp Cloud API webhook verification challenge (hub.challenge handshake)."""
        mode = request.params.get("hub.mode")
        token = request.params.get("hub.verify_token")
        challenge = request.params.get("hub.challenge", "")

        cfg = request.env["ir.config_parameter"].sudo()
        expected = cfg.get_param("odoopilot.whatsapp_verify_token")

        if mode == "subscribe" and expected and token == expected:
            return request.make_response(challenge, status=200)
        return request.make_response("Forbidden", status=403)

    @http.route(
        "/odoopilot/webhook/whatsapp",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def whatsapp_webhook(self, **kwargs):
        """Receive WhatsApp Cloud API updates and dispatch asynchronously."""
        cfg = request.env["ir.config_parameter"].sudo()
        if not cfg.get_param("odoopilot.whatsapp_enabled"):
            return request.make_response("", status=200)

        try:
            body = request.httprequest.get_data(as_text=True)
            update = json.loads(body)
        except Exception:
            return request.make_response("Bad request", status=400)

        db = request.env.cr.dbname
        registry = request.env.registry

        thread = threading.Thread(
            target=self._process_whatsapp_async,
            args=(db, registry, update),
            daemon=True,
        )
        thread.start()
        return request.make_response("", status=200)

    def _process_whatsapp_async(self, db, registry, update):
        """Process a WhatsApp update in a background thread."""
        import odoo

        try:
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                self._dispatch_whatsapp(env, update)
        except Exception:
            _logger.exception("OdooPilot: unhandled error processing WhatsApp update")

    def _dispatch_whatsapp(self, env, update):
        from ..services.whatsapp import WhatsAppClient

        cfg = env["ir.config_parameter"].sudo()
        phone_number_id = cfg.get_param("odoopilot.whatsapp_phone_number_id")
        access_token = cfg.get_param("odoopilot.whatsapp_access_token")
        if not phone_number_id or not access_token:
            return

        wa = WhatsAppClient(phone_number_id, access_token)

        # Walk through entry → changes → value → messages
        for entry in update.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if change.get("field") != "messages":
                    continue

                for msg in value.get("messages", []):
                    from_number = msg.get("from", "")
                    msg_type = msg.get("type", "")
                    msg_id = msg.get("id", "")

                    # Mark as read
                    if msg_id:
                        wa.mark_read(msg_id)

                    # Interactive button reply (confirmation)
                    if msg_type == "interactive":
                        reply = msg.get("interactive", {}).get("button_reply", {})
                        payload = reply.get("id", "")
                        if payload.startswith("confirm:"):
                            self._handle_whatsapp_confirmation(
                                env, wa, from_number, payload
                            )
                        continue

                    # Text message
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "").strip()
                        if not text:
                            continue
                        self._handle_whatsapp_message(env, wa, from_number, text)

    def _handle_whatsapp_message(self, env, wa, from_number, text):
        from ..services.agent import OdooPilotAgent
        import secrets as _secrets

        if text.startswith("/link"):
            token = _secrets.token_urlsafe(32)
            expiry = int(time.time()) + 3600
            env["ir.config_parameter"].sudo().set_param(
                f"odoopilot.link_token.{token}",
                json.dumps(
                    {"channel": "whatsapp", "chat_id": from_number, "exp": expiry}
                ),
            )
            base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            link_url = f"{base_url.rstrip('/')}/odoopilot/link/start?token={token}"
            wa.send_message(
                from_number,
                f"Click the link to connect your Odoo account (expires in 1 hour):\n\n{link_url}",
            )
            return

        if text.startswith("/start"):
            wa.send_message(
                from_number,
                "Hi! I'm OdooPilot — your Odoo AI assistant.\n\nUse /link to connect your Odoo account, then ask me anything.",
            )
            return

        identity = env["odoopilot.identity"].search(
            [
                ("channel", "=", "whatsapp"),
                ("chat_id", "=", from_number),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            wa.send_message(
                from_number,
                "Your Odoo account is not linked yet. Send /link to connect it.",
            )
            return

        user_env = env(user=identity.user_id.id)
        agent = OdooPilotAgent(user_env, wa)
        agent.handle_message(from_number, text)

    def _handle_whatsapp_confirmation(self, env, wa, from_number, payload):
        from ..services.agent import OdooPilotAgent

        identity = env["odoopilot.identity"].search(
            [
                ("channel", "=", "whatsapp"),
                ("chat_id", "=", from_number),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            return

        session = env["odoopilot.session"].search(
            [("channel", "=", "whatsapp"), ("chat_id", "=", from_number)], limit=1
        )

        if payload == "confirm:no":
            wa.send_message(from_number, "Cancelled.")
            if session:
                session.clear_pending()
                session.append_message("user", "(I declined the action)")
                session.append_message(
                    "assistant", "Understood, the action was cancelled."
                )
            return

        if payload.startswith("confirm:yes"):
            if not session or not session.pending_tool:
                wa.send_message(from_number, "Nothing to confirm.")
                return
            tool_name = session.pending_tool
            args = json.loads(session.pending_args or "{}")
            session.clear_pending()
            user_env = env(user=identity.user_id.id)
            agent = OdooPilotAgent(user_env, wa)
            agent.execute_confirmed(from_number, tool_name, args)

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

        # Notify user on the originating channel
        welcome = f"Account linked! Welcome, {request.env.user.name}. You can now ask me anything about your Odoo data."
        if channel == "telegram":
            bot_token = cfg.get_param("odoopilot.telegram_bot_token")
            if bot_token:
                from ..services.telegram import TelegramClient

                TelegramClient(bot_token).send_message(chat_id, welcome)
        elif channel == "whatsapp":
            phone_number_id = cfg.get_param("odoopilot.whatsapp_phone_number_id")
            access_token = cfg.get_param("odoopilot.whatsapp_access_token")
            if phone_number_id and access_token:
                from ..services.whatsapp import WhatsAppClient

                WhatsAppClient(phone_number_id, access_token).send_message(
                    chat_id, welcome
                )

        return request.render("odoopilot.link_success", {"user": request.env.user})

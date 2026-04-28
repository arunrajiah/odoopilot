import hmac
import json
import logging

from odoo import fields, http
from odoo.http import request

from ..services import throttle

_logger = logging.getLogger(__name__)


def _telegram_chat_id(update: dict) -> str:
    """Extract the originating chat_id from a Telegram update for rate limiting."""
    if "callback_query" in update:
        return str(
            update["callback_query"].get("message", {}).get("chat", {}).get("id", "")
        )
    return str(update.get("message", {}).get("chat", {}).get("id", ""))


def _whatsapp_chat_id(update: dict) -> str:
    """Extract the first ``from`` number out of a WhatsApp update."""
    for entry in update.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            for msg in change.get("value", {}).get("messages", []) or []:
                if msg.get("from"):
                    return str(msg["from"])
    return ""


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
        """Receive Telegram updates. Validate secret, then process async.

        Security: the webhook secret is **mandatory**. If no secret is
        configured the webhook refuses every request (HTTP 403). This forces
        operators to register the webhook through the Settings action, which
        auto-generates a 32-byte secret if none is set.
        """
        cfg = request.env["ir.config_parameter"].sudo()

        if not cfg.get_param("odoopilot.telegram_enabled"):
            return request.make_response("", status=200)

        secret = cfg.get_param("odoopilot.telegram_webhook_secret") or ""
        received = request.httprequest.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if not secret or not hmac.compare_digest(received, secret):
            _logger.warning(
                "OdooPilot: rejecting Telegram webhook with bad/missing "
                "X-Telegram-Bot-Api-Secret-Token header"
            )
            return request.make_response("Forbidden", status=403)

        try:
            body = request.httprequest.get_data(as_text=True)
            update = json.loads(body)
        except Exception:
            return request.make_response("Bad request", status=400)

        # Per-chat rate limit: protects against cost amplification (paid LLM
        # calls per message) and against a flood from a single linked user.
        # Drop silently with 200 so Telegram doesn't retry-storm us.
        chat_id = _telegram_chat_id(update)
        if chat_id and not throttle.allow(request.env, "telegram", chat_id):
            return request.make_response("", status=200)

        # Idempotency: Telegram retries on 5xx and timeouts. The unique
        # ``update_id`` lets us drop redeliveries — without this, a
        # redelivered confirmation click could re-execute the same write.
        update_id = update.get("update_id")
        if update_id is not None:
            seen_model = request.env["odoopilot.delivery.seen"].sudo()
            if not seen_model.mark_or_drop("telegram", str(update_id)):
                return request.make_response("", status=200)

        # Grab DB name and registry for use in background thread
        db = request.env.cr.dbname
        registry = request.env.registry

        # Bounded worker pool replaces unbounded daemon threads. If saturated
        # we drop the update — Telegram's retry would just compound the load.
        throttle.submit(request.env, self._process_update_async, db, registry, update)

        return request.make_response("", status=200)

    def _process_update_async(self, db, registry, update):
        """Process the Telegram update in a background thread with its own cursor."""
        import odoo

        try:
            with registry.cursor() as cr:
                # Bootstrap environment runs as SUPERUSER_ID for the unavoidable
                # privileged lookups (ir.config_parameter, odoopilot.identity,
                # odoopilot.session, odoopilot.link.token). It MUST NOT be passed
                # into agent.py code paths that touch business data — those re-
                # scope to the linked user via ``sudo_env(user=identity.user_id.id)``.
                sudo_env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                self._dispatch_update(sudo_env, update)
        except Exception:
            _logger.exception("OdooPilot: unhandled error processing Telegram update")

    def _dispatch_update(self, sudo_env, update):
        """Route an inbound Telegram update.

        ``sudo_env`` is the bootstrap superuser environment used ONLY for the
        privileged lookups needed to authenticate the chat (config params,
        identity, session, link token). Any work that touches business data
        — agent loop, tool execution, audit writes — must run in a user-
        scoped environment created from
        ``sudo_env(user=identity.user_id.id)``. This naming convention is a
        defence-in-depth measure: a future contributor adding a new code
        path is much less likely to forget to re-scope when the parameter
        is called ``sudo_env`` rather than ``env``.
        """
        from ..services.telegram import TelegramClient
        from ..services.agent import OdooPilotAgent

        cfg = sudo_env["ir.config_parameter"].sudo()
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
            self._handle_confirmation(sudo_env, tg, chat_id, payload)
            return

        # Handle regular messages
        message = update.get("message")
        if not message or "text" not in message:
            return

        chat_id = str(message["chat"]["id"])
        text = message["text"].strip()

        # /link command — generate and send a linking URL
        if text.startswith("/link"):
            self._handle_link_command(sudo_env, tg, chat_id)
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
        identity = sudo_env["odoopilot.identity"].search(
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

        # /language command — set or show per-user language preference
        if text.startswith("/language"):
            self._handle_language_command(sudo_env, tg, chat_id, text, identity)
            return

        # Re-scope to the linked Odoo user for everything that touches
        # business data. Tools, agent loop, audit writes — all run with
        # this user's record-rule permissions, never as superuser.
        user_env = sudo_env(user=identity.user_id.id)
        agent = OdooPilotAgent(user_env, tg, channel="telegram")
        agent.handle_message(chat_id, text)

    def _handle_link_command(self, sudo_env, tg, chat_id):
        """Generate a one-time linking token and send the link to the user.

        Runs in ``sudo_env`` because at this point we don't yet know which
        Odoo user the chat belongs to — the whole purpose of the link flow
        is to discover that. The token row itself is issued via ``sudo()``.
        """
        cfg = sudo_env["ir.config_parameter"].sudo()
        base_url = cfg.get_param("web.base.url", "").rstrip("/")
        if not base_url:
            tg.send_message(
                chat_id,
                "⚠️ OdooPilot is not fully configured: web.base.url is missing. "
                "Ask your Odoo admin to set it in Settings → Technical → System Parameters.",
            )
            return

        # The token's SHA-256 digest is what's stored; the raw token only
        # leaves the server as the URL we send back to this user.
        raw = sudo_env["odoopilot.link.token"].sudo().issue("telegram", chat_id)
        link_url = f"{base_url}/odoopilot/link/start?token={raw}"
        tg.send_message(
            chat_id,
            f"Click the link below to connect your Odoo account "
            f"(expires in 1 hour, single use):\n\n{link_url}",
        )

    def _handle_language_command(self, sudo_env, client, chat_id, text, identity):
        """Handle /language command — show or set the per-user language preference."""
        from ..models.odoopilot_identity import LANGUAGE_CHOICES

        parts = text.strip().split(None, 1)
        if len(parts) == 1:
            # /language with no argument — show current setting
            current = identity.language or ""
            choices_map = dict(LANGUAGE_CHOICES)
            current_name = choices_map.get(current, "Auto-detect")
            options = ", ".join(
                f"{code} ({name})"
                for code, name in LANGUAGE_CHOICES
                if code  # skip the "" / Auto-detect entry for the options list
            )
            client.send_message(
                chat_id,
                f"Current language: {current_name}\n\n"
                f"To change, send /language <code>. Available codes:\n{options}\n\n"
                "Send /language auto to reset to auto-detect.",
            )
            return

        lang_arg = parts[1].strip().lower()
        if lang_arg == "auto":
            identity.sudo().write({"language": ""})
            client.send_message(
                chat_id,
                "Language reset to auto-detect. I'll match the language you write in.",
            )
            return

        valid_codes = {code for code, _ in LANGUAGE_CHOICES if code}
        if lang_arg not in valid_codes:
            choices_map = dict(LANGUAGE_CHOICES)
            options = ", ".join(
                f"{code} ({name})" for code, name in LANGUAGE_CHOICES if code
            )
            client.send_message(
                chat_id,
                f"Unknown language code '{lang_arg}'.\n\nAvailable codes:\n{options}",
            )
            return

        choices_map = dict(LANGUAGE_CHOICES)
        identity.sudo().write({"language": lang_arg})
        client.send_message(
            chat_id,
            f"Language set to {choices_map[lang_arg]}. I'll reply in {choices_map[lang_arg]} from now on.",
        )

    def _handle_confirmation(self, sudo_env, tg, chat_id, payload):
        """Handle yes/no confirmation from inline keyboard.

        Payload format: ``confirm:yes:<nonce>`` or ``confirm:no:<nonce>``.
        The nonce is generated by the agent when staging the write and stored
        on the session row. We require it to match before executing — this
        prevents a prompt-injection attack from swapping the staged tool
        between "send confirmation" and "user clicks Yes".

        Runs identity+session lookup in ``sudo_env``; the agent always runs
        as the linked user (``sudo_env(user=identity.user_id.id)``).
        """
        from ..services.agent import OdooPilotAgent

        identity = sudo_env["odoopilot.identity"].search(
            [
                ("channel", "=", "telegram"),
                ("chat_id", "=", chat_id),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            return

        session = sudo_env["odoopilot.session"].search(
            [("channel", "=", "telegram"), ("chat_id", "=", chat_id)], limit=1
        )

        action, _, nonce = payload.partition(":")[2].partition(":")
        # payload="confirm:yes:abc" -> action="yes", nonce="abc"
        # payload="confirm:no"      -> action="no",  nonce=""

        if action == "no":
            # A "No" click without a valid nonce still cancels — rejecting
            # the user's cancellation would be worse than the small risk of
            # a forged cancel (which only loses the staged write, not data).
            tg.send_message(chat_id, "Cancelled.")
            if session:
                session.clear_pending()
                session.append_message("user", "(I declined the action)")
                session.append_message(
                    "assistant", "Understood, the action was cancelled."
                )
            return

        if action == "yes":
            if not session or not session.pending_tool:
                tg.send_message(chat_id, "Nothing to confirm.")
                return
            if not session.verify_and_consume_nonce(nonce):
                _logger.warning(
                    "OdooPilot: rejecting Telegram confirmation for chat %s "
                    "due to nonce mismatch (possible prompt-injection swap)",
                    chat_id,
                )
                tg.send_message(
                    chat_id,
                    "This confirmation has expired. Please ask me again.",
                )
                session.clear_pending()
                return
            tool_name = session.pending_tool
            args = json.loads(session.pending_args or "{}")
            session.clear_pending()  # Clear before exec to avoid double-run
            user_env = sudo_env(user=identity.user_id.id)
            agent = OdooPilotAgent(user_env, tg, channel="telegram")
            agent.execute_confirmed(chat_id, tool_name, args)
            return

        # Defence-in-depth: malformed callback payload. The original code
        # silently fell through to no-op, which was correct behaviour but
        # made it harder to spot bugs. Log and explicitly return.
        _logger.warning(
            "OdooPilot: ignoring malformed Telegram callback payload for chat %s: %r",
            chat_id,
            payload,
        )

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
        """WhatsApp Cloud API webhook verification challenge (hub.challenge handshake).

        Uses ``hmac.compare_digest`` for the verify-token comparison even
        though this token is low-value (only used during webhook setup) and
        Meta retries quickly: it costs nothing and removes one more place
        a future timing-attack analysis would need to reason about.
        """
        mode = request.params.get("hub.mode")
        token = request.params.get("hub.verify_token") or ""
        challenge = request.params.get("hub.challenge", "")

        cfg = request.env["ir.config_parameter"].sudo()
        expected = cfg.get_param("odoopilot.whatsapp_verify_token") or ""

        if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
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
        """Receive WhatsApp Cloud API updates and dispatch asynchronously.

        Security: every POST is verified against Meta's
        ``X-Hub-Signature-256`` header (HMAC-SHA256 of the raw body, keyed
        with the App Secret). If the App Secret is not configured, OR the
        header is missing/invalid, the request is rejected with HTTP 403.
        Without this check, anyone who discovers the webhook URL can
        impersonate any linked WhatsApp user (CVE-style critical).
        """
        from ..services.whatsapp import verify_signature

        cfg = request.env["ir.config_parameter"].sudo()
        if not cfg.get_param("odoopilot.whatsapp_enabled"):
            return request.make_response("", status=200)

        app_secret = cfg.get_param("odoopilot.whatsapp_app_secret") or ""
        if not app_secret:
            _logger.warning(
                "OdooPilot: rejecting WhatsApp webhook because "
                "odoopilot.whatsapp_app_secret is not configured"
            )
            return request.make_response("Forbidden", status=403)

        # IMPORTANT: read the raw body bytes *before* any json parse —
        # Meta signs the exact bytes it sent, re-encoding breaks the HMAC.
        raw_body = request.httprequest.get_data(cache=True)
        signature = request.httprequest.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(app_secret, raw_body, signature):
            _logger.warning(
                "OdooPilot: rejecting WhatsApp webhook with bad/missing "
                "X-Hub-Signature-256 header"
            )
            return request.make_response("Forbidden", status=403)

        try:
            update = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return request.make_response("Bad request", status=400)

        chat_id = _whatsapp_chat_id(update)
        if chat_id and not throttle.allow(request.env, "whatsapp", chat_id):
            return request.make_response("", status=200)

        # Idempotency: Meta retries on 5xx and timeouts. Dedup per-message
        # (one envelope can carry several) and drop already-seen ones.
        seen_model = request.env["odoopilot.delivery.seen"].sudo()
        any_new = False
        for entry in update.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                kept = []
                for msg in value.get("messages", []) or []:
                    msg_id = msg.get("id")
                    if msg_id and not seen_model.mark_or_drop("whatsapp", str(msg_id)):
                        continue
                    kept.append(msg)
                value["messages"] = kept
                if kept:
                    any_new = True
        if not any_new:
            return request.make_response("", status=200)

        db = request.env.cr.dbname
        registry = request.env.registry

        throttle.submit(request.env, self._process_whatsapp_async, db, registry, update)
        return request.make_response("", status=200)

    def _process_whatsapp_async(self, db, registry, update):
        """Process a WhatsApp update in a background thread."""
        import odoo

        try:
            with registry.cursor() as cr:
                # See ``_process_update_async`` for why this is named ``sudo_env``.
                sudo_env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                self._dispatch_whatsapp(sudo_env, update)
        except Exception:
            _logger.exception("OdooPilot: unhandled error processing WhatsApp update")

    def _dispatch_whatsapp(self, sudo_env, update):
        """Route an inbound WhatsApp update.

        See ``_dispatch_update`` for the trust-boundary contract on
        ``sudo_env`` — same rules apply here.
        """
        from ..services.whatsapp import WhatsAppClient

        cfg = sudo_env["ir.config_parameter"].sudo()
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
                                sudo_env, wa, from_number, payload
                            )
                        continue

                    # Text message
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "").strip()
                        if not text:
                            continue
                        self._handle_whatsapp_message(sudo_env, wa, from_number, text)

    def _handle_whatsapp_message(self, sudo_env, wa, from_number, text):
        from ..services.agent import OdooPilotAgent

        if text.startswith("/link"):
            raw = sudo_env["odoopilot.link.token"].sudo().issue("whatsapp", from_number)
            base_url = (
                sudo_env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            )
            link_url = f"{base_url.rstrip('/')}/odoopilot/link/start?token={raw}"
            wa.send_message(
                from_number,
                f"Click the link to connect your Odoo account "
                f"(expires in 1 hour, single use):\n\n{link_url}",
            )
            return

        if text.startswith("/start"):
            wa.send_message(
                from_number,
                "Hi! I'm OdooPilot — your Odoo AI assistant.\n\nUse /link to connect your Odoo account, then ask me anything.",
            )
            return

        identity = sudo_env["odoopilot.identity"].search(
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

        # /language command
        if text.startswith("/language"):
            self._handle_language_command(sudo_env, wa, from_number, text, identity)
            return

        # Re-scope to the linked Odoo user before any business-data access.
        user_env = sudo_env(user=identity.user_id.id)
        agent = OdooPilotAgent(user_env, wa, channel="whatsapp")
        agent.handle_message(from_number, text)

    def _handle_whatsapp_confirmation(self, sudo_env, wa, from_number, payload):
        """See _handle_confirmation for the security model — same nonce check."""
        from ..services.agent import OdooPilotAgent

        identity = sudo_env["odoopilot.identity"].search(
            [
                ("channel", "=", "whatsapp"),
                ("chat_id", "=", from_number),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not identity:
            return

        session = sudo_env["odoopilot.session"].search(
            [("channel", "=", "whatsapp"), ("chat_id", "=", from_number)], limit=1
        )

        action, _, nonce = payload.partition(":")[2].partition(":")

        if action == "no":
            wa.send_message(from_number, "Cancelled.")
            if session:
                session.clear_pending()
                session.append_message("user", "(I declined the action)")
                session.append_message(
                    "assistant", "Understood, the action was cancelled."
                )
            return

        if action == "yes":
            if not session or not session.pending_tool:
                wa.send_message(from_number, "Nothing to confirm.")
                return
            if not session.verify_and_consume_nonce(nonce):
                _logger.warning(
                    "OdooPilot: rejecting WhatsApp confirmation for %s "
                    "due to nonce mismatch (possible prompt-injection swap)",
                    from_number,
                )
                wa.send_message(
                    from_number,
                    "This confirmation has expired. Please ask me again.",
                )
                session.clear_pending()
                return
            tool_name = session.pending_tool
            args = json.loads(session.pending_args or "{}")
            session.clear_pending()
            user_env = sudo_env(user=identity.user_id.id)
            agent = OdooPilotAgent(user_env, wa, channel="whatsapp")
            agent.execute_confirmed(from_number, tool_name, args)
            return

        # Malformed payload — log and explicitly no-op. Mirrors the same
        # defensive branch in ``_handle_confirmation``.
        _logger.warning(
            "OdooPilot: ignoring malformed WhatsApp callback payload for %s: %r",
            from_number,
            payload,
        )

    # ------------------------------------------------------------------
    # Account linking pages
    # ------------------------------------------------------------------

    @http.route("/odoopilot/link/start", type="http", auth="user", methods=["GET"])
    def link_start(self, token=None, **kwargs):
        """GET: show a CSRF-protected confirmation page.

        Security: this endpoint MUST NOT consume the token or write any state.
        The previous design (consume on GET) was vulnerable to a CSRF attack
        where an attacker drops ``<img src="…/odoopilot/link/start?token=…">``
        into any record an admin will render (lead description, mail comment,
        customer note); the admin's browser then fires the GET while
        authenticated as admin, and the attacker's chat is silently linked to
        the admin's Odoo account. By making GET render a form and only POST
        actually link, the browser's automatic CSRF protection (Odoo injects
        a session-bound ``csrf_token``) blocks the attack.
        """
        if not token:
            return request.render("odoopilot.link_error", {"error": "Missing token."})

        # Peek without deleting — token consumption happens on POST.
        payload = request.env["odoopilot.link.token"].sudo().peek(token)
        if not payload:
            return request.render(
                "odoopilot.link_error",
                {"error": "Invalid, already-used, or expired link. Use /link again."},
            )

        channel = payload["channel"]
        chat_id = payload["chat_id"]

        # If a different Odoo user already owns this chat link, refuse the
        # silent hijack — even with a valid token. The legitimate owner must
        # unlink first via the OdooPilot Identities admin view. Returning the
        # error page here also burns the GET preview only; the token row stays
        # intact (POST is what consumes), but a confused user can simply click
        # "Cancel" and ask the bot for /link again.
        existing = request.env["odoopilot.identity"].search(
            [("channel", "=", channel), ("chat_id", "=", chat_id)], limit=1
        )
        if existing and existing.user_id and existing.user_id.id != request.env.user.id:
            return request.render(
                "odoopilot.link_error",
                {
                    "error": (
                        f"This {channel} chat is already linked to another Odoo "
                        f"user ({existing.user_id.name}). Ask them to unlink it "
                        "first from Settings → Technical → OdooPilot Identities."
                    )
                },
            )

        return request.render(
            "odoopilot.link_confirm",
            {
                "user": request.env.user,
                "channel": channel,
                "chat_id": chat_id,
                "token": token,
            },
        )

    @http.route(
        "/odoopilot/link/confirm",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def link_confirm(self, token=None, **kwargs):
        """POST: actually consume the token and create/update the identity.

        ``csrf=True`` makes Odoo's HTTP layer require a valid ``csrf_token``
        form field bound to the current session — this is what blocks the
        cross-site GET attack described on ``link_start``. Browsers will not
        autofill a form to a third-party origin without user interaction, and
        even if they did, they cannot forge the per-session CSRF token.
        """
        if not token:
            return request.render("odoopilot.link_error", {"error": "Missing token."})

        # Atomic: looks up by SHA-256 digest of the raw token, deletes the row,
        # and only returns a payload if the token had not yet expired.
        payload = request.env["odoopilot.link.token"].sudo().consume(token)
        if not payload:
            return request.render(
                "odoopilot.link_error",
                {"error": "Invalid, already-used, or expired link. Use /link again."},
            )

        channel = payload["channel"]
        chat_id = payload["chat_id"]

        existing = request.env["odoopilot.identity"].search(
            [("channel", "=", channel), ("chat_id", "=", chat_id)], limit=1
        )
        if existing and existing.user_id and existing.user_id.id != request.env.user.id:
            # Race: someone else linked between GET preview and POST. The
            # token has already been burnt above (one-shot), but we refuse
            # the hijack write — the legitimate owner keeps their identity.
            _logger.warning(
                "OdooPilot: refusing identity hijack on POST: chat=%s/%s "
                "owner=%s attacker_uid=%s",
                channel,
                chat_id,
                existing.user_id.id,
                request.env.user.id,
            )
            return request.render(
                "odoopilot.link_error",
                {
                    "error": (
                        f"This {channel} chat is already linked to another Odoo "
                        f"user ({existing.user_id.name}). Ask them to unlink it "
                        "first."
                    )
                },
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

        # Notify user on the originating channel
        cfg = request.env["ir.config_parameter"].sudo()
        welcome = (
            f"Account linked! Welcome, {request.env.user.name}. "
            "You can now ask me anything about your Odoo data."
        )
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

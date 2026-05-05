from odoo import _, fields, models
from odoo.exceptions import UserError
import logging
import secrets

import requests

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Telegram
    odoopilot_telegram_bot_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter="odoopilot.telegram_bot_token",
        help="From @BotFather on Telegram.",
    )
    odoopilot_telegram_webhook_secret = fields.Char(
        string="Webhook Secret (auto-generated)",
        config_parameter="odoopilot.telegram_webhook_secret",
        help=(
            "Required. Telegram includes it as the "
            "X-Telegram-Bot-Api-Secret-Token header on every webhook POST. "
            "Auto-generated when you click 'Register webhook' if blank. "
            "Without this, anyone who finds the webhook URL can spoof "
            "messages from any user."
        ),
    )
    odoopilot_telegram_enabled = fields.Boolean(
        string="Telegram Enabled",
        config_parameter="odoopilot.telegram_enabled",
    )

    # LLM
    odoopilot_llm_provider = fields.Selection(
        [
            ("anthropic", "Anthropic (Claude)"),
            ("openai", "OpenAI (GPT)"),
            ("groq", "Groq (Free tier)"),
        ],
        string="LLM Provider",
        config_parameter="odoopilot.llm_provider",
        default="anthropic",
    )
    odoopilot_llm_api_key = fields.Char(
        string="LLM API Key",
        config_parameter="odoopilot.llm_api_key",
    )
    odoopilot_llm_model = fields.Char(
        string="Model (optional override)",
        config_parameter="odoopilot.llm_model",
        help="Leave blank to use provider default: claude-3-5-haiku-20241022 / gpt-4o-mini / llama-3.1-70b-versatile",
    )

    # Voice (speech-to-text)
    #
    # Voice support is opt-in: an operator must explicitly enable it
    # AND configure an STT provider + key. We don't auto-derive the
    # STT key from the LLM key because the operator might be on
    # Anthropic or Ollama for chat (no Whisper there) and want voice
    # off rather than silently routing audio to a third party.
    odoopilot_voice_enabled = fields.Boolean(
        string="Voice Messages",
        config_parameter="odoopilot.voice_enabled",
        help=(
            "Accept voice messages from Telegram and WhatsApp. Audio is "
            "transcribed via the STT provider below and then handled by "
            "the same agent loop as a typed message."
        ),
    )
    odoopilot_stt_provider = fields.Selection(
        [
            ("groq", "Groq (whisper-large-v3, free tier)"),
            ("openai", "OpenAI (whisper-1)"),
        ],
        string="STT Provider",
        config_parameter="odoopilot.stt_provider",
        default="groq",
        help=(
            "Speech-to-text backend. Groq's free tier is the cheapest "
            "way to start; OpenAI offers higher rate limits at paid tiers."
        ),
    )
    odoopilot_stt_api_key = fields.Char(
        string="STT API Key",
        config_parameter="odoopilot.stt_api_key",
        help=(
            "API key for the STT provider above. Can be the same key as "
            "the LLM provider when both are Groq or both are OpenAI."
        ),
    )
    odoopilot_stt_model = fields.Char(
        string="STT Model (optional override)",
        config_parameter="odoopilot.stt_model",
        help=(
            "Leave blank to use provider default (whisper-large-v3 for "
            "Groq, whisper-1 for OpenAI)."
        ),
    )
    odoopilot_voice_max_duration_seconds = fields.Integer(
        string="Max voice duration (seconds)",
        config_parameter="odoopilot.voice_max_duration_seconds",
        default=60,
        help=(
            "Voice messages longer than this are rejected before "
            "download. Caps STT cost and DoS surface. Default: 60."
        ),
    )

    # WhatsApp
    odoopilot_whatsapp_enabled = fields.Boolean(
        string="WhatsApp Enabled",
        config_parameter="odoopilot.whatsapp_enabled",
    )
    odoopilot_whatsapp_phone_number_id = fields.Char(
        string="Phone Number ID",
        config_parameter="odoopilot.whatsapp_phone_number_id",
        help="From Meta Developer console → WhatsApp → API Setup.",
    )
    odoopilot_whatsapp_access_token = fields.Char(
        string="Access Token",
        config_parameter="odoopilot.whatsapp_access_token",
        help="Permanent system user token or temporary test token from Meta.",
    )
    odoopilot_whatsapp_verify_token = fields.Char(
        string="Verify Token",
        config_parameter="odoopilot.whatsapp_verify_token",
        help="Any random string you choose — paste the same value in the Meta webhook config.",
    )
    odoopilot_whatsapp_app_secret = fields.Char(
        string="App Secret (REQUIRED)",
        config_parameter="odoopilot.whatsapp_app_secret",
        help=(
            "Meta App Secret from App Dashboard -> Settings -> Basic. "
            "REQUIRED for webhook security: every incoming POST is verified "
            "with HMAC-SHA256(app_secret, body) against the "
            "X-Hub-Signature-256 header. Without this, anyone who discovers "
            "the webhook URL can impersonate any linked WhatsApp user."
        ),
    )

    # Notifications
    odoopilot_notify_task_digest = fields.Boolean(
        string="Daily task digest",
        config_parameter="odoopilot.notify_task_digest",
        help="Send each user their overdue and today's tasks every morning at 08:00 UTC.",
    )
    odoopilot_notify_invoice_alerts = fields.Boolean(
        string="Overdue invoice alerts",
        config_parameter="odoopilot.notify_invoice_alerts",
        help="Send users with accounting access a daily overdue invoice summary at 09:00 UTC.",
    )

    def action_register_telegram_webhook(self):
        """Register the Odoo webhook URL with Telegram.

        Security: the webhook secret is mandatory. If none is configured,
        we auto-generate a 32-byte URL-safe secret here, persist it, and
        register it with Telegram. The OdooPilot webhook handler then
        rejects any incoming request whose
        ``X-Telegram-Bot-Api-Secret-Token`` header does not match.
        """
        cfg = self.env["ir.config_parameter"].sudo()
        token = cfg.get_param("odoopilot.telegram_bot_token")
        if not token:
            raise UserError(_("Please save the Telegram Bot Token first."))

        base_url = cfg.get_param("web.base.url", "")
        if not base_url:
            raise UserError(
                _(
                    "web.base.url is not configured. Set it under "
                    "Settings -> Technical -> System Parameters before "
                    "registering the webhook."
                )
            )
        webhook_url = f"{base_url.rstrip('/')}/odoopilot/webhook/telegram"

        secret = cfg.get_param("odoopilot.telegram_webhook_secret") or ""
        if not secret:
            # Auto-generate a strong secret so the webhook is never left
            # unauthenticated. Telegram's secret_token must match
            # ``[A-Za-z0-9_-]{1,256}`` and token_urlsafe satisfies that.
            secret = secrets.token_urlsafe(32)
            cfg.set_param("odoopilot.telegram_webhook_secret", secret)

        payload = {
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"],
            "secret_token": secret,
        }
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Webhook registered"),
                    "message": (
                        f"Telegram webhook set to: {webhook_url} "
                        "(secret token configured)."
                    ),
                    "type": "success",
                },
            }
        raise UserError(
            _("Telegram error: %s") % data.get("description", "Unknown error")
        )

    def action_test_whatsapp_connection(self):
        """Verify the WhatsApp phone number ID and access token via Graph API."""
        phone_number_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoopilot.whatsapp_phone_number_id")
        )
        access_token = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoopilot.whatsapp_access_token")
        )
        if not phone_number_id or not access_token:
            raise UserError(
                _("Please save the Phone Number ID and Access Token first.")
            )
        resp = requests.get(
            f"https://graph.facebook.com/v19.0/{phone_number_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("id"):
            display = data.get("display_phone_number", phone_number_id)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connected!"),
                    "message": f"WhatsApp number: {display}",
                    "type": "success",
                },
            }
        error = data.get("error", {}).get("message", "Unknown error")
        raise UserError(_(f"WhatsApp API error: {error}"))

    def action_test_telegram_connection(self):
        """Test bot token by calling getMe."""
        token = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoopilot.telegram_bot_token")
        )
        if not token:
            raise UserError(_("No Telegram Bot Token configured."))
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = resp.json()
        if data.get("ok"):
            bot = data["result"]
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connected!"),
                    "message": f"Bot: @{bot.get('username')} ({bot.get('first_name')})",
                    "type": "success",
                },
            }
        raise UserError(
            _(f"Telegram error: {data.get('description', 'Unknown error')}")
        )

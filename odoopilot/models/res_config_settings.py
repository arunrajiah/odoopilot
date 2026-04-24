from odoo import _, fields, models
from odoo.exceptions import UserError
import requests
import logging

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
        string="Webhook Secret (optional)",
        config_parameter="odoopilot.telegram_webhook_secret",
        help="Random string added as X-Telegram-Bot-Api-Secret-Token header.",
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
        """Register the Odoo webhook URL with Telegram."""
        token = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoopilot.telegram_bot_token")
        )
        if not token:
            raise UserError(_("Please save the Telegram Bot Token first."))

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        webhook_url = f"{base_url.rstrip('/')}/odoopilot/webhook/telegram"
        secret = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoopilot.telegram_webhook_secret")
            or None
        )

        payload = {"url": webhook_url, "allowed_updates": ["message", "callback_query"]}
        if secret:
            payload["secret_token"] = secret

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
                    "message": f"Telegram webhook set to: {webhook_url}",
                    "type": "success",
                },
            }
        raise UserError(
            _(f"Telegram error: {data.get('description', 'Unknown error')}")
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

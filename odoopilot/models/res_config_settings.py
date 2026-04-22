from odoo import _, api, fields, models
from odoo.exceptions import UserError
import requests
import json
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

    def action_register_telegram_webhook(self):
        """Register the Odoo webhook URL with Telegram."""
        token = self.env["ir.config_parameter"].sudo().get_param("odoopilot.telegram_bot_token")
        if not token:
            raise UserError(_("Please save the Telegram Bot Token first."))

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        webhook_url = f"{base_url.rstrip('/')}/odoopilot/webhook/telegram"
        secret = self.env["ir.config_parameter"].sudo().get_param("odoopilot.telegram_webhook_secret") or None

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
        raise UserError(_(f"Telegram error: {data.get('description', 'Unknown error')}"))

    def action_test_telegram_connection(self):
        """Test bot token by calling getMe."""
        token = self.env["ir.config_parameter"].sudo().get_param("odoopilot.telegram_bot_token")
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
        raise UserError(_(f"Telegram error: {data.get('description', 'Unknown error')}"))

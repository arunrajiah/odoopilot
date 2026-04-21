from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    odoopilot_service_url = fields.Char(
        string="OdooPilot Service URL",
        config_parameter="mail_gateway_ai.service_url",
        help="Base URL of the OdooPilot service, e.g. https://odoopilot.example.com",
    )
    odoopilot_telegram_enabled = fields.Boolean(
        string="Telegram enabled",
        config_parameter="mail_gateway_ai.telegram_enabled",
    )
    odoopilot_whatsapp_enabled = fields.Boolean(
        string="WhatsApp enabled (v0.3+)",
        config_parameter="mail_gateway_ai.whatsapp_enabled",
    )

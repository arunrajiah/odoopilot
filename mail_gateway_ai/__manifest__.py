{
    "name": "AI Mail Gateway",
    "summary": "AI messaging bridge for Odoo Community — Telegram & WhatsApp via any LLM",
    "version": "17.0.1.0.0",
    "development_status": "Alpha",
    "category": "Discuss",
    "license": "LGPL-3",
    # When submitting to OCA, append ", Odoo Community Association (OCA)" to author
    "author": "OdooPilot Contributors",
    "website": "https://github.com/arunrajiah/odoopilot",
    "depends": ["mail", "base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/mail_gateway_ai_identity_views.xml",
        "views/mail_gateway_ai_audit_views.xml",
    ],
    # apps.odoo.com: add screenshots to static/description/ and list them here
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}

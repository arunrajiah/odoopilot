Standard Odoo module install:

#. Copy the ``odoopilot`` directory into your Odoo addons path
   (or ``pip install`` the wheel built from this repository).
#. Restart the Odoo server with the module update flag::

      ./odoo-bin -c odoo.conf -u odoopilot

#. Open *Apps*, search for "OdooPilot", and click *Install*.

The addon has no extra Python dependencies beyond what Odoo Community
ships -- it calls the LLM and STT provider APIs directly via the
``requests`` library that Odoo already includes.

Prerequisites
~~~~~~~~~~~~~

* Odoo 17.0 or 18.0 (Community or Enterprise).
* The Odoo instance must be reachable over HTTPS from the internet
  for Telegram and WhatsApp to deliver webhooks.
* An LLM API key from Anthropic, OpenAI, Groq (has a free tier), or
  a running Ollama endpoint.
* For Telegram: a bot token from `@BotFather <https://t.me/BotFather>`_.
* For WhatsApp: a Meta Business account with the `Cloud API
  <https://developers.facebook.com/docs/whatsapp/cloud-api>`_ enabled
  (phone-number id, permanent access token, and app secret).

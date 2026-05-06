All configuration lives at *Settings -> OdooPilot*. The same panel
has community links for sponsoring, feedback, bug reports and
private security disclosure.

Telegram
~~~~~~~~

#. Paste the bot token from `@BotFather <https://t.me/BotFather>`_ into
   *Telegram Bot Token*.
#. Click *Register Webhook*. The action calls Telegram's ``setWebhook``
   API and **auto-generates a 32-byte secret** that Telegram echoes back
   on every delivery as ``X-Telegram-Bot-Api-Secret-Token``. The
   webhook endpoint rejects any request whose header doesn't match.

WhatsApp
~~~~~~~~

#. Paste the Phone Number ID, permanent access token, verify token, and
   App Secret from the Meta App Dashboard.
#. In Meta's webhook config, set the callback URL to
   ``https://YOUR_ODOO/odoopilot/webhook/whatsapp`` and the verify
   token to whatever you pasted above.

The App Secret is **mandatory**. Without it the WhatsApp webhook
refuses all traffic. Meta signs every POST with
``X-Hub-Signature-256`` (HMAC-SHA256 of the raw body, keyed with the
App Secret); OdooPilot verifies this in constant time before any
business logic runs.

LLM provider
~~~~~~~~~~~~

Pick one of ``anthropic``, ``openai``, ``groq`` or ``ollama`` and
paste your API key. Default models if you leave the override blank:

============  ===================================  ============================
Provider      Default model                        Notes
============  ===================================  ============================
anthropic     ``claude-3-5-haiku-20241022``        Best reasoning per dollar
openai        ``gpt-4o-mini``                      Widest ecosystem
groq          ``llama-3.3-70b-versatile``          Free tier, very fast
ollama        (set in override field)              100% local, e.g. ``llama3.2``
============  ===================================  ============================

In-Odoo web chat widget (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Off by default. When enabled, every logged-in Odoo user sees a chat-
bubble icon in the systray (top-right of the navigation bar). Click
it and a panel opens with the conversation history and an input
field. Same agent loop as Telegram and WhatsApp; no ``/link`` flow
needed because the user is already authenticated.

To enable, tick **In-Odoo Web Chat** on the Settings panel. To
disable for a deployment, untick. Users see the icon disappear on
the next page reload.

The widget runs the same write-confirmation gate (Yes / No buttons
inline in the panel), the same per-(channel, chat_id) rate limit
(channel ``web``, chat_id = the user's Odoo id), the same scope
guard, and the same audit log. The frontend is XSS-safe; assistant
messages render as escaped text, never as HTML. Voice messages and
file uploads are not supported on this channel today.

Voice messages (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~

Off by default. Enable in the Voice messages box on the same panel
and configure an STT provider:

* ``groq`` -- ``whisper-large-v3``, free tier, ~10x faster than OpenAI
* ``openai`` -- ``whisper-1``, ~$0.006 per audio-minute

The duration cap (default 60 seconds) and the 25 MB hard file cap
bound both bandwidth and STT spend per message.

Linking employee accounts
~~~~~~~~~~~~~~~~~~~~~~~~~

Each employee sends ``/link`` to the bot. The bot replies with a
one-time URL. The employee opens the URL while logged into Odoo,
sees a confirmation page, clicks **Confirm and link**, and they are
done.

The flow uses a two-step CSRF-protected handshake: GET previews,
POST consumes. A logged-in admin who renders an
``<img src="…/odoopilot/link/start?token=…">`` from a malicious
record will not get silently linked -- the consume only happens on
a POST with Odoo's session-bound CSRF token.

Optional throttling knobs
~~~~~~~~~~~~~~~~~~~~~~~~~

Three system parameters tune the rate limit and worker pool:

==========================================  =========  ==============================
Parameter                                   Default    What it controls
==========================================  =========  ==============================
``odoopilot.rate_limit_per_hour``           ``30``     Messages per chat per window
``odoopilot.rate_limit_window_seconds``     ``3600``   Sliding-window length
``odoopilot.worker_pool_size``              ``8``      Bounded thread pool
``odoopilot.voice_max_duration_seconds``    ``60``     Max length of a voice note
==========================================  =========  ==============================

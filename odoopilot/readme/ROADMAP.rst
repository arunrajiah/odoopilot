The 17 and 18 series are both Beta and live on the Odoo App Store.
The named code workstreams are drained; what remains is reactive
plus a handful of optional follow-ups.

Planned
~~~~~~~

* OCA submission. Both branches are now Beta with a hardened
  security model audited four times, ~2,500 lines of regression
  tests, and conformance with OCA module structure (this preparation).
* Odoo 16 backport. Low priority; only if there is operator demand.
* Redis-backed rate limiter. The current rate limit is in-process
  per Odoo HTTP worker; multi-Odoo-worker deployments that need a
  hard global cap would benefit from a shared backend.

Out of scope
~~~~~~~~~~~~

* A custom Wear OS or smartphone app. The product deliberately
  rides on the chat platforms' own apps so employees can use
  whatever they already have. Wear OS works today via Telegram for
  Wear OS / WhatsApp for Wear OS.
* Customer-facing chatbot widgets. OdooPilot is for the internal
  team, not for end-customers. The trust model and tool surface are
  different enough that a customer-facing variant would be a
  separate addon.

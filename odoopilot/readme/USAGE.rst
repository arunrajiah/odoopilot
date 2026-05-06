After install + configuration + linking, employees chat with the bot
exactly like any other Telegram or WhatsApp contact. Three command
shortcuts are available:

* ``/start`` -- short hello and what-can-this-do reply.
* ``/link`` -- (re-)issue a linking URL. The previous identity row,
  if any, is invalidated.
* ``/language <code>`` -- set the preferred reply language. Codes:
  ``en``, ``fr``, ``es``, ``de``, ``it``, ``pt``, ``nl``, ``ar``,
  ``zh``, ``ja``, ``ko``, ``ru``, ``tr``, ``pl``, ``hi``. Use
  ``/language auto`` to revert to language auto-detection.

Read tools execute immediately. Write tools surface an inline
**Yes / No** confirmation; the prompt names the resolved record (not
the LLM's argument string) and the click carries a per-write nonce so
it cannot be swapped out by a prompt-injection between staging and
confirmation.

Example interactions
~~~~~~~~~~~~~~~~~~~~

* "What tasks are assigned to me today?"
* "Show me overdue invoices for ACME Corp."
* "Apply for 3 days off Mar 14-16."
* "Approve John's leave request."  *(then tap Yes)*
* "Move ACME deal to Negotiation, expected EUR 12k."  *(then tap Yes)*
* "Log 2 hours on Project Phoenix today -- implemented login flow."
* "Submit my expense for 42 EUR lunch with ACME."
* "Find the contact for billing@acme.com."

Voice messages are accepted on Telegram and WhatsApp when voice
support is enabled. Hold the record button, speak, and release.
The transcript runs through the same agent loop as if it had been
typed.

In-Odoo web chat
~~~~~~~~~~~~~~~~

When the widget is enabled in Settings, every logged-in Odoo user
sees a chat-bubble icon in the systray (top-right of the navigation
bar). Click it to open a panel inside the Odoo UI; type and submit
exactly like Telegram or WhatsApp. The linked user is whoever is
logged into Odoo, so write actions still surface a Yes / No
confirmation gate, the linked user's record-rule permissions still
apply, and every action lands in the audit log. No separate
``/link`` flow because the user is already authenticated.

Operator views
~~~~~~~~~~~~~~

*Settings -> OdooPilot* exposes two admin views (system-group only):

* **Linked Users** -- one row per linked Telegram / WhatsApp identity
  with last-activity timestamp, 7-day message count, and 7-day
  success rate. Filters: *Active in last 7 days*, *Linked but never
  used*, *Inactive (unlinked)*.
* **Audit Log** -- one immutable row per tool call (read or write).
  Failures decorated red. Filters: *Failures only*, *Write actions*,
  *Today*, *Last 7 days*. Group by user / tool / channel / outcome
  / day.

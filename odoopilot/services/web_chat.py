"""In-Odoo web chat client for the dashboard widget.

Why this exists
---------------

Telegram and WhatsApp give employees a hands-free way to reach Odoo
from outside Odoo. Some employees, though, spend their day in the
Odoo web UI and just want a chatbot widget there -- no separate app,
no /link flow, no phone in hand.

This module provides the bridge: a buffer-style client that mimics
the :class:`services.telegram.TelegramClient` interface so the
existing :class:`services.agent.OdooPilotAgent` loop runs unchanged.
The HTTP route in :mod:`controllers.main` constructs one of these
per request, runs the agent, and returns the buffered messages as
the JSON response body.

Why "buffer client" rather than streaming
-----------------------------------------

Streaming the agent's reply over a websocket or SSE would be a
nicer UX, but it adds two big complications: (1) websockets through
Odoo's HTTP layer require the longpolling worker on the operator's
side, which is a separate deployment knob; (2) it doubles the
attack surface for prompt injection / DoS. The synchronous-buffer
approach gives the same correctness guarantees as the messaging
channels with one less moving part. We can always upgrade to
streaming later without changing the agent.

Trust model
-----------

Identity is the logged-in Odoo user. The route is ``auth="user"``
so anonymous traffic gets 403'd at Odoo's HTTP layer before reaching
this module. We do NOT consult ``odoopilot.identity`` for the web
channel -- there is no separate chat_id to map; the chat_id IS the
user id.

Same scope guard, same per-write nonce, same audit log, same rate
limit (channel="web", chat_id=str(user.id)) as the messaging
channels. Voice messages and file uploads are NOT supported on this
channel today.
"""

from __future__ import annotations

from typing import Any


class WebChatClient:
    """Buffer client matching the messaging-client interface.

    The agent loop calls :meth:`send_message` and
    :meth:`send_confirmation`; both append a structured envelope to
    :attr:`outgoing` instead of doing any I/O. The HTTP route reads
    that list at the end and returns it to the browser.
    """

    def __init__(self) -> None:
        # Each element is a dict matching one of the documented
        # frontend envelopes:
        #   {"type": "text",    "text": str}
        #   {"type": "confirm", "question": str, "nonce": str}
        # Anything else is a programming error.
        self.outgoing: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Methods the agent loop calls (matches TelegramClient surface)
    # ------------------------------------------------------------------

    def send_message(self, chat_id: str, text: str, reply_markup=None) -> dict:
        """Buffer a text reply.

        ``reply_markup`` is accepted but ignored -- the web frontend
        renders text-only replies and exposes Yes / No buttons only
        through the dedicated ``confirm`` envelope below.
        """
        self.outgoing.append({"type": "text", "text": text or ""})
        return {}

    def send_confirmation(self, chat_id: str, question: str, nonce: str = "") -> dict:
        """Buffer a confirmation prompt with its per-write nonce.

        The frontend renders this as a question + Yes / No buttons.
        Clicking Yes posts ``confirm:yes:<nonce>`` to the same
        endpoint; clicking No posts ``confirm:no:<nonce>``. Both are
        routed by the controller into the existing
        ``_handle_confirmation`` flow.
        """
        self.outgoing.append(
            {
                "type": "confirm",
                "question": question or "",
                "nonce": nonce or "",
            }
        )
        return {}

    # ------------------------------------------------------------------
    # No-op methods the agent might call but the web channel doesn't
    # implement. Keeping them as no-ops avoids AttributeError if any
    # code path invokes them.
    # ------------------------------------------------------------------

    def answer_callback_query(self, *args, **kwargs) -> dict:
        """Telegram-only -- no-op on web."""
        return {}

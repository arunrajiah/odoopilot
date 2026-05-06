"""Tests for the 17.0.18.0.0 in-Odoo web chat widget.

We don't unit-test the OWL frontend here -- it's purely
presentational and would need a JS test harness. The interesting
contract surface is the backend:

1. **WebChatClient** -- buffer matches the agent's expected client
   interface (``send_message`` + ``send_confirmation``); calls
   accumulate as JSON-serialisable envelopes.

2. **The two HTTP routes** -- ``/odoopilot/web/config`` reflects the
   master flag; ``/odoopilot/web/message`` runs the agent and
   returns the buffered envelopes. The route handlers themselves
   require a live HTTP request, which we test only through the
   ``services`` they call.

3. **Confirmation routing** -- a ``confirm:yes:<nonce>`` payload
   reuses the existing nonce-verification path that
   ``_handle_confirmation`` already exercises (covered by
   ``test_security``); we just verify the WebChatClient buffer is
   filled correctly.
"""

import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..services.web_chat import WebChatClient


class TestWebChatClient(TransactionCase):
    """The buffer client is a faithful drop-in for TelegramClient."""

    def test_send_message_buffers_text_envelope(self):
        c = WebChatClient()
        c.send_message("user-42", "Hello!")
        self.assertEqual(
            c.outgoing,
            [{"type": "text", "text": "Hello!"}],
        )

    def test_multiple_send_message_calls_accumulate(self):
        c = WebChatClient()
        c.send_message("user-42", "first")
        c.send_message("user-42", "second")
        self.assertEqual(len(c.outgoing), 2)
        self.assertEqual(c.outgoing[0]["text"], "first")
        self.assertEqual(c.outgoing[1]["text"], "second")

    def test_send_confirmation_buffers_confirm_envelope(self):
        c = WebChatClient()
        c.send_confirmation("user-42", "Approve John's leave?", nonce="abc123")
        self.assertEqual(
            c.outgoing,
            [
                {
                    "type": "confirm",
                    "question": "Approve John's leave?",
                    "nonce": "abc123",
                }
            ],
        )

    def test_send_message_accepts_reply_markup_kwarg_silently(self):
        # The agent code path that sends an inline keyboard for the
        # confirmation passes reply_markup; on the web channel we
        # ignore it (we render Yes / No via the dedicated confirm
        # envelope instead). The kwarg must be accepted without
        # blowing up.
        c = WebChatClient()
        c.send_message("user-42", "Cancelled.", reply_markup={"buttons": []})
        self.assertEqual(c.outgoing[0]["text"], "Cancelled.")

    def test_outgoing_is_json_serialisable(self):
        # The HTTP route returns ``{"items": web_client.outgoing}`` as
        # the JSON response body. Any non-serialisable value here
        # would 500 the request.
        c = WebChatClient()
        c.send_message("user-42", "hi")
        c.send_confirmation("user-42", "ok?", nonce="n")
        json.dumps(c.outgoing)  # must not raise

    def test_answer_callback_query_is_a_safe_noop(self):
        # Telegram-only method; the agent doesn't call it on the web
        # channel today, but if any future code path does we don't
        # want an AttributeError.
        c = WebChatClient()
        self.assertEqual(c.answer_callback_query("anything"), {})


class TestWebChatRouting(TransactionCase):
    """The web-chat routes thread the right pieces together.

    We can't cleanly invoke ``http.route``-decorated methods here
    without a full HTTP transport, so the test focuses on the parts
    of the controller that ARE testable in isolation: the
    confirmation-routing logic in ``_handle_web_confirmation``,
    using a real session row.
    """

    def setUp(self):
        super().setUp()
        # Stage a pending write on a web session so the
        # _handle_web_confirmation path has something to consume.
        self.session = self.env["odoopilot.session"].create(
            {"channel": "web", "chat_id": str(self.env.uid)}
        )
        self.nonce = self.session.stage_pending(
            "mark_task_done", {"task_id": 9999, "task_name": "Test task"}
        )

    def test_confirmation_no_clears_pending_and_replies_cancelled(self):
        from ..controllers.main import OdooPilotController

        ctrl = OdooPilotController()
        client = WebChatClient()
        ctrl._handle_web_confirmation(
            self.env, client, str(self.env.uid), f"confirm:no:{self.nonce}"
        )
        # Pending is cleared.
        self.session.invalidate_recordset(["pending_tool"])
        self.assertFalse(self.session.pending_tool)
        # And the buffer says "Cancelled."
        self.assertTrue(any("Cancel" in m["text"] for m in client.outgoing))

    def test_confirmation_yes_with_bad_nonce_rejected(self):
        from ..controllers.main import OdooPilotController

        ctrl = OdooPilotController()
        client = WebChatClient()
        ctrl._handle_web_confirmation(
            self.env, client, str(self.env.uid), "confirm:yes:wrong-nonce"
        )
        # Bad nonce -> "expired" reply, pending cleared (consume).
        self.assertTrue(
            any("expired" in m["text"].lower() for m in client.outgoing),
            f"Expected 'expired' reply, got {client.outgoing!r}",
        )

    def test_confirmation_yes_with_correct_nonce_executes(self):
        from ..controllers.main import OdooPilotController

        ctrl = OdooPilotController()
        client = WebChatClient()
        # Patch out execute_confirmed so we don't actually try to
        # mark a non-existent task done -- this test pins the
        # routing, not the executor.
        with patch(
            "odoo.addons.odoopilot.services.agent.OdooPilotAgent.execute_confirmed"
        ) as fake_exec:
            ctrl._handle_web_confirmation(
                self.env, client, str(self.env.uid), f"confirm:yes:{self.nonce}"
            )
            self.assertEqual(fake_exec.call_count, 1)
        # Nonce was consumed.
        self.session.invalidate_recordset(["pending_nonce"])
        self.assertFalse(self.session.pending_nonce)

    def test_confirmation_with_no_pending_replies_nothing_to_confirm(self):
        from ..controllers.main import OdooPilotController

        # Wipe the staged write.
        self.session.clear_pending()
        ctrl = OdooPilotController()
        client = WebChatClient()
        ctrl._handle_web_confirmation(
            self.env, client, str(self.env.uid), f"confirm:yes:{self.nonce}"
        )
        self.assertTrue(
            any("nothing to confirm" in m["text"].lower() for m in client.outgoing)
        )

    def test_malformed_callback_payload_logged_not_crashed(self):
        from ..controllers.main import OdooPilotController

        ctrl = OdooPilotController()
        client = WebChatClient()
        # Defensive: ``confirm:`` with no action and no nonce. The
        # handler should noop (no chat reply, no exception).
        ctrl._handle_web_confirmation(self.env, client, str(self.env.uid), "confirm:")
        # No reply is fine; the test just asserts we didn't crash.
        self.assertEqual(client.outgoing, [])


class TestWebChatChannelKeyedSeparately(TransactionCase):
    """Web channel sessions don't collide with Telegram / WhatsApp ones.

    Sessions are keyed by ``(channel, chat_id)``. A user with chat_id=42
    on Telegram and Odoo user id 42 must end up in two different
    session rows.
    """

    def test_session_uniqueness_across_channels(self):
        Session = self.env["odoopilot.session"]
        web = Session.create({"channel": "web", "chat_id": "42"})
        tg = Session.create({"channel": "telegram", "chat_id": "42"})
        self.assertNotEqual(web.id, tg.id)
        self.assertEqual(web.channel, "web")
        self.assertEqual(tg.channel, "telegram")

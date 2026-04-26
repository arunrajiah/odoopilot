"""Regression tests for the OdooPilot 17.0.7.0.0 security release.

Each test maps to one of the four critical issues fixed in that release:

1. WhatsApp webhook now verifies Meta's X-Hub-Signature-256 HMAC.
2. Telegram webhook secret is mandatory.
3. Confirmation callbacks are bound to a per-write nonce.
4. Link tokens are stored as SHA-256 digests and consumed atomically.

These tests are pure-Python (no Odoo HTTP transport needed where possible)
and exercise the same helpers the controllers call.
"""

import hashlib
import hmac

from odoo.tests.common import TransactionCase

from ..services.whatsapp import verify_signature


class TestWhatsAppSignatureVerification(TransactionCase):
    """Fix #1 — WhatsApp HMAC verification."""

    def setUp(self):
        super().setUp()
        self.secret = "s3cr3t-app-secret"
        self.body = b'{"object":"whatsapp_business_account","entry":[]}'
        digest = hmac.new(
            self.secret.encode(), self.body, hashlib.sha256
        ).hexdigest()
        self.valid_header = f"sha256={digest}"

    def test_valid_signature_accepted(self):
        self.assertTrue(verify_signature(self.secret, self.body, self.valid_header))

    def test_missing_header_rejected(self):
        self.assertFalse(verify_signature(self.secret, self.body, ""))

    def test_missing_secret_rejected(self):
        self.assertFalse(verify_signature("", self.body, self.valid_header))

    def test_wrong_secret_rejected(self):
        self.assertFalse(
            verify_signature("wrong-secret", self.body, self.valid_header)
        )

    def test_tampered_body_rejected(self):
        tampered = self.body + b" "
        self.assertFalse(verify_signature(self.secret, tampered, self.valid_header))

    def test_bad_prefix_rejected(self):
        # Header without the required ``sha256=`` prefix must be rejected.
        digest = hmac.new(
            self.secret.encode(), self.body, hashlib.sha256
        ).hexdigest()
        self.assertFalse(verify_signature(self.secret, self.body, digest))
        self.assertFalse(
            verify_signature(self.secret, self.body, f"sha1={digest}")
        )

    def test_empty_signature_after_prefix_rejected(self):
        self.assertFalse(verify_signature(self.secret, self.body, "sha256="))


class TestSessionNoncePending(TransactionCase):
    """Fix #3 — confirmation callbacks are bound to a per-write nonce."""

    def setUp(self):
        super().setUp()
        self.session = self.env["odoopilot.session"].create(
            {"channel": "telegram", "chat_id": "111"}
        )

    def test_stage_pending_returns_nonempty_nonce(self):
        nonce = self.session.stage_pending("approve_leave", {"leave_id": 1})
        self.assertTrue(nonce)
        self.assertEqual(self.session.pending_tool, "approve_leave")
        self.assertEqual(self.session.pending_nonce, nonce)

    def test_each_stage_rotates_the_nonce(self):
        n1 = self.session.stage_pending("approve_leave", {"leave_id": 1})
        n2 = self.session.stage_pending("approve_leave", {"leave_id": 2})
        self.assertNotEqual(n1, n2)
        # After re-stage, the OLD nonce must no longer verify — this is
        # the core property that defends against the prompt-injection swap.
        self.assertFalse(self.session.verify_and_consume_nonce(n1))
        self.assertTrue(self.session.verify_and_consume_nonce(n2))

    def test_verify_rejects_empty(self):
        self.session.stage_pending("approve_leave", {"leave_id": 1})
        self.assertFalse(self.session.verify_and_consume_nonce(""))

    def test_verify_rejects_when_no_pending(self):
        # Fresh session has no pending nonce; any candidate must be rejected.
        self.assertFalse(self.session.verify_and_consume_nonce("anything"))

    def test_clear_pending_wipes_all_three_fields(self):
        self.session.stage_pending("approve_leave", {"leave_id": 1})
        self.session.clear_pending()
        self.assertFalse(self.session.pending_tool)
        self.assertFalse(self.session.pending_args)
        self.assertFalse(self.session.pending_nonce)


class TestLinkTokenLifecycle(TransactionCase):
    """Fix #4 — link tokens are hashed at rest and one-shot."""

    def test_raw_token_never_persisted(self):
        raw = self.env["odoopilot.link.token"].issue("telegram", "999")
        # The DB row stores the SHA-256 digest, not the raw token.
        digest = hashlib.sha256(raw.encode()).hexdigest()
        rows = self.env["odoopilot.link.token"].search([])
        self.assertTrue(rows)
        self.assertNotIn(raw, [r.token_digest for r in rows])
        self.assertIn(digest, [r.token_digest for r in rows])

    def test_consume_returns_payload_and_deletes_row(self):
        raw = self.env["odoopilot.link.token"].issue("whatsapp", "555")
        payload = self.env["odoopilot.link.token"].consume(raw)
        self.assertEqual(payload["channel"], "whatsapp")
        self.assertEqual(payload["chat_id"], "555")
        # Second consume returns None — single-use.
        self.assertIsNone(self.env["odoopilot.link.token"].consume(raw))

    def test_consume_rejects_unknown_token(self):
        self.assertIsNone(self.env["odoopilot.link.token"].consume("never-issued"))

    def test_issue_supersedes_previous_token_for_same_chat(self):
        first = self.env["odoopilot.link.token"].issue("telegram", "777")
        second = self.env["odoopilot.link.token"].issue("telegram", "777")
        # The first token is invalidated by re-issuing.
        self.assertIsNone(self.env["odoopilot.link.token"].consume(first))
        self.assertIsNotNone(self.env["odoopilot.link.token"].consume(second))

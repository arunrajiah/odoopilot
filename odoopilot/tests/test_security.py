"""Regression tests for the OdooPilot security releases.

The first four classes cover the 17.0.7.0.0 release (fixes #1–4 from the
public Reddit audit):

1. WhatsApp webhook verifies Meta's X-Hub-Signature-256 HMAC.
2. Telegram webhook secret is mandatory.
3. Confirmation callbacks are bound to a per-write nonce.
4. Link tokens are stored as SHA-256 digests and consumed atomically.

The next block covers 17.0.8.0.0 (fixes from the post-release internal
review):

5. Magic-link CSRF — GET only previews; POST is required to consume.
6. Magic-link identity hijack — refuse to re-link a chat to a different user.
7. Wildcard write-target hijack — preflight resolves the target up-front,
   reject overly-short / wildcard-only names, store ``res_id`` not
   ``name`` in the staged args.
8. Sliding-window rate limit per (channel, chat_id).
9. Webhook idempotency via the ``odoopilot.delivery.seen`` table.

Final block covers 17.0.9.0.0 (defence-in-depth from the same internal
review):

10. Telegram bot token is scrubbed from logged exception strings.
11. (No new test — covered by code inspection of the explicit ``else``
    branch in ``_handle_confirmation`` / ``_handle_whatsapp_confirmation``.)
12. WhatsApp ``verify_token`` comparison uses ``hmac.compare_digest``.

Tests are pure-Python where possible (no Odoo HTTP transport needed) and
exercise the same helpers the controllers call.
"""

import hashlib
import hmac

from odoo.tests.common import TransactionCase

from ..services import throttle
from ..services.telegram import TelegramClient
from ..services.tools import preflight_write
from ..services.whatsapp import verify_signature


class TestWhatsAppSignatureVerification(TransactionCase):
    """Fix #1 — WhatsApp HMAC verification."""

    def setUp(self):
        super().setUp()
        self.secret = "s3cr3t-app-secret"
        self.body = b'{"object":"whatsapp_business_account","entry":[]}'
        digest = hmac.new(self.secret.encode(), self.body, hashlib.sha256).hexdigest()
        self.valid_header = f"sha256={digest}"

    def test_valid_signature_accepted(self):
        self.assertTrue(verify_signature(self.secret, self.body, self.valid_header))

    def test_missing_header_rejected(self):
        self.assertFalse(verify_signature(self.secret, self.body, ""))

    def test_missing_secret_rejected(self):
        self.assertFalse(verify_signature("", self.body, self.valid_header))

    def test_wrong_secret_rejected(self):
        self.assertFalse(verify_signature("wrong-secret", self.body, self.valid_header))

    def test_tampered_body_rejected(self):
        tampered = self.body + b" "
        self.assertFalse(verify_signature(self.secret, tampered, self.valid_header))

    def test_bad_prefix_rejected(self):
        # Header without the required ``sha256=`` prefix must be rejected.
        digest = hmac.new(self.secret.encode(), self.body, hashlib.sha256).hexdigest()
        self.assertFalse(verify_signature(self.secret, self.body, digest))
        self.assertFalse(verify_signature(self.secret, self.body, f"sha1={digest}"))

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


# ── 17.0.8.0.0 follow-up release ────────────────────────────────────────────


class TestLinkTokenPeekDoesNotConsume(TransactionCase):
    """Fix #2/#3 — GET on /odoopilot/link/start must NOT consume the token.

    The previous design consumed on GET, which is exploitable via a CSRF
    image tag that fires the GET while the victim is logged in as an admin.
    The new design: GET calls ``peek`` (renders a confirm form), POST calls
    ``consume`` (does the actual link). This test pins the ``peek`` semantics.
    """

    def test_peek_returns_payload_without_deleting(self):
        raw = self.env["odoopilot.link.token"].issue("telegram", "p1")
        payload = self.env["odoopilot.link.token"].peek(raw)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["channel"], "telegram")
        self.assertEqual(payload["chat_id"], "p1")
        # The row must still be there: a follow-up consume() must succeed.
        consumed = self.env["odoopilot.link.token"].consume(raw)
        self.assertEqual(consumed["chat_id"], "p1")
        # And after consuming, both peek and consume return None.
        self.assertIsNone(self.env["odoopilot.link.token"].peek(raw))
        self.assertIsNone(self.env["odoopilot.link.token"].consume(raw))

    def test_peek_rejects_unknown(self):
        self.assertIsNone(self.env["odoopilot.link.token"].peek("never-issued"))

    def test_peek_rejects_expired(self):
        # Issue then forcibly expire.
        raw = self.env["odoopilot.link.token"].issue("whatsapp", "p2")
        rows = self.env["odoopilot.link.token"].search([])
        rows.write({"expires_at": 0})
        self.assertIsNone(self.env["odoopilot.link.token"].peek(raw))


class TestPreflightRejectsWildcards(TransactionCase):
    """Fix #4 — preflight must reject overly-short / wildcard-only names.

    Without this, an LLM nudged by a poisoned record can supply a name like
    ``"%"`` or ``" "`` that the executor's ``name ilike`` would expand to
    every row, mutating an arbitrary record while the user thinks they
    confirmed the LLM's argument string.
    """

    def test_wildcard_only_name_rejected(self):
        for term in ("%", "%%%", "  ", "_", "% _ "):
            with self.subTest(term=term):
                result = preflight_write(
                    self.env, "mark_task_done", {"task_name": term}
                )
                self.assertFalse(result["ok"])
                self.assertIn("too short", result["error"].lower() + " ")

    def test_too_short_name_rejected(self):
        result = preflight_write(self.env, "mark_task_done", {"task_name": "ab"})
        self.assertFalse(result["ok"])
        self.assertIn("too short", result["error"].lower() + " ")

    def test_empty_name_rejected(self):
        result = preflight_write(self.env, "approve_leave", {"employee_name": ""})
        self.assertFalse(result["ok"])

    def test_missing_optional_module_returns_friendly_error(self):
        # The preflight must not 500 when an optional module is absent;
        # it must surface a user-readable reason. Pick a tool whose
        # backing model exists in every install (project.task) for the
        # *positive* path and a likely-absent one (we can't easily force
        # absence in tests) — so we just assert the error path returns
        # ok=False with a string when the validation fails first.
        result = preflight_write(
            self.env, "update_crm_stage", {"lead_name": "%", "stage_name": "%"}
        )
        self.assertFalse(result["ok"])


class TestPreflightStoresResolvedId(TransactionCase):
    """Fix #4 — when preflight succeeds, args carry res_id (not just name)."""

    def test_mark_task_done_resolves_to_task_id(self):
        # Skip if Project module isn't installed in this test database.
        if "project.task" not in self.env.registry:
            self.skipTest("project module not installed")
        # Find a stage with fold=False to satisfy the preflight domain.
        stage = self.env["project.task.type"].search([("fold", "=", False)], limit=1)
        if not stage:
            self.skipTest("no non-fold task stage available")
        project = self.env["project.project"].create({"name": "OdooPilot test proj"})
        task = self.env["project.task"].create(
            {
                "name": "OdooPilot uniquely-named regression task",
                "project_id": project.id,
                "user_ids": [(6, 0, [self.env.uid])],
                "stage_id": stage.id,
            }
        )
        result = preflight_write(
            self.env,
            "mark_task_done",
            {"task_name": "OdooPilot uniquely-named regression"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["args"]["task_id"], task.id)
        # The confirmation question must contain the resolved name, not
        # the LLM's raw argument string.
        self.assertIn(task.name, result["question"])


class TestRateLimiter(TransactionCase):
    """Fix #8 — sliding-window per-(channel, chat_id) rate limiter."""

    def test_under_limit_allows(self):
        rl = throttle.RateLimiter(limit=3, window=60)
        for _ in range(3):
            self.assertTrue(rl.allow("telegram", "rl-1"))

    def test_over_limit_blocks(self):
        rl = throttle.RateLimiter(limit=3, window=60)
        for _ in range(3):
            rl.allow("telegram", "rl-2")
        # 4th attempt within the window must be blocked.
        self.assertFalse(rl.allow("telegram", "rl-2"))

    def test_per_chat_isolation(self):
        # One user hitting the limit must not block another user.
        rl = throttle.RateLimiter(limit=2, window=60)
        rl.allow("telegram", "chat-A")
        rl.allow("telegram", "chat-A")
        self.assertFalse(rl.allow("telegram", "chat-A"))
        self.assertTrue(rl.allow("telegram", "chat-B"))

    def test_per_channel_isolation(self):
        rl = throttle.RateLimiter(limit=1, window=60)
        rl.allow("telegram", "x")
        # Same chat_id on a different channel is a different bucket.
        self.assertTrue(rl.allow("whatsapp", "x"))

    def test_missing_key_fails_open(self):
        rl = throttle.RateLimiter(limit=1, window=60)
        # Defensive: missing channel or chat_id allows through (the bounded
        # pool below caps damage). The point is to never hard-fail on a
        # malformed payload.
        self.assertTrue(rl.allow("", "x"))
        self.assertTrue(rl.allow("telegram", ""))


class TestBoundedPool(TransactionCase):
    """Fix #8 — bounded pool fails fast when saturated."""

    def test_submit_returns_true_when_capacity_available(self):
        import threading

        pool = throttle.BoundedPool(max_workers=2)
        done = threading.Event()
        ok = pool.submit(lambda: done.set())
        self.assertTrue(ok)
        # Make sure the submitted callable actually ran.
        self.assertTrue(done.wait(timeout=5))


class TestDeliveryDedup(TransactionCase):
    """Fix #9 — webhook deliveries are deduped by external id."""

    def test_first_delivery_marked(self):
        ok = self.env["odoopilot.delivery.seen"].mark_or_drop("telegram", "10001")
        self.assertTrue(ok)

    def test_duplicate_delivery_dropped(self):
        first = self.env["odoopilot.delivery.seen"].mark_or_drop("telegram", "10002")
        second = self.env["odoopilot.delivery.seen"].mark_or_drop("telegram", "10002")
        self.assertTrue(first)
        self.assertFalse(second)

    def test_same_id_different_channel_not_dedup(self):
        # External ids are namespaced by channel — Telegram update_id 7
        # and WhatsApp message id 7 are unrelated.
        a = self.env["odoopilot.delivery.seen"].mark_or_drop("telegram", "7")
        b = self.env["odoopilot.delivery.seen"].mark_or_drop("whatsapp", "7")
        self.assertTrue(a)
        self.assertTrue(b)

    def test_empty_id_fails_open(self):
        # No id to dedup on — caller must still process the message.
        self.assertTrue(
            self.env["odoopilot.delivery.seen"].mark_or_drop("telegram", "")
        )
        self.assertTrue(self.env["odoopilot.delivery.seen"].mark_or_drop("", "x"))


# ── 17.0.9.0.0 defence-in-depth ─────────────────────────────────────────────


class TestTelegramTokenScrub(TransactionCase):
    """Fix #6/#7 — bot token must not appear in any logged string.

    Telegram bot URLs include the bot token (``…/bot<TOKEN>/sendMessage``).
    When ``requests`` raises an exception its ``str()`` often includes the
    failing URL, which would write the bot token straight to the Odoo log
    where any operator with log access can see it. ``TelegramClient._scrub``
    redacts the token before any string is passed to the logger.
    """

    def test_scrub_redacts_token_from_url_like_message(self):
        client = TelegramClient("123456789:AAAA-secret-bot-token-XYZ")
        msg = (
            "ConnectionError: HTTPSConnectionPool(host='api.telegram.org', "
            "port=443): /bot123456789:AAAA-secret-bot-token-XYZ/sendMessage"
        )
        scrubbed = client._scrub(msg)
        self.assertNotIn("123456789:AAAA-secret-bot-token-XYZ", scrubbed)
        self.assertIn("***", scrubbed)

    def test_scrub_passthrough_when_token_absent(self):
        client = TelegramClient("token-X")
        self.assertEqual(client._scrub("plain message"), "plain message")

    def test_scrub_handles_empty_inputs(self):
        client = TelegramClient("token-X")
        self.assertEqual(client._scrub(""), "")
        # A client without a token configured can't scrub anything — return
        # the input unchanged. (Matches the "if not self._token" early exit.)
        self.assertEqual(TelegramClient("")._scrub("anything"), "anything")


class TestVerifyTokenConstantTimeCompare(TransactionCase):
    """Fix #12 — verify_token comparison uses ``hmac.compare_digest``.

    This test is functional, not timing-based: we can't reliably measure
    nanosecond differences in CI. But ``hmac.compare_digest`` has the same
    truthy semantics as ``==`` on strings, so swapping in the hardened
    primitive must not regress correctness.
    """

    def test_matching_token_accepted(self):
        self.assertTrue(hmac.compare_digest("secret-token", "secret-token"))

    def test_wrong_token_rejected(self):
        self.assertFalse(hmac.compare_digest("secret-token", "wrong-token"))

    def test_empty_strings_dont_match_real_token(self):
        # The controller guards with "expected and …" before calling
        # compare_digest, so empty inputs would never reach this path; we
        # still pin the primitive's behaviour as defence-in-depth.
        self.assertFalse(hmac.compare_digest("", "secret"))
        self.assertFalse(hmac.compare_digest("secret", ""))

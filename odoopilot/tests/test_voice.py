"""Tests for the 17.0.16.0.0 voice-message support.

The interesting contract surfaces:

1. **STTClient construction** rejects unknown providers and missing
   keys with a clear ``STTUnavailable`` so the controller can show a
   user-facing reply rather than 500.

2. **STTClient input validation** caps audio size before the network
   call and returns "" for empty audio (no provider call burned).

3. **The duration-cap helper** ``_voice_too_long`` reads the operator's
   ``odoopilot.voice_max_duration_seconds`` parameter and rejects
   over-budget voice notes BEFORE we pay for the download.

4. **Token / key scrubbing** mirrors the same defence we have for the
   Telegram bot token: API keys never appear in logs.

We don't unit-test the actual HTTP calls to Groq / OpenAI here -- those
would be either a live network test (flaky, paid) or a heavy mock
(brittle). The integration story lives in the controller paths
themselves; the test below pins the stuff that's deterministic.
"""

from odoo.tests.common import TransactionCase

from ..services import stt


class TestSTTClientConstruction(TransactionCase):
    """Constructor must fail loudly for misconfiguration."""

    def test_unknown_provider_rejected(self):
        with self.assertRaises(stt.STTUnavailable) as cm:
            stt.STTClient(provider="anthropic", api_key="sk-x")
        self.assertIn("not supported", str(cm.exception).lower())

    def test_empty_provider_rejected(self):
        with self.assertRaises(stt.STTUnavailable):
            stt.STTClient(provider="", api_key="sk-x")

    def test_missing_api_key_rejected(self):
        # Provider valid, but no key: we don't want to attempt an
        # unauthenticated call to the STT endpoint.
        with self.assertRaises(stt.STTUnavailable) as cm:
            stt.STTClient(provider="openai", api_key="")
        self.assertIn("api key", str(cm.exception).lower())

    def test_default_model_per_provider(self):
        c1 = stt.STTClient(provider="groq", api_key="gsk_x")
        self.assertEqual(c1.model, "whisper-large-v3")
        c2 = stt.STTClient(provider="openai", api_key="sk-x")
        self.assertEqual(c2.model, "whisper-1")

    def test_explicit_model_override(self):
        c = stt.STTClient(provider="openai", api_key="sk-x", model="whisper-2")
        self.assertEqual(c.model, "whisper-2")


class TestSTTClientInputValidation(TransactionCase):
    """``transcribe()`` short-circuits on empty input + caps oversized."""

    def setUp(self):
        super().setUp()
        self.client = stt.STTClient(provider="groq", api_key="gsk_test")

    def test_empty_audio_returns_empty_string(self):
        # Empty bytes return "" without any HTTP call attempted.
        self.assertEqual(self.client.transcribe(b"", mime_type="audio/ogg"), "")

    def test_oversize_audio_raises_unavailable(self):
        oversize = b"\0" * (stt._MAX_AUDIO_BYTES + 1)
        with self.assertRaises(stt.STTUnavailable) as cm:
            self.client.transcribe(oversize, mime_type="audio/ogg")
        self.assertIn("too large", str(cm.exception).lower())


class TestSTTClientScrub(TransactionCase):
    """API key must not appear in logged exception strings."""

    def test_scrub_redacts_key(self):
        client = stt.STTClient(provider="groq", api_key="gsk_secret_abc123")
        msg = (
            "ConnectionError: HTTPSConnectionPool(host='api.groq.com', "
            "port=443): /v1/audio/transcriptions Authorization: Bearer "
            "gsk_secret_abc123"
        )
        scrubbed = client._scrub(msg)
        self.assertNotIn("gsk_secret_abc123", scrubbed)
        self.assertIn("***", scrubbed)

    def test_scrub_passthrough_when_key_absent(self):
        client = stt.STTClient(provider="groq", api_key="gsk_x")
        self.assertEqual(client._scrub("plain message"), "plain message")


class TestVoiceDurationCap(TransactionCase):
    """The duration cap helper reads the operator's config parameter."""

    def setUp(self):
        super().setUp()
        # Import lazily so the controllers module's side-effects don't
        # contaminate test discovery.
        from ..controllers.main import _voice_too_long

        self._voice_too_long = _voice_too_long

    def _set_cap(self, seconds):
        self.env["ir.config_parameter"].sudo().set_param(
            "odoopilot.voice_max_duration_seconds", str(seconds)
        )

    def test_under_cap_allowed(self):
        self._set_cap(60)
        self.assertFalse(self._voice_too_long(self.env, 30))

    def test_over_cap_rejected(self):
        self._set_cap(60)
        self.assertTrue(self._voice_too_long(self.env, 90))

    def test_at_cap_allowed(self):
        # Exactly at the cap is fine; only strictly greater is rejected.
        self._set_cap(60)
        self.assertFalse(self._voice_too_long(self.env, 60))

    def test_zero_or_missing_duration_passes_through(self):
        # Telegram sometimes omits duration on audio attachments;
        # treat as 0 (allow). The real protection is in
        # _MAX_AUDIO_BYTES on the download path.
        self._set_cap(60)
        self.assertFalse(self._voice_too_long(self.env, 0))
        self.assertFalse(self._voice_too_long(self.env, None))

    def test_invalid_cap_falls_back_to_60(self):
        # If an operator typed a non-number into the config field, we
        # default to 60s rather than crashing the webhook.
        self.env["ir.config_parameter"].sudo().set_param(
            "odoopilot.voice_max_duration_seconds", "not a number"
        )
        self.assertFalse(self._voice_too_long(self.env, 30))
        self.assertTrue(self._voice_too_long(self.env, 90))


class TestSTTClientNoneOrUnconfigured(TransactionCase):
    """``_stt_client_or_none`` returns None when voice is disabled.

    The controller relies on this so it can fall back to a polite
    "voice not enabled" reply rather than a 500.
    """

    def setUp(self):
        super().setUp()
        from ..controllers.main import _stt_client_or_none

        self._stt_client_or_none = _stt_client_or_none

    def _set_voice(self, enabled):
        self.env["ir.config_parameter"].sudo().set_param(
            "odoopilot.voice_enabled", "True" if enabled else "False"
        )

    def test_disabled_returns_none(self):
        self._set_voice(False)
        self.assertIsNone(self._stt_client_or_none(self.env))

    def test_enabled_but_no_provider_returns_none(self):
        # Voice flag on but no STT provider configured -- the
        # constructor raises STTUnavailable, which the helper catches
        # and converts to None.
        self._set_voice(True)
        self.env["ir.config_parameter"].sudo().set_param("odoopilot.stt_provider", "")
        self.env["ir.config_parameter"].sudo().set_param("odoopilot.stt_api_key", "")
        self.assertIsNone(self._stt_client_or_none(self.env))

    def test_enabled_with_provider_and_key_returns_client(self):
        self._set_voice(True)
        self.env["ir.config_parameter"].sudo().set_param(
            "odoopilot.stt_provider", "groq"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "odoopilot.stt_api_key", "gsk_test_key"
        )
        client = self._stt_client_or_none(self.env)
        self.assertIsNotNone(client)
        self.assertEqual(client.provider, "groq")

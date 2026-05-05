"""Speech-to-text client for inbound Telegram / WhatsApp voice messages.

Why this exists
---------------

Both messaging platforms deliver voice notes as audio attachments
(Telegram = OGG/Opus in ``message.voice``; WhatsApp = OGG/Opus in
``messages[].audio``). The killer use case the listing leads with --
a warehouse picker, a driver, anyone whose hands aren't free to type
-- only works if those audio attachments make it into the existing
text-based agent loop. This module is the bridge: download → transcribe
→ hand off the text to ``OdooPilotAgent.handle_message`` as if the user
had typed it.

Provider matrix
---------------

We support two STT backends, both behind the OpenAI-compatible
``audio/transcriptions`` endpoint shape:

* ``groq`` (default when available) -- ``whisper-large-v3``, free tier
  with generous limits, ~10x faster than OpenAI.
* ``openai`` -- ``whisper-1``, the reference implementation. ~$0.006
  per minute of audio.

Other providers (Anthropic doesn't ship STT; Ollama can run
``whisper.cpp`` locally) are out of scope for v1. Operators on
``anthropic`` or ``ollama`` for their LLM can still enable voice by
configuring a Groq or OpenAI key in the dedicated STT settings -- the
two clients are independent.

Cost / DoS guard
----------------

Voice messages double the per-message cost (one STT call + one LLM
call). The existing per-(channel, chat_id) sliding-window rate limit
already covers this -- 30 messages/hour is 30 messages, voice or text.
A more aggressive operator can lower ``odoopilot.rate_limit_per_hour``
or set ``odoopilot.voice_max_duration_seconds`` to bound the longest
single transcription job we'll accept.
"""

from __future__ import annotations

import logging

import requests

_logger = logging.getLogger(__name__)


# Default model per provider.
DEFAULTS = {
    "groq": "whisper-large-v3",
    "openai": "whisper-1",
}

# OpenAI-compatible audio transcription endpoint per provider.
ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/audio/transcriptions",
    "openai": "https://api.openai.com/v1/audio/transcriptions",
}

# Maximum file size we'll send to the STT provider. Guards against a
# malicious client sending a huge audio file to drive costs or stall
# the worker pool. Both Telegram and WhatsApp cap voice notes well
# below this in practice.
_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB

# Default safety cap on transcribable audio length. Operators can tune
# via ``odoopilot.voice_max_duration_seconds``; the actual check
# happens in the controller before download (using the metadata the
# platform sends), so we don't even pay the bandwidth for an
# over-budget message.
DEFAULT_MAX_DURATION_SECONDS = 60


class STTUnavailable(Exception):
    """Raised when the configured provider doesn't support STT.

    The dispatcher catches this and falls back to a polite "voice not
    enabled" reply rather than dropping the message silently.
    """


class STTClient:
    """Thin wrapper around the OpenAI-compatible /audio/transcriptions API.

    Construct once per request; transcribe with :meth:`transcribe`.
    """

    def __init__(self, provider: str, api_key: str, model: str = ""):
        self.provider = (provider or "").lower()
        self._api_key = api_key or ""
        self.model = model or DEFAULTS.get(self.provider, "")
        if self.provider not in ENDPOINTS:
            raise STTUnavailable(
                f"STT provider '{self.provider}' is not supported. "
                f"Configure 'groq' or 'openai' in Settings -> OdooPilot."
            )
        if not self._api_key:
            raise STTUnavailable(
                f"STT provider '{self.provider}' requires an API key. "
                f"Set 'odoopilot.stt_api_key' in Settings -> OdooPilot."
            )

    def transcribe(
        self, audio_bytes: bytes, mime_type: str, filename: str = "voice.ogg"
    ) -> str:
        """Send the audio to the provider and return the transcribed text.

        Returns an empty string if the provider returned no text (silence,
        unintelligible audio). Raises ``STTUnavailable`` on quota /
        network errors -- the caller should reply to the user with a
        friendly fallback rather than crashing.

        Args:
            audio_bytes: Raw audio file content (OGG/Opus from Telegram
                or WhatsApp; OpenAI's Whisper accepts ogg, m4a, mp3,
                mp4, mpeg, mpga, wav, webm).
            mime_type: Content-Type advertised by the platform; passed
                through as the multipart filename's content-type.
            filename: Filename to advertise in the multipart upload.
                Whisper looks at the extension here; we default to
                ``voice.ogg`` since both platforms ship OGG/Opus.
        """
        if not audio_bytes:
            return ""
        if len(audio_bytes) > _MAX_AUDIO_BYTES:
            raise STTUnavailable(
                f"Audio too large ({len(audio_bytes):,} bytes; cap "
                f"{_MAX_AUDIO_BYTES:,}). Ask for a shorter message."
            )

        url = ENDPOINTS[self.provider]
        headers = {"Authorization": f"Bearer {self._api_key}"}
        files = {"file": (filename, audio_bytes, mime_type or "audio/ogg")}
        data = {
            "model": self.model,
            # response_format=text gives us a plain string body which is
            # cheaper to parse than a JSON envelope. Both providers
            # support it.
            "response_format": "text",
        }
        try:
            resp = requests.post(
                url, headers=headers, files=files, data=data, timeout=30
            )
        except Exception as e:
            _logger.error(
                "STT request failed (%s): %s: %s",
                self.provider,
                type(e).__name__,
                self._scrub(str(e)),
            )
            raise STTUnavailable(f"STT request failed: {type(e).__name__}") from e

        if resp.status_code >= 400:
            _logger.error(
                "STT %s returned %s: %s",
                self.provider,
                resp.status_code,
                self._scrub(resp.text[:500]),
            )
            raise STTUnavailable(f"STT provider returned HTTP {resp.status_code}")

        # Plain-text response when ``response_format=text``.
        text = (resp.text or "").strip()
        return text

    def _scrub(self, message: str) -> str:
        """Redact the API key from any string before logging.

        Mirrors the same defence in :class:`services.telegram.TelegramClient`
        -- providers occasionally echo the auth header into error messages.
        """
        if not self._api_key or not message:
            return message
        return message.replace(self._api_key, "***")

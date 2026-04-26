"""One-shot link tokens used to bind a Telegram/WhatsApp chat to an Odoo user.

Security properties of this model:

* The raw token is **never persisted** — only its SHA-256 digest. Even an
  attacker with read access to the Odoo database cannot replay a token.
* Tokens are **single-use**: ``consume`` deletes the row in the same
  transaction, so a stolen-after-use token has no value.
* Tokens **expire** after a short TTL (default 1 hour) and are
  garbage-collected by a periodic cron.
* Lookups are O(1) via the indexed digest column.

The previous design stored the raw token in ``ir.config_parameter`` keyed
by token, which (a) leaked the token to anyone with config-read rights and
(b) created an unbounded number of system parameters.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from odoo import api, fields, models

# How long a freshly-issued link token remains valid (seconds).
_TOKEN_TTL_SECONDS = 3600


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class OdooPilotLinkToken(models.Model):
    _name = "odoopilot.link.token"
    _description = "OdooPilot one-shot account linking token"
    _rec_name = "channel"

    # SHA-256 hex digest of the raw token. The raw token is shown to the
    # user exactly once (in the link URL) and never stored.
    token_digest = fields.Char(required=True, index=True)
    channel = fields.Char(required=True)
    chat_id = fields.Char(required=True)
    expires_at = fields.Integer(
        required=True, help="Unix timestamp at which this token expires."
    )
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    _sql_constraints = [
        (
            "unique_digest",
            "UNIQUE(token_digest)",
            "Token digest must be unique.",
        ),
    ]

    # ------------------------------------------------------------------
    # Issuance and consumption
    # ------------------------------------------------------------------

    @api.model
    def issue(self, channel: str, chat_id: str) -> str:
        """Generate a fresh token, persist its digest, return the raw token.

        The raw token is what goes into the link URL. The caller must NOT
        log or store it anywhere.
        """
        # Strip any pending tokens for this exact (channel, chat_id) so the
        # latest /link request is the only one that can be redeemed.
        self.search(
            [("channel", "=", channel), ("chat_id", "=", chat_id)]
        ).unlink()

        raw = secrets.token_urlsafe(32)  # ~43 chars, 256 bits of entropy
        self.create(
            {
                "token_digest": _digest(raw),
                "channel": channel,
                "chat_id": chat_id,
                "expires_at": int(time.time()) + _TOKEN_TTL_SECONDS,
            }
        )
        return raw

    @api.model
    def consume(self, raw_token: str) -> dict | None:
        """Look up and atomically delete a token. Returns its payload or None.

        Returns ``None`` if the token is unknown, expired, or already used.
        Always deletes the row when found, even if expired, so tokens
        cannot be brute-forced via repeated lookups.
        """
        if not raw_token:
            return None
        record = self.search(
            [("token_digest", "=", _digest(raw_token))], limit=1
        )
        if not record:
            return None
        payload = {
            "channel": record.channel,
            "chat_id": record.chat_id,
            "expires_at": record.expires_at,
        }
        record.unlink()  # one-shot — invalid after this call regardless of expiry
        if int(time.time()) > payload["expires_at"]:
            return None
        return payload

    @api.model
    def _gc_expired(self):
        """Cron entry-point: remove expired link tokens."""
        now = int(time.time())
        self.search([("expires_at", "<", now)]).unlink()

"""Idempotency table for webhook deliveries.

Both Telegram and WhatsApp retry deliveries on 5xx responses and timeouts.
Without deduplication, a redelivered message will run the full pipeline a
second time — wasting an LLM call at minimum, and at worst (if a write tool
ran but the HTTP 200 was lost on the first attempt) re-running the staged
write through ``execute_confirmed``.

Each accepted delivery records ``(channel, external_id)`` where
``external_id`` is Telegram's ``update_id`` or WhatsApp's per-message
``id``. The unique SQL constraint on the pair makes :func:`mark_or_drop`
atomic: when N concurrent retries arrive simultaneously, exactly one of
the N inserts succeeds (returns ``True``) and the others raise
``IntegrityError`` (returns ``False``).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# How long to keep dedup rows. Telegram retries for at most a few hours,
# WhatsApp similarly; 24h is a generous bound that keeps the table small.
_TTL_HOURS = 24


class OdooPilotDeliverySeen(models.Model):
    _name = "odoopilot.delivery.seen"
    _description = "OdooPilot: webhook delivery idempotency record"

    channel = fields.Char(required=True)
    external_id = fields.Char(required=True, index=True)
    seen_at = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        (
            "unique_channel_external",
            "UNIQUE(channel, external_id)",
            "A delivery with this id has already been recorded.",
        ),
    ]

    @api.model
    def mark_or_drop(self, channel: str, external_id: str) -> bool:
        """Record a delivery atomically. Returns True for new, False for dup.

        Implemented as ``INSERT … UNIQUE``: the database guarantees only one
        of N concurrent callers with the same ``(channel, external_id)`` pair
        succeeds. The losing callers see ``psycopg2.IntegrityError`` and
        return ``False`` — meaning "already processed; drop this delivery."
        """
        if not channel or not external_id:
            # No id to dedupe on — fail open. The caller should still process
            # the message; the rate limiter and pool above bound the damage.
            return True
        try:
            with self.env.cr.savepoint():
                self.create({"channel": channel, "external_id": external_id})
            return True
        except psycopg2.IntegrityError:
            _logger.info(
                "OdooPilot: dropping duplicate %s delivery %s",
                channel,
                external_id,
            )
            return False

    @api.model
    def _gc_old(self) -> None:
        """Cron entry-point: delete dedup rows older than the TTL."""
        cutoff = fields.Datetime.now() - timedelta(hours=_TTL_HOURS)
        self.search([("seen_at", "<", cutoff)]).unlink()

"""Post-migration for OdooPilot 17.0.7.0.0 (security release).

Clears any in-flight write confirmations from before this release. Older
versions did not bind the Yes/No button to a per-write nonce, so a pending
write that survives the upgrade could be confirmed without the new check.
We drop them; users simply re-issue the request to the bot.

Also wipes link tokens that were stored in ``ir.config_parameter`` under
``odoopilot.link_token.*`` keys, since those raw tokens are now considered
sensitive and should never have been persisted in plaintext. Users with
pending links must run ``/link`` again.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE odoopilot_session
        SET pending_tool = NULL,
            pending_args = NULL,
            pending_nonce = NULL
        WHERE pending_tool IS NOT NULL
        """
    )
    _logger.info(
        "OdooPilot upgrade: cleared %d in-flight pending write(s) "
        "(pre-7.0 confirmations did not carry a per-write nonce).",
        cr.rowcount,
    )

    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key LIKE 'odoopilot.link_token.%%'"
    )
    _logger.info(
        "OdooPilot upgrade: removed %d legacy link-token system parameter(s) "
        "(link tokens now live in odoopilot.link.token with hashed storage).",
        cr.rowcount,
    )

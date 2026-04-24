"""Proactive notification helpers for OdooPilot cron jobs."""

from __future__ import annotations

import logging
from datetime import date

from .telegram import TelegramClient
from .whatsapp import WhatsAppClient

_logger = logging.getLogger(__name__)


def _get_client_for_identity(env, identity):
    """Return the right messaging client for the given identity's channel, or None."""
    cfg = env["ir.config_parameter"].sudo()
    channel = identity.channel

    if channel == "telegram":
        if not cfg.get_param("odoopilot.telegram_enabled"):
            return None
        token = cfg.get_param("odoopilot.telegram_bot_token")
        return TelegramClient(token) if token else None

    if channel == "whatsapp":
        if not cfg.get_param("odoopilot.whatsapp_enabled"):
            return None
        phone_number_id = cfg.get_param("odoopilot.whatsapp_phone_number_id")
        access_token = cfg.get_param("odoopilot.whatsapp_access_token")
        return (
            WhatsAppClient(phone_number_id, access_token)
            if phone_number_id and access_token
            else None
        )

    return None


def send_task_digest(env) -> int:
    """Send a daily task digest to every linked user who has tasks due today or overdue.

    Supports both Telegram and WhatsApp channels.
    Returns the number of users notified.
    """
    cfg = env["ir.config_parameter"].sudo()
    if not cfg.get_param("odoopilot.notify_task_digest"):
        return 0

    if "project.task" not in env.registry:
        _logger.info("OdooPilot task digest skipped: Project module not installed")
        return 0

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    notified = 0

    identities = env["odoopilot.identity"].sudo().search([("active", "=", True)])

    for identity in identities:
        client = _get_client_for_identity(env, identity)
        if not client:
            continue

        try:
            user_env = env(user=identity.user_id.id)
            tasks = user_env["project.task"].search(
                [
                    ("user_ids", "in", [identity.user_id.id]),
                    ("stage_id.fold", "=", False),
                    ("date_deadline", "!=", False),
                    ("date_deadline", "<=", today_str),
                ],
                order="date_deadline asc",
                limit=15,
            )
            if not tasks:
                continue

            overdue = [t for t in tasks if str(t.date_deadline)[:10] < today_str]
            due_today = [t for t in tasks if str(t.date_deadline)[:10] == today_str]

            lines = []
            for t in overdue:
                lines.append(
                    f"⚠️ {t.name}" + (f" [{t.project_id.name}]" if t.project_id else "")
                )
            for t in due_today:
                lines.append(
                    f"📅 {t.name}" + (f" [{t.project_id.name}]" if t.project_id else "")
                )

            summary_parts = []
            if overdue:
                summary_parts.append(f"{len(overdue)} overdue")
            if due_today:
                summary_parts.append(f"{len(due_today)} due today")

            msg = (
                f"<b>Good morning, {identity.user_id.name}! 👋</b>\n\n"
                f"You have <b>{', '.join(summary_parts)}</b>:\n\n"
                + "\n".join(lines)
                + "\n\nReply with a question or action, e.g. <i>mark task X as done</i>."
            )
            client.send_message(identity.chat_id, msg)
            notified += 1
        except Exception:
            _logger.exception(
                "Task digest failed for identity %s (user %s)",
                identity.id,
                identity.user_id.name,
            )

    _logger.info("OdooPilot task digest: notified %d user(s)", notified)
    return notified


def send_invoice_alerts(env) -> int:
    """Send overdue invoice alerts to linked users who have accounting access.

    Supports both Telegram and WhatsApp channels.
    Returns the number of users notified.
    """
    cfg = env["ir.config_parameter"].sudo()
    if not cfg.get_param("odoopilot.notify_invoice_alerts"):
        return 0

    if "account.move" not in env.registry:
        _logger.info(
            "OdooPilot invoice alerts skipped: Accounting module not installed"
        )
        return 0

    today_str = date.today().strftime("%Y-%m-%d")
    notified = 0

    identities = env["odoopilot.identity"].sudo().search([("active", "=", True)])

    for identity in identities:
        client = _get_client_for_identity(env, identity)
        if not client:
            continue

        try:
            user_env = env(user=identity.user_id.id)

            if not (
                user_env["res.users"]
                .browse(identity.user_id.id)
                .has_group("account.group_account_invoice")
            ):
                continue

            invoices = user_env["account.move"].search(
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "!=", "paid"),
                    ("invoice_date_due", "<", today_str),
                ],
                order="invoice_date_due asc",
                limit=10,
            )
            if not invoices:
                continue

            total = sum(invoices.mapped("amount_residual"))
            currency = invoices[0].currency_id.symbol if invoices else ""
            oldest_days = (
                (date.today() - invoices[0].invoice_date_due).days
                if invoices[0].invoice_date_due
                else 0
            )

            lines = [
                f"• {i.name} — {i.partner_id.name} — {currency}{i.amount_residual:,.2f}"
                f" (due {i.invoice_date_due})"
                for i in invoices[:5]
            ]
            if len(invoices) > 5:
                lines.append(f"  … and {len(invoices) - 5} more")

            msg = (
                f"<b>📋 Overdue Invoice Alert</b>\n\n"
                f"<b>{len(invoices)} invoice(s)</b> are overdue, "
                f"totalling <b>{currency}{total:,.2f}</b>.\n"
                f"Oldest: {oldest_days} days overdue.\n\n"
                + "\n".join(lines)
                + "\n\nReply <i>show overdue invoices</i> for the full list."
            )
            client.send_message(identity.chat_id, msg)
            notified += 1
        except Exception:
            _logger.exception(
                "Invoice alert failed for identity %s (user %s)",
                identity.id,
                identity.user_id.name,
            )

    _logger.info("OdooPilot invoice alerts: notified %d user(s)", notified)
    return notified

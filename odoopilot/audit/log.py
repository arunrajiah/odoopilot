from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from odoopilot.storage.models import AuditLogEntry

logger = logging.getLogger(__name__)


class AuditLogger:
    """Writes a structured audit record for every tool call.

    Keeping the audit log is the core trust story for a guided-write agent:
    every action (and every confirmation) is traceable to a specific user.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def log(
        self,
        *,
        user_id: int,
        tool: str,
        arguments: dict[str, Any],
        result: str,
        confirmed: bool | None = None,
    ) -> None:
        entry = AuditLogEntry(
            odoo_user_id=user_id,
            tool=tool,
            arguments=json.dumps(arguments, default=str),
            result=result[:2000],  # truncate very long results
            confirmed=confirmed,
        )
        try:
            async with self._session_factory() as session:
                session.add(entry)
                await session.commit()
        except Exception:
            logger.exception("Failed to write audit log entry for tool=%s user=%s", tool, user_id)

    async def get_recent(
        self,
        *,
        user_id: int | None = None,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        async with self._session_factory() as session:
            stmt = select(AuditLogEntry).order_by(AuditLogEntry.created_at.desc()).limit(limit)
            if user_id is not None:
                stmt = stmt.where(AuditLogEntry.odoo_user_id == user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

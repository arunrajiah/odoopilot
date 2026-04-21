from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from odoopilot.storage.models import ChannelIdentity, LinkingToken, UserIdentity

logger = logging.getLogger(__name__)

_TOKEN_EXPIRY_HOURS = 1


class IdentityStore:
    """Manages the (channel, chat_id) → Odoo user mapping and linking tokens."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], secret_key: str) -> None:
        self._session_factory = session_factory
        self._secret = secret_key.encode()

    async def get_identity(self, channel: str, chat_id: str) -> UserIdentity | None:
        """Look up the linked Odoo user for a given channel + chat ID."""
        async with self._session_factory() as session:
            stmt = select(ChannelIdentity).where(
                ChannelIdentity.channel == channel,
                ChannelIdentity.chat_id == chat_id,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return UserIdentity(
                odoo_user_id=row.odoo_user_id,
                odoo_password=row.odoo_password,
                odoo_username=row.odoo_username,
                display_name=row.display_name,
            )

    async def link_user(
        self,
        *,
        channel: str,
        chat_id: str,
        odoo_user_id: int,
        odoo_username: str,
        odoo_password: str,
        display_name: str,
    ) -> None:
        """Create or update the identity mapping for a chat."""
        async with self._session_factory() as session:
            stmt = select(ChannelIdentity).where(
                ChannelIdentity.channel == channel,
                ChannelIdentity.chat_id == chat_id,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                row.odoo_user_id = odoo_user_id
                row.odoo_username = odoo_username
                row.odoo_password = odoo_password
                row.display_name = display_name
            else:
                session.add(
                    ChannelIdentity(
                        channel=channel,
                        chat_id=chat_id,
                        odoo_user_id=odoo_user_id,
                        odoo_username=odoo_username,
                        odoo_password=odoo_password,
                        display_name=display_name,
                    )
                )
            await session.commit()

    async def create_linking_token(self, channel: str, chat_id: str) -> str:
        """Generate a one-time linking token for the given chat."""
        raw = secrets.token_urlsafe(32)
        sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        token = f"{raw}.{sig}"

        expires_at = datetime.now(tz=UTC) + timedelta(hours=_TOKEN_EXPIRY_HOURS)
        async with self._session_factory() as session:
            session.add(
                LinkingToken(
                    token=token,
                    channel=channel,
                    chat_id=chat_id,
                    expires_at=expires_at,
                )
            )
            await session.commit()
        return token

    async def consume_linking_token(self, token: str) -> tuple[str, str] | None:
        """Validate and consume a linking token. Returns (channel, chat_id) or None."""
        async with self._session_factory() as session:
            stmt = select(LinkingToken).where(
                LinkingToken.token == token,
                LinkingToken.used.is_(False),  # SQLAlchemy column comparison, not Python bool
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            if row.expires_at.replace(tzinfo=UTC) < datetime.now(tz=UTC):
                return None
            row.used = True
            await session.commit()
            return row.channel, row.chat_id

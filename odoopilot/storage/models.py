from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ChannelIdentity(Base):
    """Maps a (channel, chat_id) pair to an Odoo user."""

    __tablename__ = "channel_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(100), nullable=False)
    odoo_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    odoo_password: Mapped[str] = mapped_column(String(500), nullable=False)
    odoo_username: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_channel_identity_lookup", "channel", "chat_id", unique=True),)


class UserIdentity:
    """In-memory view of a linked user — not persisted directly."""

    def __init__(
        self,
        odoo_user_id: int,
        odoo_password: str,
        odoo_username: str,
        display_name: str,
    ) -> None:
        self.odoo_user_id = odoo_user_id
        self.odoo_password = odoo_password
        self.odoo_username = odoo_username
        self.display_name = display_name


class AuditLogEntry(Base):
    """Audit record for every tool call."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    odoo_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confirmed: Mapped[bool | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PendingConfirmation(Base):
    """Stores a write tool invocation pending user confirmation."""

    __tablename__ = "pending_confirmation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_arguments: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_pending_confirmation_chat", "channel", "chat_id"),)


class LinkingToken(Base):
    """One-time token for linking a Telegram chat to an Odoo user."""

    __tablename__ = "linking_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

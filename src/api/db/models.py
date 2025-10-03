"""
SQLAlchemy Models for COM-AI v3 (MEM-001)
Task ID: MEM-001
Component: Database Layer (PostgreSQL authoritative)

Tables:
- users: User accounts with external_id mapping
- sessions: Conversation sessions with metadata
- messages: Individual messages within sessions
- usage_log: Telemetry for /api/health/usage aggregations
- provider_preferences: Per-user provider defaults
- rate_limits: Token-bucket quota tracking
- provider_health: Provider diagnostics for /api/health/providers/detail

Follows Phase 2A spec: PostgreSQL as authoritative store,
dual-write to Firestore (mirror) implemented separately.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Text, String, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models - enables async attribute loading"""
    pass


class User(Base):
    """
    User accounts table.
    Supports multi-tenant auth (single-tenant now, multi-tenant ready).
    """
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key (UUID)"
    )
    external_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="External identity (e.g., OAuth sub, API key hash)"
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        comment="User role (user, admin, etc.)"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Account creation timestamp (UTC)"
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    preferences: Mapped[Optional["ProviderPreference"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    rate_limits: Mapped[Optional["RateLimit"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, external_id='{self.external_id}', role='{self.role}')>"


class Session(Base):
    """
    Conversation sessions table.
    Tracks user interaction sessions with metadata.
    """
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Session ID (UUID)"
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID"
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Session title (optional)"
    )
    session_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        default=dict,
        comment="Session metadata (JSONB)"
    )
    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Session start time (UTC)"
    )
    last_active_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Last activity timestamp (UTC)"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, title='{self.title}')>"


class Message(Base):
    """
    Individual messages within sessions.
    Captures role, content, provider used, and performance metrics.
    """
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
        Index("ix_messages_request_id", "request_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Message ID (UUID)"
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent session ID"
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Message role (user, assistant, system)"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message content"
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Provider used (openai, anthropic, gemini)"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Model used (e.g., gpt-4, claude-opus-4-1)"
    )
    tokens_in: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Input tokens consumed"
    )
    tokens_out: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Output tokens generated"
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Response latency in milliseconds"
    )
    request_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        comment="Request ID for tracing"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Message creation timestamp (UTC)"
    )

    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role='{self.role}', provider='{self.provider}')>"


class UsageLog(Base):
    """
    Usage telemetry log.
    Drives /api/health/usage aggregations.
    One record per request with provider, model, status, latency, tokens, cost.
    """
    __tablename__ = "usage_log"
    __table_args__ = (
        Index("ix_usage_log_created_at", "created_at"),
        Index("ix_usage_log_user_provider", "user_id", "provider"),
        Index("ix_usage_log_status", "status"),
    )

    request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Request ID (UUID, PK)"
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        comment="User who made the request"
    )
    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Provider used"
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Model used"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Request status (success, error, timeout)"
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Request latency in milliseconds"
    )
    tokens_in: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Input tokens"
    )
    tokens_out: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Output tokens"
    )
    cost_usd: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6),
        comment="Cost in USD (6 decimal precision)"
    )
    fallback_chain: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Fallback chain if primary provider failed"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Log entry timestamp (UTC)"
    )

    def __repr__(self) -> str:
        return f"<UsageLog(request_id={self.request_id}, provider='{self.provider}', status='{self.status}')>"


class ProviderPreference(Base):
    """
    Per-user provider preferences.
    Stores default provider, model, temperature, fallback policy.
    PostgreSQL authoritative; mirrored to Firestore for UI reads.
    """
    __tablename__ = "provider_preferences"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User ID (PK, FK)"
    )
    default_provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Default provider (openai, anthropic, gemini)"
    )
    default_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Default model for the provider"
    )
    temperature: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        comment="Default temperature (0.00 - 2.00)"
    )
    fallback_policy: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Fallback policy configuration (JSONB)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Last update timestamp (UTC)"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<ProviderPreference(user_id={self.user_id}, default_provider='{self.default_provider}')>"


class RateLimit(Base):
    """
    Token-bucket rate limits per user.
    Tracks requests and tokens within time windows.
    Supports daily/monthly caps and per-provider limits.
    """
    __tablename__ = "rate_limits"
    __table_args__ = (
        Index("ix_rate_limits_window", "user_id", "window_start", "window_end"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User ID (PK, FK)"
    )
    window_start: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Rate limit window start (UTC)"
    )
    window_end: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Rate limit window end (UTC)"
    )
    requests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Requests consumed in window"
    )
    tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Tokens consumed in window"
    )
    limit_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Max requests allowed in window"
    )
    limit_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Max tokens allowed in window"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="rate_limits")

    def __repr__(self) -> str:
        return f"<RateLimit(user_id={self.user_id}, requests={self.requests}/{self.limit_requests})>"


class ProviderHealth(Base):
    """
    Provider health diagnostics.
    Drives /api/health/providers/detail endpoint.
    Tracks latency, success/error timestamps, and error messages.
    """
    __tablename__ = "provider_health"
    __table_args__ = (
        Index("ix_provider_health_timestamp", "provider_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Auto-increment PK"
    )
    provider_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Provider identifier (openai, anthropic, gemini)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        comment="Health check timestamp (UTC)"
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Response latency in milliseconds"
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Health check success flag"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Error message if health check failed"
    )

    def __repr__(self) -> str:
        status = "OK" if self.success else "ERROR"
        return f"<ProviderHealth(provider_id='{self.provider_id}', status='{status}')>"
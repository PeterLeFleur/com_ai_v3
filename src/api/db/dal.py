"""
Data Access Layer (DAL) for COM-AI v3
Provides async database operations for PostgreSQL (authoritative store).
"""

from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
import json
import os
import asyncio
import logging

from sqlalchemy import select, update, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert, JSONB

from src.api.db.models import (
    User,
    Session,
    Message,
    UsageLog,
    ProviderHealth
)

# Firestore mirror (lazy, behind flag)
try:
    from src.firebase.client import init_firebase
    from src.firebase.mirror import FirestoreMirror
except ImportError:
    # Keep DAL importable even if Firebase deps not installed
    init_firebase = None
    FirestoreMirror = None

logger = logging.getLogger(__name__)
_firestore_mirror = None


def _is_truthy(val: str | None) -> bool:
    """Check if a string value represents a truthy state."""
    if val is None:
        return False
    return val.strip().lower() in ("1", "true", "yes", "on")


def _mirror_enabled() -> bool:
    """
    Read FIREBASE_MIRROR_ENABLED at call-time so later .env loads 
    or process env changes are respected.
    """
    return _is_truthy(os.getenv("FIREBASE_MIRROR_ENABLED", "false"))


def _get_mirror():
    """
    Lazily create and cache the FirestoreMirror instance.
    Returns None if mirroring is disabled or firebase not available.
    """
    global _firestore_mirror
    
    if not _mirror_enabled():
        return None
    
    if init_firebase is None or FirestoreMirror is None:
        logger.warning("FIREBASE_MIRROR_ENABLED=true but firebase modules unavailable")
        return None
    
    if _firestore_mirror is None:
        try:
            _firestore_mirror = FirestoreMirror(init_firebase(), enable_debug=True)
            logger.info("Firestore mirror initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore mirror: {e}", exc_info=True)
            return None
    
    return _firestore_mirror


def _schedule_mirror(coro, what: str):
    """Fire-and-forget scheduling. DAL must never await mirror writes."""
    try:
        asyncio.create_task(coro)
    except Exception as e:
        logger.error(f"Mirror schedule failed for {what}: {e}", exc_info=True)


# ============================================================================
# USER FUNCTIONS
# ============================================================================

async def create_user(
    db: AsyncSession,
    external_id: str,
    role: str = "user"
) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        external_id: External identifier (e.g., OAuth ID, API key hash)
        role: User role (default: "user")
    
    Returns:
        Created User instance
    """
    user = User(
        id=uuid4(),
        external_id=external_id,
        role=role,
        created_at=datetime.utcnow()
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_external_id(
    db: AsyncSession,
    external_id: str
) -> Optional[User]:
    """
    Retrieve user by external_id.
    
    Args:
        db: Database session
        external_id: External identifier
    
    Returns:
        User instance or None if not found
    """
    result = await db.execute(
        select(User).where(User.external_id == external_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(
    db: AsyncSession,
    external_id: str,
    role: str = "user"
) -> User:
    """
    Get existing user or create new one.
    
    Args:
        db: Database session
        external_id: External identifier
        role: User role (used only if creating new user)
    
    Returns:
        User instance (existing or newly created)
    """
    user = await get_user_by_external_id(db, external_id)
    if user is None:
        user = await create_user(db, external_id, role)
    return user


# ============================================================================
# SESSION FUNCTIONS
# ============================================================================

async def create_session(
    db: AsyncSession,
    user_id: UUID,
    title: Optional[str] = None
) -> Session:
    """
    Create a new conversation session.
    
    Args:
        db: Database session
        user_id: User UUID
        title: Optional session title
    
    Returns:
        Created Session instance
    """
    now = datetime.utcnow()
    session = Session(
        id=uuid4(),
        user_id=user_id,
        title=title,
        session_metadata={},  # Empty JSONB object
        started_at=now,
        last_active_at=now
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Mirror to Firestore (fire-and-forget)
    mirror = _get_mirror()
    if mirror:
        _schedule_mirror(
            mirror.mirror_session(session, context="dal.create_session"),
            f"sessions/{session.id}"
        )
    
    return session


async def get_session(
    db: AsyncSession,
    session_id: UUID
) -> Optional[Session]:
    """
    Retrieve session by ID.
    
    Args:
        db: Database session
        session_id: Session UUID
    
    Returns:
        Session instance or None if not found
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    return result.scalar_one_or_none()


async def update_session_activity(
    db: AsyncSession,
    session_id: UUID
) -> Session:
    """
    Update session's last_active_at timestamp.
    
    Args:
        db: Database session
        session_id: Session UUID
    
    Returns:
        Updated Session instance
    
    Raises:
        ValueError: If session not found
    """
    session = await get_session(db, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    
    session.last_active_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)
    return session


async def list_user_sessions(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 50
) -> list[Session]:
    """
    List sessions for a user, ordered by most recent activity.
    
    Args:
        db: Database session
        user_id: User UUID
        limit: Maximum number of sessions to return
    
    Returns:
        List of Session instances
    """
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.last_active_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============================================================================
# MESSAGE FUNCTIONS
# ============================================================================

async def append_message(
    db: AsyncSession,
    session_id: UUID,
    role: str,
    content: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    latency_ms: Optional[int] = None,
    request_id: Optional[UUID] = None
) -> Message:
    """
    Append a message to a session.
    
    Args:
        db: Database session
        session_id: Session UUID
        role: Message role ("user", "assistant", "system")
        content: Message content
        provider: AI provider name (e.g., "openai", "anthropic")
        model: Model identifier
        tokens_in: Input tokens consumed
        tokens_out: Output tokens generated
        latency_ms: Response latency in milliseconds
        request_id: Optional request UUID for tracing
    
    Returns:
        Created Message instance
    """
    message = Message(
        id=uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        provider=provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        request_id=request_id,
        created_at=datetime.utcnow()
    )
    db.add(message)
    
    # Update session activity
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(last_active_at=datetime.utcnow())
    )
    
    await db.commit()
    await db.refresh(message)
    
    # Mirror to Firestore (fire-and-forget)
    mirror = _get_mirror()
    if mirror:
        _schedule_mirror(
            mirror.mirror_message(message, context="dal.append_message"),
            f"messages/{message.id}"
        )
    
    return message


# ============================================================================
# USAGE LOGGING (TELEMETRY) - NEW UPSERT VERSION
# ============================================================================

async def upsert_usage(
    db: AsyncSession,
    request_id: UUID,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    user_id: Optional[UUID] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    cost_usd: Optional[float] = None,
    fallback_chain: Optional[dict] = None,
) -> None:
    """
    Idempotent usage logging with UPSERT (handles multiple attempts per request).
    
    This function can be called multiple times with the same request_id.
    On conflict, it updates the existing row and merges the fallback_chain.
    
    Args:
        db: Database session
        request_id: Unique request UUID (primary key)
        provider: Provider name
        model: Model identifier
        status: Request status ("success", "error", "timeout", etc.)
        latency_ms: Response latency in milliseconds
        user_id: Optional user UUID
        tokens_in: Input tokens
        tokens_out: Output tokens
        cost_usd: Estimated cost in USD
        fallback_chain: JSONB object tracking fallback attempts
    """
    # Sanitize fallback_chain for JSON serialization (handles UUID, datetime, etc.)
    safe_chain = json.loads(json.dumps(fallback_chain or {}, default=str))
    
    stmt = pg_insert(UsageLog).values(
        request_id=request_id,
        user_id=user_id,
        provider=provider,
        model=model,
        status=status,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        fallback_chain=safe_chain
    )
    
    # On conflict with existing request_id, update fields and merge fallback_chain
    stmt = stmt.on_conflict_do_update(
        index_elements=['request_id'],
        set_={
            'user_id': user_id,
            'provider': provider,
            'model': model,
            'status': status,
            'latency_ms': latency_ms,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost_usd': cost_usd,
            'fallback_chain': UsageLog.fallback_chain.op('||')(cast(safe_chain, JSONB))
        }
    )
    
    await db.execute(stmt)
    # Let route-level unit-of-work handle commit


# ============================================================================
# LEGACY USAGE LOGGING (DEPRECATED - Use upsert_usage instead)
# ============================================================================

async def log_usage(
    db: AsyncSession,
    request_id: UUID,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    user_id: Optional[UUID] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    cost_usd: Optional[float] = None,
    fallback_chain: Optional[dict] = None
) -> UsageLog:
    """
    DEPRECATED: Use upsert_usage() instead.
    
    This function will fail with duplicate key error if called multiple times
    with the same request_id.
    """
    usage = UsageLog(
        request_id=request_id,
        user_id=user_id,
        provider=provider,
        model=model,
        status=status,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        fallback_chain=fallback_chain or {},
        created_at=datetime.utcnow()
    )
    db.add(usage)
    await db.commit()
    await db.refresh(usage)
    return usage


# ============================================================================
# PROVIDER HEALTH TRACKING
# ============================================================================

async def record_provider_health(
    db: AsyncSession,
    provider_id: str,
    success: bool,
    latency_ms: Optional[int] = None,
    error_message: Optional[str] = None
) -> ProviderHealth:
    """
    Record provider health check result.
    
    Args:
        db: Database session
        provider_id: Provider identifier
        success: Whether the health check succeeded
        latency_ms: Response latency in milliseconds
        error_message: Error message if health check failed
    
    Returns:
        Created ProviderHealth instance
    """
    health = ProviderHealth(
        provider_id=provider_id,
        timestamp=datetime.utcnow(),
        latency_ms=latency_ms,
        success=success,
        error_message=error_message
    )
    db.add(health)
    await db.commit()
    await db.refresh(health)
    return health
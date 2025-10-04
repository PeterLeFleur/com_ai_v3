"""
Data Access Layer (DAL) for COM-AI v3
Provides async database operations for PostgreSQL (authoritative store).
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Optional
import json
import os
import asyncio
import logging

from sqlalchemy import select, update, cast, func, and_, Integer
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
# USAGE AGGREGATION (TELEMETRY QUERIES) - NEW FOR TRACK-001
# ============================================================================

async def get_usage_summary(
    db: AsyncSession,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    user_id: Optional[UUID] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> dict:
    """
    Aggregate usage statistics from usage_log.
    
    Args:
        db: Database session
        start_time: Filter start (defaults to 24 hours ago)
        end_time: Filter end (defaults to now)
        user_id: Optional user filter
        provider: Optional provider filter
        model: Optional model filter
    
    Returns:
        Dictionary with aggregated statistics:
        {
            "window": {"start": "...", "end": "..."},
            "summary": [
                {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "total_requests": 42,
                    "successful_requests": 40,
                    "failed_requests": 2,
                    "total_tokens_in": 15000,
                    "total_tokens_out": 23000,
                    "avg_latency_ms": 1250.5,
                    "total_cost_usd": null  # null until COST-001 complete
                }
            ],
            "totals": {
                "total_requests": 42,
                "successful_requests": 40,
                "failed_requests": 2,
                "total_tokens_in": 15000,
                "total_tokens_out": 23000,
                "total_cost_usd": null  # null until COST-001 complete
            }
        }
    
    Note: cost_usd calculation requires provider pricing tables (Task COST-001).
    Currently returns sum of existing values or null if none recorded.
    """
    # Default time window: last 24 hours
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(days=1)
    if end_time is None:
        end_time = datetime.utcnow()
    
    # Build filter conditions
    conditions = [
        UsageLog.created_at >= start_time,
        UsageLog.created_at <= end_time
    ]
    
    if user_id:
        conditions.append(UsageLog.user_id == user_id)
    if provider:
        conditions.append(UsageLog.provider == provider)
    if model:
        conditions.append(UsageLog.model == model)
    
    # Aggregate by provider and model
    query = select(
        UsageLog.provider,
        UsageLog.model,
        func.count(UsageLog.request_id).label('total_requests'),
        func.sum(
            func.cast(UsageLog.status == 'success', Integer)
        ).label('successful_requests'),
        func.sum(
            func.cast(UsageLog.status != 'success', Integer)
        ).label('failed_requests'),
        func.sum(UsageLog.tokens_in).label('total_tokens_in'),
        func.sum(UsageLog.tokens_out).label('total_tokens_out'),
        func.avg(UsageLog.latency_ms).label('avg_latency_ms'),
        func.sum(UsageLog.cost_usd).label('total_cost_usd')
    ).where(
        and_(*conditions)
    ).group_by(
        UsageLog.provider,
        UsageLog.model
    ).order_by(
        UsageLog.provider,
        UsageLog.model
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    # Format response
    summary = []
    totals = {
        'total_requests': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'total_tokens_in': 0,
        'total_tokens_out': 0,
        'total_cost_usd': 0.0
    }
    
    for row in rows:
        entry = {
            'provider': row.provider,
            'model': row.model,
            'total_requests': int(row.total_requests or 0),
            'successful_requests': int(row.successful_requests or 0),
            'failed_requests': int(row.failed_requests or 0),
            'total_tokens_in': int(row.total_tokens_in or 0),
            'total_tokens_out': int(row.total_tokens_out or 0),
            'avg_latency_ms': round(float(row.avg_latency_ms), 2) if row.avg_latency_ms else None,
            'total_cost_usd': round(float(row.total_cost_usd), 4) if row.total_cost_usd else None
        }
        summary.append(entry)
        
        # Accumulate totals
        totals['total_requests'] += entry['total_requests']
        totals['successful_requests'] += entry['successful_requests']
        totals['failed_requests'] += entry['failed_requests']
        totals['total_tokens_in'] += entry['total_tokens_in']
        totals['total_tokens_out'] += entry['total_tokens_out']
        if entry['total_cost_usd'] is not None:
            totals['total_cost_usd'] += entry['total_cost_usd']
    
    # If no costs were recorded, set total to null
    if totals['total_cost_usd'] == 0.0 and not any(
        entry['total_cost_usd'] is not None for entry in summary
    ):
        totals['total_cost_usd'] = None
    else:
        totals['total_cost_usd'] = round(totals['total_cost_usd'], 4)
    
    return {
        'window': {
            'start': start_time.isoformat(),
            'end': end_time.isoformat()
        },
        'summary': summary,
        'totals': totals
    }


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
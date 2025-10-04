"""
COM-AI v3 - Usage Telemetry Health Checks
Provides both lightweight table checks and detailed aggregation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text

from src.api.db.session import get_db_session_dependency
from src.api.db.dal import get_usage_summary
from src.utils.config import get_settings

router = APIRouter(prefix="/api/health", tags=["health", "telemetry"])


def _effective_db_url():
    """
    Build a PostgreSQL connection string from settings or discrete env vars.
    """
    s = get_settings()
    if s.database_url:
        return s.database_url

    user = s.postgres_user or "comai"
    pw   = s.postgres_password or "change_me"
    host = s.postgres_host or "localhost"
    port = s.postgres_port or 5432
    db   = s.postgres_db or "com_ai_v3"

    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


@router.get("/usage")
async def usage_health():
    """
    Light health probe for usage telemetry.
    Returns total rows and most recent event timestamp from usage_log if present.
    Designed to be non-fatal when the table doesn't exist yet.
    
    This is a quick health check - use /usage/summary for detailed aggregations.
    """
    url = _effective_db_url()
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            q = text("""
                SELECT
                    COUNT(*)::bigint AS total_rows,
                    COALESCE(MAX(created_at), TIMESTAMP '1970-01-01') AS latest_event
                FROM usage_log
            """)
            result = await conn.execute(q)
            row = result.first()
            total_rows = int(row.total_rows) if row and row.total_rows is not None else 0
            latest_event = str(row.latest_event) if row and row.latest_event is not None else None

            return {
                "ok": True,
                "table": "usage_log",
                "total_rows": total_rows,
                "latest_event": latest_event,
                "note": "If totals are zero, either no data yet or ingestion not wired.",
            }

    except Exception as e:
        msg = str(e)
        table_missing = "does not exist" in msg and "usage_log" in msg
        return {
            "ok": False,
            "error": msg,
            "status": "table_missing" if table_missing else "error",
            "next_steps": [
                "Run alembic migrations to create tables (including usage_log).",
                "Confirm DATABASE_URL/POSTGRES_* env vars are correct.",
                "Verify the app user has SELECT permission on usage_log."
            ],
        }
    finally:
        await engine.dispose()


@router.get("/usage/summary")
async def usage_summary(
    start: Optional[datetime] = Query(
        None,
        description="Start of time window (ISO 8601). Defaults to 24 hours ago."
    ),
    end: Optional[datetime] = Query(
        None,
        description="End of time window (ISO 8601). Defaults to now."
    ),
    user_id: Optional[str] = Query(
        None,
        description="Filter by user UUID"
    ),
    provider: Optional[str] = Query(
        None,
        description="Filter by provider (e.g., 'openai', 'anthropic')"
    ),
    model: Optional[str] = Query(
        None,
        description="Filter by model identifier"
    ),
    db: AsyncSession = Depends(get_db_session_dependency)
):
    """
    Aggregate usage statistics from usage_log table.
    
    Returns summary grouped by provider and model, with optional filters.
    
    Query Parameters:
        start: ISO 8601 datetime (default: 24 hours ago)
        end: ISO 8601 datetime (default: now)
        user_id: Filter by user UUID
        provider: Filter by provider name
        model: Filter by model identifier
    
    Response includes:
        - request_id: UUID for tracing
        - window: start/end timestamps
        - summary: array of provider/model statistics
        - totals: aggregated across all providers
    
    Note: total_cost_usd requires provider pricing tables (Task COST-001).
    Currently returns sum of existing cost values or null if none recorded.
    """
    request_id = uuid4()
    
    try:
        user_uuid = None
        if user_id:
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid user_id format: must be UUID. request_id={request_id}"
                )
        
        # Strip timezone info to match database TIMESTAMP WITHOUT TIME ZONE columns
        start_naive = start.replace(tzinfo=None) if start else None
        end_naive = end.replace(tzinfo=None) if end else None
        
        result = await get_usage_summary(
            db=db,
            start_time=start_naive,
            end_time=end_naive,
            user_id=user_uuid,
            provider=provider,
            model=model
        )
        
        result['request_id'] = str(request_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve usage summary: {str(e)}. request_id={request_id}"
        )
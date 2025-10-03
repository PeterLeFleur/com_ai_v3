# src/api/health/usage.py
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from src.utils.config import get_settings

router = APIRouter(prefix="/api/health", tags=["health"])


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
    port = s.postgres_port or 5433
    db   = s.postgres_db or "com_ai_v3"

    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


@router.get("/usage")
async def usage_health():
    """
    Light health probe for usage telemetry.
    Returns total rows and most recent event timestamp from `usage_log` if present.
    Designed to be non-fatal when the table doesn't exist yet.
    """
    url = _effective_db_url()
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            # Try to read aggregate info; tolerate missing table.
            # Assumes columns: id (any), created_at (timestamp) in table `usage_log`
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
        # Common cases:
        # - relation "usage_log" does not exist
        # - permission issue
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

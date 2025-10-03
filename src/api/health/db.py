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


@router.get("/db")
async def db_health():
    """
    Health probe for PostgreSQL — runs `SELECT 1`.
    """
    url = _effective_db_url()
    engine = create_async_engine(url)

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await engine.dispose()

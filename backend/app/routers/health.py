from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """Liveness + dependency check. Never raises: a DB outage is reported, not a 500."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "unreachable"

    return {
        "status": "ok",
        "environment": settings.env,
        "database": database_status,
    }

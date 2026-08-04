import uuid

from fastapi import Header, HTTPException, status


async def get_current_user_id(x_user_id: str = Header(..., alias="X-User-Id")) -> uuid.UUID:
    """Interim tenant identity until Phase 8 JWT auth lands: callers supply
    the acting user via X-User-Id. Every owned-table query must still be
    scoped through the returned id — see [[tenant-isolation]] guardrail.
    """
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-User-Id header")

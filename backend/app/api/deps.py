import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import InvalidTokenError, decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user_id(token: str = Depends(_oauth2_scheme)) -> uuid.UUID:
    """Every owned-table query must still be scoped through the returned id
    — see [[tenant-isolation]] guardrail. Replaces the interim X-User-Id
    header now that Phase 8 JWT auth has landed.
    """
    try:
        return decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

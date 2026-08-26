import uuid

from app.core.security import create_access_token


def auth_headers(user_id: uuid.UUID | str) -> dict[str, str]:
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}

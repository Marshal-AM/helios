"""JWT authentication helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from helios_common.config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_access_token(analyst_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": analyst_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise JWTError("missing subject")
        return str(sub)
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

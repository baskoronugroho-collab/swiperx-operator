"""Session tokens (JWT) and role-gating dependencies.

Roles are baked into the session at mint time, so role changes take effect on next
sign-in (matches FR-AUTH3). Courier links are a separate, unauthenticated path
(resolved by the awb.link_token lookup in the courier router).
"""
import time

import jwt
from fastapi import Cookie, Depends, HTTPException

import config


def mint_session(user_id: int, email: str, name: str, roles: list[str]) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "roles": roles,
        "iat": now,
        "exp": now + config.SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def _decode(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])


async def current_user(swiperx_session: str | None = Cookie(default=None)) -> dict:
    """Signed-in user. 401 if no/invalid session. Empty roles is allowed here
    (the frontend shows the 'contact the Ninja Van team' screen)."""
    if not swiperx_session:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        claims = _decode(swiperx_session)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_session")
    return {
        "id": int(claims["sub"]),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": claims.get("roles", []),
    }


def require_roles(*allowed: str):
    """Dependency factory: 403 unless the user holds one of `allowed` (superadmin always passes)."""
    async def _guard(user: dict = Depends(current_user)) -> dict:
        roles = set(user["roles"])
        if "superadmin" in roles or roles.intersection(allowed):
            return user
        raise HTTPException(status_code=403, detail="forbidden")

    return _guard

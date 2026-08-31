"""Identity and role-gating dependencies.

Identity comes from Substrait's platform SSO gateway, which authenticates the request
before it reaches us and injects `x-forwarded-email`. That header is the primary source
of truth; the app looks the address up in `users` to get roles. This is the same pattern
Ninja PNS uses, and it closes open item C33 — there is no longer a second login inside
the app for staff to clear.

The header is trustworthy because it only ever arrives on a gated path. The gateway
allowlists exactly `/c/*` and `/api/c/*`; every other path (including all of `/api/*`
that isn't a courier route) is 302'd to SSO or 401'd before the app sees it, and the
gateway sets the header itself rather than passing a client-supplied one through. No
route that calls `current_user` is reachable without passing that gate.

The JWT session cookie remains as a LOCAL-DEV fallback only, minted by the dev-login
stopgap in auth.py. It is skipped entirely whenever the proxy header is present.

Courier links are a third, separate path: unauthenticated by design, resolved by the
awb.link_token lookup in courier.py, and they never reach anything in this module.
"""
import time

import jwt
from fastapi import Cookie, Depends, HTTPException, Request

import config
import db

# Injected by the platform SSO gateway (oauth2-proxy style) on every gated request.
PROXY_EMAIL_HEADER = "x-forwarded-email"


async def load_user_by_email(email: str) -> dict | None:
    """Registered, active user + roles. None if unknown or deactivated."""
    user = await db.fetch_one(
        "SELECT id, name, google_email, active FROM users WHERE google_email = %s",
        (email.lower(),),
    )
    if not user or not user["active"]:
        return None
    roles = await db.fetch_all(
        "SELECT role FROM user_roles WHERE user_id = %s", (user["id"],)
    )
    return {**user, "roles": [r["role"] for r in roles]}


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


def proxy_email(request: Request) -> str | None:
    """The SSO-authenticated address for this request, if it came through the gateway."""
    return (request.headers.get(PROXY_EMAIL_HEADER) or "").strip().lower() or None


async def current_user(
    request: Request,
    swiperx_session: str | None = Cookie(default=None),
) -> dict:
    """Signed-in user. 401 if the request carries no identity at all.

    Empty roles is allowed here — the frontend shows the 'contact the Ninja Van team'
    screen for an address the gateway let in but no superadmin has registered yet.

    Roles are read from the database per request, so a role change takes effect
    immediately rather than on next sign-in (supersedes the FR-AUTH3 caveat that
    applied while roles were baked into the session at mint time).
    """
    email = proxy_email(request)
    if email:
        user = await load_user_by_email(email)
        if user is None:
            # Authenticated by the platform but not registered / deactivated here.
            return {"id": 0, "email": email, "name": email, "roles": []}
        return {
            "id": user["id"],
            "email": user["google_email"],
            "name": user["name"],
            "roles": user["roles"],
        }

    # Local dev only: no gateway in front, so fall back to the dev-login cookie.
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

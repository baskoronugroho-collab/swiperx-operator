"""Identity endpoints.

Staff no longer sign in *to this app*. Substrait's platform SSO gateway authenticates
every request before it arrives and injects `x-forwarded-email`; security.current_user
resolves that address to a registered user and their roles. The app's own Google OIDC
flow was removed on 28 Aug 2026 (open item C33) — it was a second login in front of a
login, and the platform's own SSO is the sanctioned one.

What remains here is /me, /logout, and a dev-login stopgap that only works when there is
no gateway in front of the app (i.e. local development).
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

import config
from security import current_user, load_user_by_email, mint_session, proxy_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session(resp, user: dict):
    token = mint_session(user["id"], user["google_email"], user["name"], user["roles"])
    resp.set_cookie(
        config.SESSION_COOKIE, token,
        max_age=config.SESSION_TTL_SECONDS,
        httponly=True, samesite="lax",
        secure=config.PUBLIC_BASE_URL.startswith("https"),
        path="/",
    )
    return resp


@router.get("/google/login")
async def google_login():
    """Retired. The platform gateway signs users in before the request reaches us, so
    landing here means something still links to the old flow — send them to the app."""
    return RedirectResponse("/")


@router.post("/dev-login")
async def dev_login(request: Request, email: str = Body(..., embed=True)):
    """LOCAL DEV ONLY: mint a session for a registered address without a password.

    Two independent guards, because this endpoint hands out any registered identity —
    superadmin included — to whoever calls it:

      1. DEV_LOGIN_ENABLED must be on (it defaults to off).
      2. The request must NOT have come through the SSO gateway. On the deployed app
         every request carries x-forwarded-email, so this is unreachable there even if
         someone leaves the flag switched on in the portal by mistake.
    """
    if not config.DEV_LOGIN_ENABLED or proxy_email(request):
        raise HTTPException(status_code=404, detail="disabled")
    user = await load_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=403, detail="unknown_or_inactive")
    return _set_session(JSONResponse({"ok": True, "roles": user["roles"]}), user)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    """Current identity + roles. roles=[] means the gateway let this address in but no
    superadmin has registered it (show contact-admin)."""
    return {
        "id": user["id"], "email": user["email"], "name": user["name"],
        "roles": user["roles"], "has_access": bool(user["roles"]),
    }


@router.post("/logout")
async def logout():
    """Clears the local dev-login cookie. It does NOT end the platform SSO session —
    that is the gateway's to end, from the Substrait side."""
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(config.SESSION_COOKIE, path="/")
    return resp

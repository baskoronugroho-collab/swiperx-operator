"""Authentication: Google Workspace OIDC + a dev-login fallback for pre-OAuth building.

Flow: /api/auth/google/login → Google → /api/auth/google/callback → look up the
registered user + roles → mint a session cookie → redirect to the app. Unregistered
accounts still get a (roles=[]) session so the frontend can show 'contact admin'.
"""
import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

import config
import db
from security import current_user, mint_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


async def _load_user(email: str) -> dict | None:
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
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="oidc_not_configured")
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.PUBLIC_BASE_URL + config.OIDC_REDIRECT_PATH,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
    }
    return RedirectResponse(GOOGLE_AUTH + "?" + urllib.parse.urlencode(params))


@router.get("/google/callback")
async def google_callback(code: str | None = None, error: str | None = None):
    if error or not code:
        return RedirectResponse("/?auth_error=1")
    async with httpx.AsyncClient(timeout=10) as client:
        tok = await client.post(GOOGLE_TOKEN, data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.PUBLIC_BASE_URL + config.OIDC_REDIRECT_PATH,
            "grant_type": "authorization_code",
        })
        tok.raise_for_status()
        access = tok.json().get("access_token")
        info = await client.get(GOOGLE_USERINFO, headers={"Authorization": f"Bearer {access}"})
        info.raise_for_status()
    profile = info.json()
    email = (profile.get("email") or "").lower()
    if not email or not profile.get("email_verified", True):
        return RedirectResponse("/?auth_error=1")
    if config.ALLOWED_GOOGLE_DOMAINS and email.split("@")[-1] not in config.ALLOWED_GOOGLE_DOMAINS:
        return RedirectResponse("/?auth_error=domain")

    user = await _load_user(email)
    if user is None:
        # Authenticated by Google but not registered / inactive → session with no roles.
        user = {"id": 0, "google_email": email, "name": profile.get("name", email), "roles": []}
    return _set_session(RedirectResponse("/"), user)


@router.post("/dev-login")
async def dev_login(email: str = Body(..., embed=True)):
    """Stopgap for building before the OAuth client exists. Disabled unless DEV_LOGIN_ENABLED."""
    if not config.DEV_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail="disabled")
    user = await _load_user(email)
    if user is None:
        raise HTTPException(status_code=403, detail="unknown_or_inactive")
    return _set_session(JSONResponse({"ok": True, "roles": user["roles"]}), user)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    """Current identity + roles. roles=[] means registered-but-no-role (show contact-admin)."""
    return {
        "id": user["id"], "email": user["email"], "name": user["name"],
        "roles": user["roles"], "has_access": bool(user["roles"]),
    }


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(config.SESSION_COOKIE, path="/")
    return resp

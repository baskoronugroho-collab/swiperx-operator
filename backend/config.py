"""Runtime configuration, read from the environment (Substrait injects/pre-creates these)."""
import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str) -> list[str]:
    return [x.strip().lower() for x in os.getenv(name, "").split(",") if x.strip()]


APP_ENV = os.getenv("APP_ENV", "alpha")
APP_VERSION = os.getenv("APP_VERSION", "Alpha 0.1")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Host used ONLY to build courier links (/c/<token>). Defaults to PUBLIC_BASE_URL, so
# leaving it unset changes nothing.
#
# It exists because the two hosts cannot be the same one. Google SSO only works on the
# app's platform hostname — Substrait states this outright on the Domains screen — so
# PUBLIC_BASE_URL must stay on that hostname or staff sign-in breaks: it is also the OIDC
# `redirect_uri` (auth.py) and the session-cookie Secure flag.
#
# Courier links have the opposite constraint. They are unauthenticated (the token is the
# credential), so they don't care about SSO, and they are counted TWICE inside the 500-char
# col-R budget (href + visible anchor text). On the org-scoped hostname that budget lands at
# exactly 500/500 with zero spare, so any growth silently drops the call-to-action and then
# ellipsises mandated compliance wording. A short custom domain is the only way to buy that
# margin back — e.g. https://swrx.ninjavan.co returns ~60 characters.
COURIER_BASE_URL = os.getenv("COURIER_BASE_URL", "").rstrip("/") or PUBLIC_BASE_URL

# Platform-injected (never in .env.example).
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")

# Auth.
DEV_LOGIN_ENABLED = _bool("DEV_LOGIN_ENABLED", False)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ALLOWED_GOOGLE_DOMAINS = _list("ALLOWED_GOOGLE_DOMAINS")
OIDC_REDIRECT_PATH = "/api/auth/google/callback"

# Email (optional; blank host → log-only).
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "swiperx-operator@ninjavan.co")

SESSION_COOKIE = "swiperx_session"
SESSION_TTL_SECONDS = 8 * 3600
ALL_ROLES = (
    "superadmin", "program_manager", "de", "implant",
    "station_ic", "validator", "swiperx",
)

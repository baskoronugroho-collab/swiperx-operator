"""Runtime configuration, read from the environment (Substrait injects/pre-creates these)."""
import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str) -> list[str]:
    return [x.strip().lower() for x in os.getenv(name, "").split(",") if x.strip()]


APP_ENV = os.getenv("APP_ENV", "alpha")
APP_VERSION = os.getenv("APP_VERSION", "Alpha 0.1")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

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

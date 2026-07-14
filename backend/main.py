"""SwipeRx Operator backend (Alpha 0.1) — Substrait upload mode.

Contract: listen on :8000, serve GET /health (readiness), API under /api.
OceanBase is MySQL-wire → asyncmy + %s (never asyncpg/$1). All DDL is in Flyway
migrations under resources/db/migration/, never in code.

M0: health, version, Google-SSO + dev-login, multi-role user management.
M1 (this build): OC intake + courier links (oc.py) — upload TMP, generate NV upload
.xlsx + links, resolve /c/<token>. Following: courier capture (M2),
returns/handover/validation (M3), PM overview + SwipeRx report (M4).
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import Response

import config
import db
from auth import router as auth_router
from oc import public_router as courier_router
from oc import router as oc_router
from security import current_user
from storage import store
from users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    yield
    await db.close_pool()


app = FastAPI(title="SwipeRx Operator", version=config.APP_VERSION, lifespan=lifespan)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(oc_router)
app.include_router(courier_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/version")
async def version() -> dict:
    """Current system name + changelog for the in-app 'What's new' panel."""
    notes = []
    if db.available():
        notes = await db.fetch_all(
            "SELECT version, notes, released_at FROM app_version ORDER BY released_at DESC, id DESC"
        )
        for n in notes:
            n["released_at"] = str(n["released_at"])
    return {"name": config.APP_VERSION, "env": config.APP_ENV, "changelog": notes}


@app.get("/api/media/{key}")
async def media(key: str, user: dict = Depends(current_user)):
    """Serve a stored blob (session-gated for staff surfaces). Courier-scoped media
    access arrives with the courier routes in M2. Swaps to presigned URLs under S3."""
    found = await store.get(key)
    if not found:
        return Response(status_code=404)
    data, content_type = found
    return Response(content=data, media_type=content_type)

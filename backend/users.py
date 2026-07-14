"""Superadmin user management: register by Google email, assign multiple roles, deactivate.

Multi-role by design (a person can be e.g. DE + Implant). Role changes apply on the
user's next sign-in, since roles are baked into the session (see security.mint_session).
"""
from fastapi import APIRouter, Body, Depends, HTTPException

import config
import db
from security import require_roles

router = APIRouter(prefix="/api/users", tags=["users"])
admin_only = require_roles("superadmin")


def _clean_roles(roles: list[str]) -> list[str]:
    picked = [r for r in dict.fromkeys(roles) if r in config.ALL_ROLES]
    if not picked:
        raise HTTPException(status_code=400, detail="no_valid_role")
    return picked


async def _roles_of(user_id: int) -> list[str]:
    rows = await db.fetch_all("SELECT role FROM user_roles WHERE user_id = %s", (user_id,))
    return [r["role"] for r in rows]


@router.get("")
async def list_users(_: dict = Depends(admin_only)):
    users = await db.fetch_all("SELECT id, name, google_email, active FROM users ORDER BY id")
    for u in users:
        u["roles"] = await _roles_of(u["id"])
        u["active"] = bool(u["active"])
    return {"users": users}


@router.post("", status_code=201)
async def register_user(
    email: str = Body(...),
    name: str = Body(...),
    roles: list[str] = Body(default=[]),
    _: dict = Depends(admin_only),
):
    roles = _clean_roles(roles)
    email = email.strip().lower()
    if await db.fetch_one("SELECT id FROM users WHERE google_email = %s", (email,)):
        raise HTTPException(status_code=409, detail="already_registered")
    uid = await db.execute(
        "INSERT INTO users (name, google_email, active) VALUES (%s, %s, 1)", (name.strip(), email)
    )
    for r in roles:
        await db.execute("INSERT INTO user_roles (user_id, role) VALUES (%s, %s)", (uid, r))
    return {"id": uid, "email": email, "roles": roles}


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    roles: list[str] | None = Body(default=None),
    active: bool | None = Body(default=None),
    _: dict = Depends(admin_only),
):
    if not await db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,)):
        raise HTTPException(status_code=404, detail="not_found")
    if roles is not None:
        roles = _clean_roles(roles)
        await db.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
        for r in roles:
            await db.execute("INSERT INTO user_roles (user_id, role) VALUES (%s, %s)", (user_id, r))
    if active is not None:
        await db.execute("UPDATE users SET active = %s WHERE id = %s", (1 if active else 0, user_id))
    return {"id": user_id, "roles": await _roles_of(user_id)}

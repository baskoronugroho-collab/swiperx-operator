"""Superadmin hub master: add, edit and remove hubs without a deploy (25 Sep 2026).

The `hub` table is the ONE hub list (V13). Two pickers read it:
  * the courier link lists every ACTIVE hub (courier.py);
  * Order Creation lists hubs that are active AND `oc_enabled` (oc.py, via oc_hub_names).
Before V13 the Order Creation list was hard-coded in oc_config.json, so adding a hub there
took a code change and a production security review.

A hub already stamped on an AWB can be deactivated but never deleted: its name is the only
record of where that parcel went, and the returns worklist and exports read it back. Rename
is deliberately absent for the same reason — `hub_name` is the key AWBs point at, so a
rename is a delete plus a create, and is only possible while nothing references the old one.
"""
import re

from fastapi import APIRouter, Body, Depends, HTTPException

import db
import oc_engine
from security import require_roles

router = APIRouter(prefix="/api/hubs", tags=["hubs"])
admin_only = require_roles("superadmin")

# Same 2-32 bound as the courier's free-text fallback and awb.hub_name (VARCHAR(32)).
# Uppercase letters, digits and hyphens: every seeded hub fits (BDO-NSB-SDB, MAC-MAC-SB).
_HUB_NAME = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,31}$")


async def oc_hub_names() -> list[str]:
    """Hubs offered in the Order Creation dropdown, and the only ones /api/oc/create accepts."""
    rows = await db.fetch_all(
        "SELECT hub_name FROM hub WHERE active = 1 AND oc_enabled = 1 ORDER BY hub_name"
    )
    return [r["hub_name"] for r in rows]


def _clean_name(value: str) -> str:
    name = (value or "").strip().upper()
    if not _HUB_NAME.match(name):
        raise HTTPException(status_code=400, detail="bad_hub_name")
    return name


def _clean_origin(value) -> str | None:
    """None/blank clears it — most hubs have no mapped warehouse yet (see V10)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str) or value not in oc_engine.CFG.get("origins", {}):
        raise HTTPException(status_code=400, detail="bad_origin")
    return value


def _flag(patch: dict, key: str) -> bool:
    v = patch[key]
    if not isinstance(v, bool):
        raise HTTPException(status_code=400, detail=f"bad_{key}")
    return v


async def _row(hub_name: str) -> dict | None:
    row = await db.fetch_one(
        "SELECT h.hub_name, h.origin, h.active, h.oc_enabled, h.updated_at, "
        "(SELECT COUNT(*) FROM awb a WHERE a.hub_name = h.hub_name) AS awb_count "
        "FROM hub h WHERE h.hub_name = %s",
        (hub_name,),
    )
    return _shape(row) if row else None


def _shape(r: dict) -> dict:
    return {
        "hub_name": r["hub_name"],
        "origin": r["origin"],
        "active": bool(r["active"]),
        "oc_enabled": bool(r["oc_enabled"]),
        "awb_count": int(r["awb_count"] or 0),
        "updated_at": str(r["updated_at"]) if r["updated_at"] is not None else None,
    }


async def _audit(user: dict, action: str, hub_name: str, what: str) -> None:
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, %s, 'hub', %s)",
        (user["email"], action, f"{hub_name}: {what}"[:255]),
    )


@router.get("")
async def list_hubs(_: dict = Depends(admin_only)):
    rows = await db.fetch_all(
        "SELECT h.hub_name, h.origin, h.active, h.oc_enabled, h.updated_at, "
        "(SELECT COUNT(*) FROM awb a WHERE a.hub_name = h.hub_name) AS awb_count "
        "FROM hub h ORDER BY h.hub_name"
    )
    return {"hubs": [_shape(r) for r in rows], "origins": oc_engine.origins()}


@router.post("", status_code=201)
async def create_hub(
    hub_name: str = Body(...),
    origin: str | None = Body(default=None),
    active: bool = Body(default=True),
    oc_enabled: bool = Body(default=False),
    user: dict = Depends(admin_only),
):
    name = _clean_name(hub_name)
    origin = _clean_origin(origin)
    if await db.fetch_one("SELECT hub_name FROM hub WHERE hub_name = %s", (name,)):
        raise HTTPException(status_code=409, detail="already_exists")
    await db.execute(
        "INSERT INTO hub (hub_name, origin, active, oc_enabled) VALUES (%s, %s, %s, %s)",
        (name, origin, 1 if active else 0, 1 if oc_enabled else 0),
    )
    await _audit(user, "hub_create", name,
                 f"origin={origin} active={active} oc_enabled={oc_enabled}")
    return await _row(name)


@router.patch("/{hub_name}")
async def update_hub(hub_name: str, patch: dict = Body(...), user: dict = Depends(admin_only)):
    """Partial update of origin / active / oc_enabled. A JSON body rather than typed Body
    params, because `"origin": null` (clear it) must be told apart from origin omitted."""
    name = hub_name.strip().upper()
    if not await db.fetch_one("SELECT hub_name FROM hub WHERE hub_name = %s", (name,)):
        raise HTTPException(status_code=404, detail="not_found")

    changes: dict[str, object] = {}
    if "origin" in patch:
        changes["origin"] = _clean_origin(patch["origin"])
    for key in ("active", "oc_enabled"):
        if key in patch:
            changes[key] = _flag(patch, key)
    if not changes:
        raise HTTPException(status_code=400, detail="nothing_to_update")

    # Column names come from the fixed tuple above, never from the request body.
    cols = ", ".join(f"{k} = %s" for k in changes)
    vals = [(1 if v else 0) if isinstance(v, bool) else v for v in changes.values()]
    await db.execute(f"UPDATE hub SET {cols}, updated_at = NOW() WHERE hub_name = %s", (*vals, name))
    await _audit(user, "hub_update", name, " ".join(f"{k}={v}" for k, v in changes.items()))
    return await _row(name)


@router.delete("/{hub_name}")
async def delete_hub(hub_name: str, user: dict = Depends(admin_only)):
    name = hub_name.strip().upper()
    row = await _row(name)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    if row["awb_count"]:
        raise HTTPException(status_code=409, detail="hub_in_use")
    await db.execute("DELETE FROM hub WHERE hub_name = %s", (name,))
    await _audit(user, "hub_delete", name, "deleted")
    return {"deleted": name}

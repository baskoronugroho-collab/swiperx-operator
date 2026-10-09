"""Migrate to Vasil Operator — a tracking list that is separate from the reject-returns lane.

Superadmin and KAM tick reject returns off as uploaded to Vasil Operator. Everything lives
in `vasil_migration`; nothing here writes to `return_parcel`, so no stage, export or print
step on the other lane can be affected by what happens on this page.

  pending (default) --done--> done --pending--> pending
  pending / done    --hide--> hidden   (gone from this page only; never deleted)
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

import db
from returns import _proof_photos, _rows, worklist_csv
from security import require_roles

router = APIRouter(prefix="/api/vasil", tags=["vasil"])

# superadmin always passes `require_roles`; KAM is the one other role that sees this page.
vasil_roles = require_roles("kam")

VIEWS = ("pending", "done", "all")


async def _status_map() -> dict[int, dict]:
    rows = await db.fetch_all(
        "SELECT vm.return_parcel_id, vm.status, vm.done_at, u.google_email AS done_by_email "
        "FROM vasil_migration vm LEFT JOIN users u ON u.id = vm.done_by"
    )
    return {r["return_parcel_id"]: r for r in rows}


async def _view(status: str) -> list[dict]:
    if status not in VIEWS:
        raise HTTPException(status_code=400, detail="bad_status")
    marks = await _status_map()
    out = []
    for r in await _rows():
        m = marks.get(r["id"])
        state = m["status"] if m else "pending"
        if state == "hidden":
            continue
        if status != "all" and state != status:
            continue
        r["vasil_status"] = state
        r["vasil_done_at"] = str(m["done_at"]) if m and m["done_at"] else None
        r["vasil_done_by_email"] = m["done_by_email"] if m else None
        out.append(r)
    return out


@router.get("/returns")
async def list_returns(status: str = Query(default="pending", description="|".join(VIEWS)),
                       _: dict = Depends(vasil_roles)):
    rows = await _view(status)
    for r in rows:
        # The at-the-door evidence the Detail panel shows, same as on Reject returns.
        r["proof_photos"] = await _proof_photos(r["original_awb_id"])
    return {"returns": rows, "count": len(rows)}


@router.get("/export.csv")
async def export_csv(status: str = Query(default="all", description="|".join(VIEWS)),
                     _: dict = Depends(vasil_roles)):
    """Same columns as the Reject returns export, narrowed to this page's pending/done/all."""
    return Response(content=worklist_csv(await _view(status)), media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="vasil-{status}.csv"'})


async def _apply(ids: list[int], from_states: tuple[str, ...], to_state: str,
                 action: str, user: dict) -> dict:
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    valid = {r["id"] for r in await _rows(ids)}
    marks = await _status_map()
    updated = 0
    for rid in ids:
        if rid not in valid:
            continue
        m = marks.get(rid)
        if (m["status"] if m else "pending") not in from_states:
            continue
        if to_state == "done":
            sets, args = "status='done', done_at=NOW(), done_by=%s, hidden_at=NULL, hidden_by=NULL", [user["id"]]
        elif to_state == "pending":
            sets, args = "status='pending', done_at=NULL, done_by=NULL", []
        else:
            sets, args = "status='hidden', hidden_at=NOW(), hidden_by=%s", [user["id"]]
        if m:
            await db.execute(
                f"UPDATE vasil_migration SET {sets}, updated_at=NOW() WHERE return_parcel_id=%s",
                (*args, rid))
        else:
            await db.execute(
                "INSERT INTO vasil_migration (return_parcel_id, status, updated_at) "
                "VALUES (%s, 'pending', NOW())", (rid,))
            await db.execute(
                f"UPDATE vasil_migration SET {sets}, updated_at=NOW() WHERE return_parcel_id=%s",
                (*args, rid))
        updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, %s, 'vasil_migration', %s)",
        (user["email"], action, f"{updated} rows"),
    )
    return {"updated": updated}


@router.post("/mark-done")
async def mark_done(ids: list[int] = Body(..., embed=True), user: dict = Depends(vasil_roles)):
    return await _apply(ids, ("pending",), "done", "vasil_mark_done", user)


@router.post("/mark-pending")
async def mark_pending(ids: list[int] = Body(..., embed=True), user: dict = Depends(vasil_roles)):
    return await _apply(ids, ("done",), "pending", "vasil_mark_pending", user)


@router.post("/hide")
async def hide(ids: list[int] = Body(..., embed=True), user: dict = Depends(vasil_roles)):
    """Remove from this page only. The reject return itself is untouched."""
    return await _apply(ids, ("pending", "done"), "hidden", "vasil_hide", user)

"""Migrate to Vasil Operator — a tracking list that is separate from the reject-returns lane.

Superadmin and KAM tick reject returns off as uploaded to Vasil Operator. Everything lives
in `vasil_migration` and `vasil_photo`; nothing here writes to `return_parcel` or
`document_capture`, so no stage, export, print step or courier photo on the other lane can
be affected by what happens on this page.

  pending (default) --done--> done
  pending / done    --unable (with reasons)--> unable
  done / unable     --pending--> pending
  any of the above  --hide--> hidden   (gone from this page only; never deleted)

Photo fixes are Vasil-only too: removing a courier photo just hides it from this page, and
an uploaded replacement lives in `vasil_photo`. The courier's original is never changed.
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

import db
from courier import ALLOWED_IMAGE_TYPES, MAX_PHOTO_BYTES
from returns import _rows, worklist_csv
from security import require_roles
from storage import store

router = APIRouter(prefix="/api/vasil", tags=["vasil"])

# superadmin always passes `require_roles`; KAM is the one other role that sees this page.
vasil_roles = require_roles("kam")

VIEWS = ("pending", "done", "unable", "all")

# key -> label, in the order the page lists them.
REASONS = {
    "dn": "no proper DN photos",
    "item": "no item photos",
    "sp_manual": "no sp manual photos",
}
# The three photo kinds those reasons are about; the AWB sticker is shown but not edited.
EDITABLE_DOCS = ("delivery_note", "rejected_goods", "sp_manual")
SHOWN_DOCS = ("delivery_note", "rejected_goods", "awb_sticker", "sp_manual")


def _day(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="bad_date") from None


def _reasons(values: list[str]) -> list[str]:
    if not values or set(values) - set(REASONS):
        raise HTTPException(status_code=400, detail="bad_reasons")
    return [k for k in REASONS if k in set(values)]


async def _status_map() -> dict[int, dict]:
    rows = await db.fetch_all(
        "SELECT vm.return_parcel_id, vm.status, vm.done_at, vm.unable_reasons, "
        "u.google_email AS done_by_email "
        "FROM vasil_migration vm LEFT JOIN users u ON u.id = vm.done_by"
    )
    return {r["return_parcel_id"]: r for r in rows}


async def _collect(date_from: str | None, date_to: str | None) -> list[dict]:
    """Every row not hidden from this page, within the reject-date window, with its state."""
    lo, hi = _day(date_from), _day(date_to)
    marks = await _status_map()
    out = []
    for r in await _rows():
        day = (r["rejected_at"] or "")[:10]
        if (lo and day < lo) or (hi and day > hi):
            continue
        m = marks.get(r["id"])
        state = m["status"] if m else "pending"
        if state == "hidden":
            continue
        keys = [k for k in (m["unable_reasons"] or "").split(",") if k] if m else []
        r["vasil_status"] = state
        r["vasil_done_at"] = str(m["done_at"]) if m and m["done_at"] else None
        r["vasil_done_by_email"] = m["done_by_email"] if m else None
        r["unable_reasons"] = keys
        r["unable_reason"] = ", ".join(REASONS[k] for k in keys if k in REASONS)
        out.append(r)
    return out


def _select(rows: list[dict], status: str, reason: str | None) -> list[dict]:
    if status not in VIEWS:
        raise HTTPException(status_code=400, detail="bad_status")
    if reason and reason not in REASONS:
        raise HTTPException(status_code=400, detail="bad_reason")
    return [r for r in rows
            if (status == "all" or r["vasil_status"] == status)
            and (not reason or reason in r["unable_reasons"])]


async def _attach_photos(rows: list[dict]) -> None:
    """`proof_photos` per row: the courier's photos minus those hidden here, plus uploads."""
    if not rows:
        return
    awbs = sorted({r["original_awb_id"] for r in rows})
    caps = await db.fetch_all(
        "SELECT id, awb_id, doc_type, po_number, photo_ref FROM document_capture "
        f"WHERE awb_id IN ({','.join(['%s'] * len(awbs))}) "
        f"AND doc_type IN ({','.join(['%s'] * len(SHOWN_DOCS))}) ORDER BY id",
        (*awbs, *SHOWN_DOCS),
    )
    ids = [r["id"] for r in rows]
    fixes = await db.fetch_all(
        "SELECT id, return_parcel_id, doc_type, po_number, photo_ref, original_capture_id, "
        f"removed_at FROM vasil_photo WHERE return_parcel_id IN ({','.join(['%s'] * len(ids))}) "
        "ORDER BY id", tuple(ids),
    )
    pos = await db.fetch_all(
        "SELECT awb_id, po_number, koli FROM po_line "
        f"WHERE awb_id IN ({','.join(['%s'] * len(awbs))}) ORDER BY id", tuple(awbs))
    for r in rows:
        # The forward order's POs: what an SP manual replacement photo can be filed under.
        r["po_options"] = [{"po_number": p["po_number"], "koli": p["koli"]}
                           for p in pos if p["awb_id"] == r["original_awb_id"]]
        mine = [f for f in fixes if f["return_parcel_id"] == r["id"]]
        hidden = {f["original_capture_id"] for f in mine if f["original_capture_id"]}
        photos = [
            {"source": "original", "ref_id": c["id"], "doc_type": c["doc_type"],
             "po_number": c["po_number"], "photo_url": f"/api/media/{c['photo_ref']}",
             "editable": c["doc_type"] in EDITABLE_DOCS}
            for c in caps if c["awb_id"] == r["original_awb_id"] and c["id"] not in hidden
        ]
        photos += [
            {"source": "vasil", "ref_id": f["id"], "doc_type": f["doc_type"],
             "po_number": f["po_number"], "photo_url": f"/api/media/{f['photo_ref']}",
             "editable": True}
            for f in mine if f["photo_ref"] and not f["removed_at"]
        ]
        r["proof_photos"] = photos


@router.get("/returns")
async def list_returns(
    status: str = Query(default="pending", description="|".join(VIEWS)),
    date_from: str | None = Query(default=None, description="reject date, YYYY-MM-DD, inclusive"),
    date_to: str | None = Query(default=None, description="reject date, YYYY-MM-DD, inclusive"),
    reason: str | None = Query(default=None, description="|".join(REASONS)),
    _: dict = Depends(vasil_roles),
):
    window = await _collect(date_from, date_to)
    rows = _select(window, status, reason)
    await _attach_photos(rows)
    # Counted over the whole window, so the chips stay put while one reason is filtered on.
    counts = {k: sum(1 for r in window if r["vasil_status"] == "unable" and k in r["unable_reasons"])
              for k in REASONS}
    return {"returns": rows, "count": len(rows), "reason_counts": counts,
            "reasons": [{"key": k, "label": v} for k, v in REASONS.items()]}


@router.get("/export.csv")
async def export_csv(
    status: str = Query(default="all", description="|".join(VIEWS)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    reason: str | None = Query(default=None),
    _: dict = Depends(vasil_roles),
):
    """Same columns as the Reject returns export; the Unable tab adds one `unable_reason` column."""
    rows = _select(await _collect(date_from, date_to), status, reason)
    extra = ("unable_reason",) if status == "unable" else ()
    return Response(content=worklist_csv(rows, extra), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="vasil-{status}.csv"'})


async def _apply(ids: list[int], from_states: tuple[str, ...], to_state: str, action: str,
                 user: dict, reasons: list[str] | None = None) -> dict:
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
            sets, args = ("status='done', done_at=NOW(), done_by=%s, unable_reasons=NULL, "
                          "hidden_at=NULL, hidden_by=NULL"), [user["id"]]
        elif to_state == "unable":
            sets, args = ("status='unable', unable_reasons=%s, done_at=NULL, done_by=NULL, "
                          "hidden_at=NULL, hidden_by=NULL"), [",".join(reasons or [])]
        elif to_state == "pending":
            sets, args = "status='pending', done_at=NULL, done_by=NULL, unable_reasons=NULL", []
        else:
            sets, args = "status='hidden', hidden_at=NOW(), hidden_by=%s", [user["id"]]
        if not m:
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


@router.post("/mark-unable")
async def mark_unable(ids: list[int] = Body(..., embed=True),
                      reasons: list[str] = Body(..., embed=True),
                      user: dict = Depends(vasil_roles)):
    """Flag AWBs that can't be uploaded yet, with what photo is wrong (one or more reasons)."""
    return await _apply(ids, ("pending", "done"), "unable", "vasil_mark_unable", user,
                        _reasons(reasons))


@router.post("/set-reasons")
async def set_reasons(ids: list[int] = Body(..., embed=True),
                      reasons: list[str] = Body(..., embed=True),
                      user: dict = Depends(vasil_roles)):
    """Change the reasons on AWBs already marked unable (a wrong pick, or one photo fixed)."""
    picked = _reasons(reasons)
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    valid = {r["id"] for r in await _rows(ids)}
    marks = await _status_map()
    updated = 0
    for rid in ids:
        if rid in valid and rid in marks and marks[rid]["status"] == "unable":
            await db.execute(
                "UPDATE vasil_migration SET unable_reasons=%s, updated_at=NOW() "
                "WHERE return_parcel_id=%s", (",".join(picked), rid))
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'vasil_set_reasons', 'vasil_migration', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


@router.post("/mark-pending")
async def mark_pending(ids: list[int] = Body(..., embed=True), user: dict = Depends(vasil_roles)):
    return await _apply(ids, ("done", "unable"), "pending", "vasil_mark_pending", user)


@router.post("/hide")
async def hide(ids: list[int] = Body(..., embed=True), user: dict = Depends(vasil_roles)):
    """Remove from this page only. The reject return itself is untouched."""
    return await _apply(ids, ("pending", "done", "unable"), "hidden", "vasil_hide", user)


# ------------------------------------------------------- Vasil-only photo fixes ----
async def _one_row(rid: int) -> dict:
    rows = await _rows([rid])
    if not rows:
        raise HTTPException(status_code=404, detail="return_not_found")
    return rows[0]


@router.post("/returns/{rid}/photos", status_code=201)
async def upload_photo(
    rid: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    po_number: str | None = Form(default=None),
    user: dict = Depends(vasil_roles),
):
    """Add a replacement photo that exists on the Vasil page only."""
    row = await _one_row(rid)
    if doc_type not in EDITABLE_DOCS:
        raise HTTPException(status_code=400, detail="unknown_doc_type")
    if doc_type == "sp_manual" and not po_number:
        raise HTTPException(status_code=400, detail="sp_manual_needs_po")
    if po_number and not await db.fetch_one(
        "SELECT 1 AS ok FROM po_line WHERE awb_id = %s AND po_number = %s",
        (row["original_awb_id"], po_number),
    ):
        raise HTTPException(status_code=400, detail="unknown_po")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="photo_too_large")
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_image_type")
    ref = await store.put(data, content_type)
    photo_id = await db.execute(
        "INSERT INTO vasil_photo (return_parcel_id, doc_type, po_number, photo_ref, created_by, created_at) "
        "VALUES (%s, %s, %s, %s, %s, NOW())", (rid, doc_type, po_number, ref, user["id"]))
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'vasil_photo_upload', 'vasil_photo', %s)",
        (user["email"], f"{rid}:{doc_type}"),
    )
    return {"id": photo_id, "doc_type": doc_type, "po_number": po_number,
            "photo_url": f"/api/media/{ref}"}


@router.post("/returns/{rid}/photos/remove")
async def remove_photo(
    rid: int,
    source: str = Body(..., embed=True),
    ref_id: int = Body(..., embed=True),
    user: dict = Depends(vasil_roles),
):
    """Remove a photo from the Vasil view. A courier photo is only hidden here; an upload
    made on this page is marked removed. Neither deletes anything from the other lane."""
    row = await _one_row(rid)
    if source == "vasil":
        found = await db.fetch_one(
            "SELECT id FROM vasil_photo WHERE id = %s AND return_parcel_id = %s "
            "AND photo_ref IS NOT NULL AND removed_at IS NULL", (ref_id, rid))
        if not found:
            raise HTTPException(status_code=404, detail="photo_not_found")
        await db.execute(
            "UPDATE vasil_photo SET removed_at = NOW(), removed_by = %s WHERE id = %s",
            (user["id"], ref_id))
    elif source == "original":
        cap = await db.fetch_one(
            "SELECT id, doc_type, po_number FROM document_capture WHERE id = %s AND awb_id = %s",
            (ref_id, row["original_awb_id"]))
        if not cap or cap["doc_type"] not in EDITABLE_DOCS:
            raise HTTPException(status_code=404, detail="photo_not_found")
        if not await db.fetch_one(
            "SELECT id FROM vasil_photo WHERE return_parcel_id = %s AND original_capture_id = %s",
            (rid, ref_id)):
            await db.execute(
                "INSERT INTO vasil_photo (return_parcel_id, doc_type, po_number, original_capture_id, "
                "created_by, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (rid, cap["doc_type"], cap["po_number"], ref_id, user["id"]))
    else:
        raise HTTPException(status_code=400, detail="bad_source")
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'vasil_photo_remove', 'vasil_photo', %s)",
        (user["email"], f"{rid}:{source}:{ref_id}"),
    )
    return {"ok": True}

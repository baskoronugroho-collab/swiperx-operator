"""Lane 3 — the reject-return worklist (SCOPE_V3_MVP.md §3).

Replaces the WA-group workaround described in the New-RDO deck (slide 16): a courier
reject appears here immediately, Ops acknowledges it, then records the replacement TIDs
that DE minted on the RTS account so the row closes with an audit trail.

Deliberately NOT in scope: generating the return OC. Ops pastes the TIDs that DE created
in NV's system, exactly as today — the value here is visibility and the trail, not
generation (PRD FR-R4 / §19 #23 stays deferred).
"""
import csv
import io

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

import db
from security import require_roles

router = APIRouter(prefix="/api/returns", tags=["returns"])
ops_roles = require_roles("implant", "de", "station_ic", "program_manager")

# The account the deck mandates for replacement return TIDs.
RTS_SHIPPER_ID = "11398434"

# A full reject (`semua`) closes by RTS instead of by return TIDs — see V8 migration.
STAGES = ("pending_ack", "acknowledged", "tids_sent", "rts_requested")

_SELECT = """
    SELECT rp.id, rp.original_awb_id, rp.return_type, rp.service_id,
           rp.created_at        AS rejected_at,
           rp.acknowledged_at, rp.return_tids, rp.tids_sent_at,
           rp.rts_requested_at,
           a.pharmacy_name, a.city,
           ack.google_email     AS acknowledged_by_email,
           snt.google_email     AS tids_sent_by_email,
           rts.google_email     AS rts_requested_by_email
      FROM return_parcel rp
      LEFT JOIN awb   a   ON a.awb_id   = rp.original_awb_id
      LEFT JOIN users ack ON ack.id     = rp.acknowledged_by
      LEFT JOIN users snt ON snt.id     = rp.tids_sent_by
      LEFT JOIN users rts ON rts.id     = rp.rts_requested_by
"""


def _is_full(row: dict) -> bool:
    """A whole-consignment refusal. Closes by RTS on the FORWARD tracking number."""
    return row.get("return_type") == "semua"


def _stage(row: dict) -> str:
    if _is_full(row) and row.get("rts_requested_at"):
        return "rts_requested"
    if row["tids_sent_at"]:
        return "tids_sent"
    if row["acknowledged_at"]:
        return "acknowledged"
    return "pending_ack"


def _shape(row: dict) -> dict:
    for k in ("rejected_at", "acknowledged_at", "tids_sent_at", "rts_requested_at"):
        row[k] = str(row[k]) if row[k] else None
    row["stage"] = _stage(row)
    # Tells the UI which closing action this row needs, without it re-deriving the rule.
    row["closes_by"] = "rts" if _is_full(row) else "tids"
    return row


async def _one(return_id: int) -> dict:
    row = await db.fetch_one(f"{_SELECT} WHERE rp.id = %s", (return_id,))
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return _shape(row)


async def _proof_photos(awb_id: str) -> list[dict]:
    """The at-the-door reject evidence, so Ops can see what they're acknowledging."""
    rows = await db.fetch_all(
        "SELECT doc_type, photo_ref FROM document_capture WHERE awb_id = %s "
        "AND doc_type IN ('rejected_goods', 'delivery_note', 'awb_sticker') ORDER BY id",
        (awb_id,),
    )
    return [{"doc_type": r["doc_type"], "photo_url": f"/api/media/{r['photo_ref']}"} for r in rows]


@router.get("")
async def list_returns(
    stage: str | None = Query(default=None, description="pending_ack|acknowledged|tids_sent"),
    _: dict = Depends(ops_roles),
):
    """Open reject-returns, newest first. Default view in the UI is `pending_ack`."""
    if stage and stage not in STAGES:
        raise HTTPException(status_code=400, detail="bad_stage")

    where = {
        "pending_ack": " WHERE rp.acknowledged_at IS NULL",
        "acknowledged": (" WHERE rp.acknowledged_at IS NOT NULL AND rp.tids_sent_at IS NULL"
                         " AND rp.rts_requested_at IS NULL"),
        "tids_sent": " WHERE rp.tids_sent_at IS NOT NULL",
        "rts_requested": " WHERE rp.rts_requested_at IS NOT NULL",
    }.get(stage or "", "")

    rows = await db.fetch_all(f"{_SELECT}{where} ORDER BY rp.created_at DESC, rp.id DESC LIMIT 500")
    out = []
    for r in rows:
        shaped = _shape(r)
        shaped["proof_photos"] = await _proof_photos(shaped["original_awb_id"])
        out.append(shaped)
    return {"returns": out, "rts_shipper_id": RTS_SHIPPER_ID}


@router.post("/{return_id}/acknowledge")
async def acknowledge(
    return_id: int,
    acknowledged: bool = Body(..., embed=True),
    user: dict = Depends(ops_roles),
):
    """Tick/untick 'I've seen this reject and I'm handling it'. Records who and when."""
    row = await _one(return_id)
    if row["stage"] == "tids_sent" and not acknowledged:
        raise HTTPException(status_code=409, detail="already_closed")

    if acknowledged:
        await db.execute(
            "UPDATE return_parcel SET acknowledged_at = NOW(), acknowledged_by = %s, "
            "updated_at = NOW() WHERE id = %s", (user["id"], return_id),
        )
    else:
        await db.execute(
            "UPDATE return_parcel SET acknowledged_at = NULL, acknowledged_by = NULL, "
            "updated_at = NOW() WHERE id = %s", (return_id,),
        )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, %s, 'return_parcel', %s)",
        (user["email"], "return_ack" if acknowledged else "return_unack", str(return_id)),
    )
    return await _one(return_id)


@router.post("/{return_id}/tids")
async def send_tids(
    return_id: int,
    return_tids: str = Body(..., embed=True),
    user: dict = Depends(ops_roles),
):
    """Record the replacement return TID(s) DE minted on the RTS account, and mark them
    sent. This closes the row."""
    row = await _one(return_id)
    if _is_full(row):
        # A whole-consignment refusal is an RTS on the existing forward TID; minting a
        # second one would duplicate the parcel in NV's system (deck slide 7, 10 Aug).
        raise HTTPException(status_code=409, detail="full_reject_uses_rts")
    tids = [t.strip() for t in return_tids.replace("\n", ",").split(",") if t.strip()]
    if not tids:
        raise HTTPException(status_code=400, detail="no_tids")
    if not row["acknowledged_at"]:
        raise HTTPException(status_code=409, detail="not_acknowledged")

    joined = ", ".join(tids)
    await db.execute(
        "UPDATE return_parcel SET return_tids = %s, return_awb_id = %s, tids_sent_at = NOW(), "
        "tids_sent_by = %s, updated_at = NOW() WHERE id = %s",
        (joined, tids[0][:40], user["id"], return_id),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'return_tids_sent', "
        "'return_parcel', %s)", (user["email"], str(return_id)),
    )
    return await _one(return_id)


@router.post("/{return_id}/rts")
async def request_rts(return_id: int, user: dict = Depends(ops_roles)):
    """Record that RTS has been triggered on the ORIGINAL forward tracking number.

    This is how a `semua` row closes. No new tracking number is created: the parcel already
    has one, and RTS turns that same shipment around — which keeps one identifier and one
    history instead of two. Requires acknowledgement first, same as the TID path, so nobody
    closes a row they haven't looked at.
    """
    row = await _one(return_id)
    if not _is_full(row):
        raise HTTPException(status_code=409, detail="partial_reject_uses_tids")
    if not row["acknowledged_at"]:
        raise HTTPException(status_code=409, detail="not_acknowledged")
    if row["rts_requested_at"]:
        raise HTTPException(status_code=409, detail="already_requested")

    await db.execute(
        "UPDATE return_parcel SET rts_requested_at = NOW(), rts_requested_by = %s, "
        "updated_at = NOW() WHERE id = %s", (user["id"], return_id),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'return_rts_requested', "
        "'return_parcel', %s)", (user["email"], str(return_id)),
    )
    return await _one(return_id)


@router.get("/export.csv")
async def export_csv(_: dict = Depends(ops_roles)):
    """Flat export of the worklist with its full audit trail."""
    rows = await db.fetch_all(f"{_SELECT} ORDER BY rp.created_at DESC, rp.id DESC")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "return_id", "forward_awb", "pharmacy", "city", "reject_type", "rejected_at",
        "stage", "closes_by", "acknowledged_at", "acknowledged_by", "return_tids",
        "tids_sent_at", "tids_sent_by", "rts_requested_at", "rts_requested_by",
    ])
    for r in rows:
        s = _shape(r)
        w.writerow([
            s["id"], s["original_awb_id"], s["pharmacy_name"] or "", s["city"] or "",
            s["return_type"], s["rejected_at"] or "", s["stage"], s["closes_by"],
            s["acknowledged_at"] or "", s["acknowledged_by_email"] or "", s["return_tids"] or "",
            s["tids_sent_at"] or "", s["tids_sent_by_email"] or "",
            s["rts_requested_at"] or "", s["rts_requested_by_email"] or "",
        ])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="reject-returns.csv"'},
    )

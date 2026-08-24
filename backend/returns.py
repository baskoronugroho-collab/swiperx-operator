"""Lane 3 — the reject-return worklist (reworked 24 Aug 2026 to the whiteboard flow).

A courier reject lands here the moment it is submitted, then walks a fixed pipeline:

    pending_validator ──▶ pending_de_upload ──▶ pending_print ──▶ printed      (sebagian)
                      └─▶ pending_de_upload ──▶ rts_triggered                  (semua)

* The VALIDATOR reviews the photos first — both reject types, no exceptions. Bad evidence
  is caught here, not three steps later.
* A PARTIAL return (`sebagian`) needs a new AWB (`<SwipeAWB>-R01`): DE exports the return
  OC — origin pre-filled from the forward order — uploads it to Ninja, marks it uploaded,
  and Station IC prints, labels and repacks (Pending Print → Printed & Labelled).
* A FULL refusal (`semua`) never gets a new AWB and never reaches print: RTS is triggered
  on the original forward tracking number, marked in bulk and exported as a list.

Stages are DERIVED from timestamps, never stored, so a row can never claim a stage its
own history does not support. Legacy rows: `acknowledged_at` (the pre-24-Aug flow) counts
as validated, and rows closed by pasted TIDs stay visible as `tids_sent`.
"""
import csv
import io

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

import db
import oc_engine
from security import require_roles

router = APIRouter(prefix="/api/returns", tags=["returns"])

# Everyone in the loop can SEE the worklist — IC needs to know what is coming to print
# long before it is theirs to act on ("Station IC can still see it", 19 Aug).
viewer_roles = require_roles("implant", "de", "station_ic", "program_manager", "validator")
validator_roles = require_roles("validator", "program_manager")
de_roles = require_roles("implant", "de")
# The RTS list is uploaded by the Validator team per the 19 Aug decision, but DE can too.
rts_roles = require_roles("validator", "implant", "de")
printer_roles = require_roles("station_ic", "implant", "de")

# The account the deck mandates for replacement return TIDs.
RTS_SHIPPER_ID = "11398434"

STAGES = (
    "pending_validator", "pending_de_upload", "pending_print",
    "printed", "rts_triggered", "tids_sent",
)

_SELECT = """
    SELECT rp.id, rp.original_awb_id, rp.return_type, rp.service_id, rp.return_awb_id,
           rp.created_at        AS rejected_at,
           rp.acknowledged_at, rp.return_tids, rp.tids_sent_at,
           rp.rts_requested_at, rp.reject_pcs,
           rp.validated_at, rp.de_uploaded_at, rp.printed_at,
           COALESCE(rp.origin, a.origin) AS origin,
           a.pharmacy_name, a.city, a.hub_name, a.phone, a.address,
           val.google_email     AS validated_by_email,
           dup.google_email     AS de_uploaded_by_email,
           prt.google_email     AS printed_by_email,
           rts.google_email     AS rts_requested_by_email
      FROM return_parcel rp
      LEFT JOIN awb   a   ON a.awb_id   = rp.original_awb_id
      LEFT JOIN users val ON val.id     = rp.validated_by
      LEFT JOIN users dup ON dup.id     = rp.de_uploaded_by
      LEFT JOIN users prt ON prt.id     = rp.printed_by
      LEFT JOIN users rts ON rts.id     = rp.rts_requested_by
"""

_TIMES = ("rejected_at", "acknowledged_at", "tids_sent_at", "rts_requested_at",
          "validated_at", "de_uploaded_at", "printed_at")


def _is_full(row: dict) -> bool:
    """A whole-consignment refusal. Closes by RTS on the FORWARD tracking number."""
    return row.get("return_type") == "semua"


def _validated(row: dict) -> bool:
    # acknowledged_at is the pre-24-Aug flow's tick; treating it as validated keeps old
    # rows moving instead of dumping them back on the Validator.
    return bool(row.get("validated_at") or row.get("acknowledged_at"))


def _stage(row: dict) -> str:
    if row.get("tids_sent_at"):
        return "tids_sent"  # legacy close (pasted TIDs, pre-24-Aug)
    if _is_full(row):
        if row.get("rts_requested_at"):
            return "rts_triggered"
    else:
        if row.get("printed_at"):
            return "printed"
        if row.get("de_uploaded_at"):
            return "pending_print"
    return "pending_de_upload" if _validated(row) else "pending_validator"


def _shape(row: dict) -> dict:
    for k in _TIMES:
        row[k] = str(row[k]) if row[k] else None
    row["stage"] = _stage(row)
    # A return with no recorded origin cannot be addressed home — DE must set it (in
    # bulk from the worklist) before the return OC can be exported.
    row["origin_unknown"] = not row.get("origin")
    # Which closing pipeline this row is on, so the UI never re-derives the rule.
    row["closes_by"] = "rts" if _is_full(row) else "return_oc"
    return row


async def _rows(ids: list[int] | None = None) -> list[dict]:
    rows = await db.fetch_all(f"{_SELECT} ORDER BY rp.created_at DESC, rp.id DESC LIMIT 500")
    shaped = [_shape(r) for r in rows]
    if ids is not None:
        want = set(ids)
        shaped = [r for r in shaped if r["id"] in want]
    return shaped


async def _proof_photos(awb_id: str) -> list[dict]:
    """The at-the-door reject evidence, so the Validator can judge what they're approving."""
    rows = await db.fetch_all(
        "SELECT doc_type, photo_ref FROM document_capture WHERE awb_id = %s "
        "AND doc_type IN ('rejected_goods', 'delivery_note', 'awb_sticker') ORDER BY id",
        (awb_id,),
    )
    return [{"doc_type": r["doc_type"], "photo_url": f"/api/media/{r['photo_ref']}"} for r in rows]


@router.get("")
async def list_returns(
    stage: str | None = Query(default=None, description="|".join(STAGES)),
    _: dict = Depends(viewer_roles),
):
    """The worklist, newest first. Stage filtering is done on the DERIVED stage."""
    if stage and stage not in STAGES:
        raise HTTPException(status_code=400, detail="bad_stage")
    out = []
    for r in await _rows():
        if stage and r["stage"] != stage:
            continue
        r["proof_photos"] = await _proof_photos(r["original_awb_id"])
        out.append(r)
    return {"returns": out, "rts_shipper_id": RTS_SHIPPER_ID}


# ------------------------------------------------------------- validator ----
@router.post("/validate")
async def validate_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(validator_roles),
):
    """The Validator confirms the photos show what the driver claimed — both reject types.

    Nothing downstream (OC export, RTS, print) is possible until this happened; catching
    bad evidence here is the whole reason the stage exists.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if r["stage"] == "pending_validator":
            await db.execute(
                "UPDATE return_parcel SET validated_at = NOW(), validated_by = %s, "
                "updated_at = NOW() WHERE id = %s", (user["id"], r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_validated', 'return_parcel', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


# ---------------------------------------------------------------- origin ----
@router.post("/origin")
async def set_origin_bulk(
    ids: list[int] = Body(..., embed=True),
    origin: str = Body(..., embed=True),
    user: dict = Depends(viewer_roles),
):
    """Bulk-set the origin on rows whose forward order predates origin tracking.

    Only rows that are still origin-unknown are touched — a stored origin is a fact about
    what happened and is never overwritten from a list selection.
    """
    if origin not in oc_engine.CFG.get("origins", {}):
        raise HTTPException(status_code=400, detail="bad_origin")
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if r["origin_unknown"]:
            await db.execute(
                "UPDATE return_parcel SET origin = %s, updated_at = NOW() WHERE id = %s",
                (origin, r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_origin_bulk_set', 'return_parcel', %s)",
        (user["email"], f"{updated} rows -> {origin}"),
    )
    return {"updated": updated, "origin": origin}


# --------------------------------------------------- sebagian: DE pipeline ----
def _exportable_oc(rows: list[dict]) -> list[dict]:
    return [r for r in rows
            if r["stage"] == "pending_de_upload" and not _is_full(r) and not r["origin_unknown"]]


@router.get("/export-oc.xlsx")
async def export_return_oc(_: dict = Depends(de_roles)):
    """The return OC workbook for every validated partial reject awaiting upload.

    One row per reject, `<SwipeAWB>-R01`, addressed from the pharmacy back to the origin
    warehouse recorded on the forward order. Rows whose origin is unknown are EXCLUDED —
    exporting them would ship the parcel to the wrong city; fix them via the origin-unknown
    filter first.
    """
    rows = _exportable_oc(await _rows())
    if not rows:
        raise HTTPException(status_code=404, detail="no_exportable_rows")
    data = oc_engine.build_return_rows([{
        "awb_id": r["original_awb_id"],
        "pharmacy_name": r["pharmacy_name"] or "",
        "phone": r["phone"] or "",
        "address": r["address"] or "",
        "origin": r["origin"],
        "reject_pcs": r["reject_pcs"],
    } for r in rows])
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Return-OC-pending.xlsx"'},
    )


@router.post("/mark-uploaded")
async def mark_uploaded_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(de_roles),
):
    """DE confirms the exported return OC went into Ninja — rows move to Pending Print.

    Stamps the generated `-R01` on the row so Station IC has the tracking number to search
    in OPV2 without deriving anything.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if r["stage"] == "pending_de_upload" and not _is_full(r):
            if r["origin_unknown"]:
                raise HTTPException(status_code=409, detail="origin_unknown")
            await db.execute(
                "UPDATE return_parcel SET de_uploaded_at = NOW(), de_uploaded_by = %s, "
                "return_awb_id = %s, updated_at = NOW() WHERE id = %s",
                (user["id"], oc_engine.return_trid(r["original_awb_id"])[:40], r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_oc_uploaded', 'return_parcel', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


@router.post("/mark-printed")
async def mark_printed_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(printer_roles),
):
    """Station IC printed the label and repacked the parcel — the row closes."""
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if r["stage"] == "pending_print":
            await db.execute(
                "UPDATE return_parcel SET printed_at = NOW(), printed_by = %s, "
                "updated_at = NOW() WHERE id = %s", (user["id"], r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_printed', 'return_parcel', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


# ------------------------------------------------------- semua: RTS pipeline --
@router.post("/rts")
async def mark_rts_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(rts_roles),
):
    """Bulk-mark validated full refusals as RTS-triggered on their forward AWB.

    No new tracking number exists or is created — the parcel travels back on its original
    label, which is why this branch never reaches Pending Print.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if _is_full(r) and r["stage"] == "pending_de_upload":
            await db.execute(
                "UPDATE return_parcel SET rts_requested_at = NOW(), rts_requested_by = %s, "
                "updated_at = NOW() WHERE id = %s", (user["id"], r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_rts_bulk', 'return_parcel', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


@router.get("/export-rts.csv")
async def export_rts_csv(_: dict = Depends(rts_roles)):
    """Every validated full refusal, as the list the Validator team uploads to trigger RTS.

    Includes rows already marked (rts_marked = yes) so the file matches what was just
    bulk-marked in the UI — the mark and the export are two halves of one action.
    """
    rows = [r for r in await _rows()
            if _is_full(r) and r["stage"] in ("pending_de_upload", "rts_triggered")]
    if not rows:
        raise HTTPException(status_code=404, detail="no_exportable_rows")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["forward_tracking_id", "pharmacy", "hub", "reject_pcs", "rejected_at", "rts_marked"])
    for r in rows:
        w.writerow([
            r["original_awb_id"], r["pharmacy_name"] or "", r["hub_name"] or "",
            r["reject_pcs"] or "", r["rejected_at"] or "",
            "yes" if r["stage"] == "rts_triggered" else "no",
        ])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="RTS-list.csv"'})


# ------------------------------------------------------------------ audit ----
@router.get("/export.csv")
async def export_csv(_: dict = Depends(viewer_roles)):
    """Flat export of the worklist with its full audit trail."""
    rows = await _rows()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "return_id", "forward_awb", "return_awb", "pharmacy", "city", "reject_type",
        "rejected_at", "stage", "closes_by", "hub", "origin", "reject_pcs",
        "validated_at", "validated_by", "de_uploaded_at", "de_uploaded_by",
        "printed_at", "printed_by", "rts_requested_at", "rts_requested_by",
        "legacy_return_tids",
    ])
    for s in rows:
        w.writerow([
            s["id"], s["original_awb_id"], s["return_awb_id"] or "",
            s["pharmacy_name"] or "", s["city"] or "",
            s["return_type"], s["rejected_at"] or "", s["stage"], s["closes_by"],
            s["hub_name"] or "", s["origin"] or "", s["reject_pcs"] or "",
            s["validated_at"] or "", s["validated_by_email"] or "",
            s["de_uploaded_at"] or "", s["de_uploaded_by_email"] or "",
            s["printed_at"] or "", s["printed_by_email"] or "",
            s["rts_requested_at"] or "", s["rts_requested_by_email"] or "",
            s["return_tids"] or "",
        ])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="reject-returns.csv"'})

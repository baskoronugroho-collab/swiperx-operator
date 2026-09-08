"""Lane 3 — the reject-return worklist (validator gate removed 31 Aug 2026).

A courier reject lands on the DE's desk the moment it is submitted — there is no queue in
front of it any more:

    pending_de_upload ──▶ pending_print ──▶ printed      (sebagian)
    pending_de_upload ──▶ rts_triggered                  (semua)

* A PARTIAL return (`sebagian`) needs a new AWB, built from the PO the courier picked at the
  door: parcel `<PO>1`, its one piece `<PO>1-R01` (8 Sep 2026 — they used to be the same
  `<SwipeAWB>-R01` string, which the OC system rejects). DE sets the origin if the forward
  order never recorded one, exports the return OC CSV, uploads it to Ninja and marks it
  uploaded; Station IC then prints, labels and repacks.
* A FULL refusal (`semua`) never gets a new AWB and never reaches print: RTS is triggered
  on the original forward tracking number, marked in bulk and exported as a list.

The one step BACKWARDS on this lane is `pending_print → pending_de_upload` (`/reopen-upload`,
DE / implant / program_manager): a DE who marks the OC uploaded before exporting the CSV
strands the row, because the export only ever contains `pending_de_upload` rows. Station IC,
who is the one who finds out — the `-R01` is not in OPV2 — cannot make that move; they raise a
remark on the row instead (`/flag`), which is what DE reads before pressing it. A flag is a
note, never a stage: it moves nothing, and it clears when the row goes back.

The VALIDATOR pre-check is gone (31 Aug 2026). It held every reject — both types — behind a
second pair of eyes on the door photos, which is a queue the pilot cannot staff; the photos
are still attached to every row and DE sees them before acting. Rows validated under the old
flow keep their `validated_at`/`validated_by` stamps: those are facts about what happened,
so they stay in the trail and the audit export, they just no longer gate anything.

Stages are DERIVED from timestamps, never stored, so a row can never claim a stage its own
history does not support. Rows closed by pasted TIDs stay visible as `tids_sent`.
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
# long before it is theirs to act on ("Station IC can still see it", 19 Aug). `validator` is
# deliberately absent: the role no longer has a step on this lane.
viewer_roles = require_roles("implant", "de", "station_ic", "program_manager")
de_roles = require_roles("implant", "de")
# RTS moved to DE with the validator gate (31 Aug) — it is the same person who exports the
# return OC, so both closing paths now start from one desk.
rts_roles = require_roles("implant", "de")
printer_roles = require_roles("station_ic", "implant", "de")
# Sending a Pending Print row BACK is a DE-desk decision — it un-does DE's own upload stamp
# and puts the row back in the export file. Station IC is deliberately NOT here: an IC who
# cannot find the AWB raises a flag on the row instead (`/flag`), and DE acts on it.
reopen_roles = require_roles("implant", "de", "program_manager")
# Raising that flag is Station IC's move, from the bench, at the moment the search fails.
flag_roles = require_roles("station_ic", "implant", "de")
# Filling in a PO by hand is the superadmin's alone. It is the one field on this lane whose
# real answer only ever existed at the door, so writing one afterwards is a judgement call
# about a fact nobody witnessed — not a step in anyone's daily work.
po_admin_roles = require_roles("superadmin")

# The account the deck mandates for replacement return TIDs.
RTS_SHIPPER_ID = "11398434"

STAGES = (
    "pending_de_upload", "pending_print", "printed", "rts_triggered", "tids_sent",
)

_SELECT = """
    SELECT rp.id, rp.original_awb_id, rp.return_type, rp.service_id, rp.return_awb_id,
           rp.created_at        AS rejected_at,
           rp.acknowledged_at, rp.return_tids, rp.tids_sent_at,
           rp.rts_requested_at, rp.reject_pcs,
           -- The PO the courier picked. For rows filed BEFORE they were asked (8 Sep 2026)
           -- fall back to the forward order's PO — but only where it has exactly one, so
           -- there is nothing to choose. `HAVING COUNT(*) = 1` with no GROUP BY makes the
           -- subquery return NULL the moment the AWB has two, which is the honest answer:
           -- nobody can say afterwards which one a box of strips came from.
           COALESCE(rp.po_number,
                    (SELECT MIN(pl.po_number) FROM po_line pl
                      WHERE pl.awb_id = rp.original_awb_id HAVING COUNT(*) = 1)) AS po_number,
           rp.validated_at, rp.de_uploaded_at, rp.printed_at,
           rp.flag_note, rp.flagged_at,
           COALESCE(rp.origin, a.origin) AS origin,
           a.pharmacy_name, a.city, a.hub_name, a.phone, a.address,
           val.google_email     AS validated_by_email,
           dup.google_email     AS de_uploaded_by_email,
           prt.google_email     AS printed_by_email,
           rts.google_email     AS rts_requested_by_email,
           flg.google_email     AS flagged_by_email
      FROM return_parcel rp
      LEFT JOIN awb   a   ON a.awb_id   = rp.original_awb_id
      LEFT JOIN users val ON val.id     = rp.validated_by
      LEFT JOIN users dup ON dup.id     = rp.de_uploaded_by
      LEFT JOIN users prt ON prt.id     = rp.printed_by
      LEFT JOIN users rts ON rts.id     = rp.rts_requested_by
      LEFT JOIN users flg ON flg.id     = rp.flagged_by
"""

_TIMES = ("rejected_at", "acknowledged_at", "tids_sent_at", "rts_requested_at",
          "validated_at", "de_uploaded_at", "printed_at", "flagged_at")


def _is_full(row: dict) -> bool:
    """A whole-consignment refusal. Closes by RTS on the FORWARD tracking number."""
    return row.get("return_type") == "semua"


def _stage(row: dict) -> str:
    """Derived from what the row can prove about itself, newest fact first.

    Submission IS the entry event now, so the fallback is `pending_de_upload`: a reject that
    has had nothing done to it is waiting on DE, never on a queue in front of DE.
    """
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
    return "pending_de_upload"


def _shape(row: dict) -> dict:
    for k in _TIMES:
        row[k] = str(row[k]) if row[k] else None
    row["stage"] = _stage(row)
    # A return with no recorded origin cannot be addressed home — DE must set it (in
    # bulk from the worklist) before the return OC can be exported.
    row["origin_unknown"] = not row.get("origin")
    # And with no PO it has no tracking number: the return OC's `requested_tracking_number`
    # IS `<PO>1`. Unlike origin this is NOT fixable from a desk — only the courier at the
    # counter knew which PO the goods came from — so these rows are held out of the export
    # rather than offered a bulk-set. Full refusals never carry one: no OC row, no field.
    row["po_unknown"] = not _is_full(row) and not row.get("po_number")
    # Filled in by the list route for the rows that need it (superadmin's picker).
    row["po_options"] = []
    # Which closing pipeline this row is on, so the UI never re-derives the rule.
    row["closes_by"] = "rts" if _is_full(row) else "return_oc"
    # A Station IC remark hanging on the row. NOT a stage — it moves nothing, it just makes
    # the row shout on DE's screen with the reason written on it.
    row["flagged"] = bool(row.get("flagged_at"))
    return row


async def _rows(ids: list[int] | None = None) -> list[dict]:
    rows = await db.fetch_all(f"{_SELECT} ORDER BY rp.created_at DESC, rp.id DESC LIMIT 500")
    shaped = [_shape(r) for r in rows]
    if ids is not None:
        want = set(ids)
        shaped = [r for r in shaped if r["id"] in want]
    return shaped


async def _proof_photos(awb_id: str) -> list[dict]:
    """The at-the-door reject evidence, shown on the row so DE sees it before acting."""
    rows = await db.fetch_all(
        "SELECT doc_type, photo_ref FROM document_capture WHERE awb_id = %s "
        "AND doc_type IN ('rejected_goods', 'delivery_note', 'awb_sticker') ORDER BY id",
        (awb_id,),
    )
    return [{"doc_type": r["doc_type"], "photo_url": f"/api/media/{r['photo_ref']}"} for r in rows]


async def _po_options(awb_id: str) -> list[dict]:
    """The forward order's PO lines — the SAME list the courier was shown at the door.

    Read from `po_line`, in the order they came off the TMP file, so a superadmin filling a
    gap is choosing between the real POs on that consignment and nothing else.
    """
    rows = await db.fetch_all(
        "SELECT po_number, koli FROM po_line WHERE awb_id = %s ORDER BY id", (awb_id,)
    )
    return [{"po_number": r["po_number"], "koli": r["koli"]} for r in rows]


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
        # What a superadmin may choose from, on the rows that need it. Fetched only for
        # those: it is the forward order's own PO lines, the same list the courier saw.
        r["po_options"] = await _po_options(r["original_awb_id"]) if r["po_unknown"] else []
        out.append(r)
    return {"returns": out, "rts_shipper_id": RTS_SHIPPER_ID}


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
            if r["stage"] == "pending_de_upload" and not _is_full(r)
            and not r["origin_unknown"] and not r["po_unknown"]]


@router.get("/export-oc.csv")
async def export_return_oc(_: dict = Depends(de_roles)):
    """The return OC CSV for every partial reject awaiting upload.

    One row per reject, tracking number `<PO>1` with a single piece `<PO>1-R01`, addressed
    from the pharmacy back to the origin warehouse recorded on the forward order.

    Two kinds of row are EXCLUDED. Origin-unknown, because exporting them would ship the
    parcel to the wrong city — DE clears those with the origin-unknown filter first, which is
    why setting the origin comes before the export. And PO-unknown, because the tracking
    number is built from the PO and there is nothing to build it from; those are legacy rows
    filed before the courier was asked, and no desk can answer for them.
    """
    rows = _exportable_oc(await _rows())
    if not rows:
        raise HTTPException(status_code=404, detail="no_exportable_rows")
    data = oc_engine.build_return_csv([{
        "awb_id": r["original_awb_id"],
        "po_number": r["po_number"],
        "pharmacy_name": r["pharmacy_name"] or "",
        "phone": r["phone"] or "",
        "address": r["address"] or "",
        "origin": r["origin"],
        "reject_pcs": r["reject_pcs"],
    } for r in rows])
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="Return-OC-pending.csv"'},
    )


@router.post("/mark-uploaded")
async def mark_uploaded_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(de_roles),
):
    """DE confirms the exported return OC went into Ninja — rows move to Pending Print.

    Stamps the generated `<PO>1` on the row so Station IC has the tracking number to search
    in OPV2 without deriving anything. A row with no PO has no such number and is refused
    here for the same reason it is held out of the export.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    updated = 0
    for r in await _rows(ids):
        if r["stage"] == "pending_de_upload" and not _is_full(r):
            if r["origin_unknown"]:
                raise HTTPException(status_code=409, detail="origin_unknown")
            if r["po_unknown"]:
                raise HTTPException(status_code=409, detail="po_unknown")
            await db.execute(
                "UPDATE return_parcel SET de_uploaded_at = NOW(), de_uploaded_by = %s, "
                "return_awb_id = %s, updated_at = NOW() WHERE id = %s",
                (user["id"], oc_engine.return_trid(r["po_number"])[:40], r["id"]),
            )
            updated += 1
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_oc_uploaded', 'return_parcel', %s)",
        (user["email"], f"{updated} rows"),
    )
    return {"updated": updated}


@router.post("/po")
async def set_po(
    id: int = Body(..., embed=True),
    po_number: str = Body(..., embed=True),
    user: dict = Depends(po_admin_roles),
):
    """Superadmin fills in the PO on a row that has none. One row at a time, by hand.

    Why this exists: a reject filed before couriers were asked (8 Sep 2026) carries no PO, and
    without one there is no `requested_tracking_number` to issue — the row cannot be exported
    and is stuck on Pending DE upload forever. Somebody has to be able to unstick it.

    Why superadmin only: the honest answer to "which PO did these goods come from" existed for
    a few seconds at a pharmacy counter and was not written down. Anyone filling it in
    afterwards is reconstructing it from the delivery note or a phone call, which is a
    judgement call about a fact nobody recorded — not a step in DE's or IC's daily work. It is
    deliberately awkward, deliberately one row at a time, and deliberately logged.

    Two limits, both on purpose:

    * The PO must be one of the FORWARD ORDER'S OWN `po_line` rows. A free-typed value would
      mint a tracking number for an order that does not exist — the same rule the courier's
      pick is held to.
    * Only a row that HAS no PO. A PO the courier chose is a fact from the door and is never
      overwritten from a desk, exactly as a stored origin is never overwritten.
    """
    rows = await _rows([id])
    if not rows:
        raise HTTPException(status_code=404, detail="not_found")
    row = rows[0]
    if _is_full(row):
        raise HTTPException(status_code=409, detail="full_refusal_has_no_oc_row")
    if not row["po_unknown"]:
        raise HTTPException(status_code=409, detail="po_already_set")
    if po_number not in {p["po_number"] for p in await _po_options(row["original_awb_id"])}:
        raise HTTPException(status_code=422, detail="po_number_not_on_awb")
    await db.execute(
        "UPDATE return_parcel SET po_number = %s, updated_at = NOW() WHERE id = %s",
        (po_number, id),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_po_set_by_hand', 'return_parcel', %s)",
        (user["email"], f"{id} -> {po_number}"),
    )
    return {"updated": 1, "po_number": po_number}


# ------------------------------------------------- station IC: the flag ----
FLAG_MAX = 500


@router.post("/flag")
async def flag_bulk(
    ids: list[int] = Body(..., embed=True),
    note: str = Body(..., embed=True),
    user: dict = Depends(flag_roles),
):
    """Station IC attaches a remark to a Pending Print row — normally "AWB not in NV".

    The bench case: IC searches the `-R01` in OPV2 to print the label and it is not there,
    because the OC was marked uploaded without the CSV ever being exported, so Ninja never
    issued it. The IC cannot fix that — sending a row back is DE's move (`/reopen-upload`) —
    but they are the only person who knows, and until now the news travelled by chat group.

    So this MOVES NOTHING. It is a note, and its whole job is to put the row in front of DE
    with the reason written on it. Only `pending_print` rows take one: that is the only stage
    where an IC is hunting for an AWB, and a flag anywhere else would describe nothing.

    One flag per row, replaced by the next. The audit log keeps every raise — the row keeps
    only the current one, because what DE needs to read is the reason it is stuck TODAY.
    """
    note = (note or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="no_note")
    if len(note) > FLAG_MAX:
        raise HTTPException(status_code=400, detail="note_too_long")
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    flagged = []
    for r in await _rows(ids):
        if r["stage"] == "pending_print":
            await db.execute(
                "UPDATE return_parcel SET flag_note = %s, flagged_at = NOW(), flagged_by = %s, "
                "updated_at = NOW() WHERE id = %s", (note, user["id"], r["id"]),
            )
            flagged.append(r["id"])
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_flagged', 'return_parcel', %s)",
        (user["email"], f"{flagged}: {note}"),
    )
    return {"updated": len(flagged)}


@router.post("/unflag")
async def unflag_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(reopen_roles),
):
    """Clear the flag without moving the row — DE looked, and the AWB is really there.

    Same desk as `/reopen-upload`, because both are the answer to a flag: either the row goes
    back to be re-exported, or the IC is told to look again. Leaving it to the raiser would
    let a flag be withdrawn before anyone read it.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    cleared = []
    for r in await _rows(ids):
        if r["flagged"]:
            await db.execute(
                "UPDATE return_parcel SET flag_note = NULL, flagged_at = NULL, "
                "flagged_by = NULL, updated_at = NOW() WHERE id = %s", (r["id"],),
            )
            cleared.append(r["id"])
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_unflagged', 'return_parcel', %s)",
        (user["email"], f"{cleared}"),
    )
    return {"updated": len(cleared)}


@router.post("/reopen-upload")
async def reopen_upload_bulk(
    ids: list[int] = Body(..., embed=True),
    user: dict = Depends(reopen_roles),
):
    """Send a Pending Print row back to Pending DE upload.

    The failure this exists for: DE marks the OC uploaded WITHOUT having exported the CSV
    first. The row moves to Pending Print, and the return OC export only ever contains
    `pending_de_upload` rows (`_exportable_oc`) — so the file that has to go into Ninja can
    no longer be produced, and the parcel is stuck with a label nobody can print.

    DE, implant and program_manager only. Station IC is the one who NOTICES — the `-R01` is not
    in OPV2 and the parcel is on their bench — but the move itself belongs to the desk that
    made the upload claim and has to re-run export → mark uploaded. The IC's route in is
    `/flag`: a remark on the row, which is what DE reads before pressing this.

    Reversal means CLEARING `de_uploaded_at` (and the `-R01` it stamped), because the stage
    is derived from the timestamps: leaving the stamp would leave the row claiming an upload
    that never happened. The reversal itself is recorded in `audit_log`, with the row ids —
    that is where the history of the correction lives.

    Only `pending_print` rows move. A `printed` row is past this door (Station IC already
    printed and labelled), and `pending_de_upload` is already where this sends things. Any
    flag on the row is cleared with the stamp — the reason for it is being acted on.
    """
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    moved = []
    for r in await _rows(ids):
        if r["stage"] == "pending_print":
            # The flag goes with it: "can't find this AWB" is answered by the row going
            # back to be exported, and a stale flag would send DE looking twice.
            await db.execute(
                "UPDATE return_parcel SET de_uploaded_at = NULL, de_uploaded_by = NULL, "
                "return_awb_id = NULL, flag_note = NULL, flagged_at = NULL, flagged_by = NULL, "
                "updated_at = NOW() WHERE id = %s", (r["id"],),
            )
            moved.append(r["id"])
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'return_upload_reopened', 'return_parcel', %s)",
        (user["email"], f"{moved} -> pending_de_upload"),
    )
    return {"updated": len(moved)}


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
    """Bulk-mark full refusals as RTS-triggered on their forward AWB.

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
    """Every full refusal, as the list DE uploads to trigger RTS.

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
        "rejected_at", "stage", "closes_by", "hub", "origin", "po_number", "reject_pcs",
        "legacy_validated_at", "legacy_validated_by", "de_uploaded_at", "de_uploaded_by",
        "printed_at", "printed_by", "rts_requested_at", "rts_requested_by",
        "flagged_at", "flagged_by", "flag_note", "legacy_return_tids",
    ])
    for s in rows:
        w.writerow([
            s["id"], s["original_awb_id"], s["return_awb_id"] or "",
            s["pharmacy_name"] or "", s["city"] or "",
            s["return_type"], s["rejected_at"] or "", s["stage"], s["closes_by"],
            s["hub_name"] or "", s["origin"] or "", s["po_number"] or "", s["reject_pcs"] or "",
            s["validated_at"] or "", s["validated_by_email"] or "",
            s["de_uploaded_at"] or "", s["de_uploaded_by_email"] or "",
            s["printed_at"] or "", s["printed_by_email"] or "",
            s["rts_requested_at"] or "", s["rts_requested_by_email"] or "",
            s["flagged_at"] or "", s["flagged_by_email"] or "", s["flag_note"] or "",
            s["return_tids"] or "",
        ])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="reject-returns.csv"'})

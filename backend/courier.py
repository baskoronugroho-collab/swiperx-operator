"""M2 — courier capture, reached only through the tokenized link.

Every route here is UNAUTHENTICATED by design: the per-AWB `link_token` is the sole
credential (FR-OC2), so there is no session and no user. That makes two rules absolute:

  * a token resolves to exactly one AWB and can never reach another one's data;
  * media uploaded here is served back only through `/api/c/<token>/media/<ref>`,
    scoped to that same AWB — never through the session-gated `/api/media/<key>`.

Completeness gate (PRD §9): the courier cannot submit until every required photo for the
chosen outcome exists AND the signed+stamped attestation is ticked. The gate is computed
server-side in `_requirements()` so a tampered client cannot bypass it.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

import db
from storage import store

router = APIRouter(prefix="/api/c", tags=["courier"])

LINK_TTL_DAYS = 30  # PRD §10, LOCKED
MAX_PHOTO_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

DOC_TYPES = {
    "pharmacy_pod", "receiver_pod", "delivery_note", "sp_manual",
    "rejected_goods", "awb_sticker", "return_form",
}
# Documents that may appear more than once per AWB.
#
# `awb_sticker` joined this on 10 Aug 2026: a partial return can send back parcels from
# several POs, each with its own label, and one shot cannot cover them. `rejected_goods`
# was already repeatable server-side but the wizard only ever rendered one slot, so in
# practice both were single — the UI now lists every photo taken.
REPEATABLE = {"sp_manual", "delivery_note", "rejected_goods", "awb_sticker"}

# PRD §7.2.1 — LOCKED 09 Jul. Order matters: it is the order the courier app renders.
FAIL_REASONS = [
    ("cancelled", "Penerima membatalkan pesanan", "Recipient cancels the order"),
    ("not_ordered", "Penerima tidak memesan paket", "Recipient did not order the package"),
    ("address_wrong", "Alamat tidak lengkap atau salah", "Address incomplete or wrong"),
    ("moved", "Penerima sudah pindah dari lokasi", "Recipient has moved from the location"),
    ("no_receiver", "Penerima tidak ada di lokasi", "Recipient not at the location"),
    ("reschedule", "Penerima meminta untuk penjadwalan ulang", "Recipient asks for a reschedule"),
    ("office_closed", "Kantor tutup", "Office closed"),
    ("force_majeure", "Bencana alam, huru-hara, atau musibah/kecelakaan",
     "Natural disaster, riot, or accident"),
    ("refused_sign", "Penerima tidak mau menandatangani dokumen",
     "Recipient refuses to sign the documents"),
]
FAIL_CODES = {c for c, _, _ in FAIL_REASONS}

TERMINAL_STATUSES = {"delivered", "arrived", "handed_over", "delivery_failed"}


# --------------------------------------------------------------- helpers ----
async def _load(token: str) -> dict:
    awb = await db.fetch_one(
        "SELECT awb_id, merchant_order_number, pharmacy_name, address, city, service_id, status, "
        "is_return, invoice, item_detail, return_type, created_at FROM awb WHERE link_token = %s",
        (token,),
    )
    if not awb:
        raise HTTPException(status_code=404, detail="invalid_link")
    awb["is_return"] = bool(awb["is_return"])
    return awb


def _expired(awb: dict) -> bool:
    created = awb.get("created_at")
    if not isinstance(created, datetime):
        return False
    return datetime.now() - created > timedelta(days=LINK_TTL_DAYS)


async def _guard_open(token: str) -> dict:
    """Resolve the token and refuse writes on an expired or terminal AWB."""
    awb = await _load(token)
    if _expired(awb):
        raise HTTPException(status_code=410, detail="link_expired")
    if awb["status"] in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="already_submitted")
    return awb


async def _captures(awb_id: str, token: str) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT id, doc_type, po_number, photo_ref, signed_stamped, captured_at "
        "FROM document_capture WHERE awb_id = %s ORDER BY id", (awb_id,)
    )
    out = []
    for r in rows:
        out.append({
            "id": r["id"], "doc_type": r["doc_type"], "po_number": r["po_number"],
            "photo_url": f"/api/c/{token}/media/{r['photo_ref']}",
            "signed_stamped": None if r["signed_stamped"] is None else bool(r["signed_stamped"]),
            "captured_at": str(r["captured_at"]),
        })
    return out


def _requirements(awb: dict, outcome: str, captures: list[dict]) -> list[str]:
    """Missing requirements for `outcome`. Empty list = the completeness gate passes.

    Forward normal delivery (§7.1): pharmacy POD, receiver POD, DN whole document with a
    signed+stamped attestation on the forward section. SP-Manual is rider-driven — the
    rider decides which POs need one at the door — so it is never *required* here.

    Reject (§7.2): additionally the DN return section (close-up + full page = 2 DN shots),
    one overall photo of the rejected goods, and the forward AWB sticker.

    Return service (§7.4): no DN; the courier prepares the BA and captures it. A success
    with nothing to collect still needs the blank-but-signed return form.
    """
    have = {}
    for c in captures:
        have.setdefault(c["doc_type"], []).append(c)
    missing: list[str] = []

    def need(doc: str, label: str, count: int = 1):
        if len(have.get(doc, [])) < count:
            missing.append(label)

    if awb["is_return"]:
        need("return_form", "Foto BA Retur / return form")
        if outcome == "reject":
            need("rejected_goods", "Foto barang retur")
        return missing

    need("pharmacy_pod", "Foto apotek")
    need("receiver_pod", "Foto penerima")
    need("delivery_note", "Foto Delivery Note")

    dn = have.get("delivery_note", [])
    if not any(c["signed_stamped"] for c in dn):
        missing.append("Centang Delivery Note sudah ditandatangani & distempel")

    if outcome == "reject":
        need("delivery_note", "Dua foto Delivery Note (close-up bagian retur + halaman penuh)", 2)
        need("rejected_goods", "Foto barang yang ditolak")
        need("awb_sticker", "Foto label AWB")

    return missing


# ------------------------------------------------------------- read-only ----
@router.get("/{token}/order")
async def order(token: str):
    """Everything the courier app renders, plus enough state to resume in place."""
    awb = await _load(token)
    captures = await _captures(awb["awb_id"], token)
    po_lines = await db.fetch_all(
        "SELECT po_number, koli FROM po_line WHERE awb_id = %s ORDER BY id", (awb["awb_id"],)
    )
    return {
        "awb_id": awb["awb_id"],
        "merchant_order_number": awb["merchant_order_number"],
        "pharmacy_name": awb["pharmacy_name"],
        "address": awb["address"],
        "city": awb["city"],
        "service_id": awb["service_id"],
        "status": awb["status"],
        "is_return": awb["is_return"],
        "invoice": awb["invoice"],
        "item_detail": awb["item_detail"],
        "po_lines": po_lines,
        "captures": captures,
        "expired": _expired(awb),
        "terminal": awb["status"] in TERMINAL_STATUSES,
        "fail_reasons": [{"code": c, "id": i, "en": e} for c, i, e in FAIL_REASONS],
    }


@router.get("/{token}/media/{ref}")
async def media(token: str, ref: str):
    """Serve a photo, scoped to the AWB this token owns — never a global blob read."""
    awb = await _load(token)
    owned = await db.fetch_one(
        "SELECT 1 AS ok FROM document_capture WHERE awb_id = %s AND photo_ref = %s",
        (awb["awb_id"], ref),
    ) or await db.fetch_one(
        "SELECT 1 AS ok FROM failed_delivery WHERE awb_id = %s AND proof_photo_ref = %s",
        (awb["awb_id"], ref),
    )
    if not owned:
        raise HTTPException(status_code=404, detail="not_found")
    found = await store.get(ref)
    if not found:
        raise HTTPException(status_code=404, detail="file_missing")
    data, content_type = found
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "private, max-age=3600"})


# ---------------------------------------------------------------- writes ----
@router.post("/{token}/capture", status_code=201)
async def capture(
    token: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    timestamp_source: str = Form("camera"),
    po_number: str | None = Form(default=None),
    signed_stamped: bool | None = Form(default=None),
    gps: str | None = Form(default=None),
):
    """Store one photo against the AWB.

    `timestamp_source` records how the capture moment was established: `camera` (live
    in-app capture, app-stamped) or `exif` (the upload fallback). Not forensic proof —
    it's deterrence, and it tells a Validator which shots to trust (PRD §7.2.1).
    """
    awb = await _guard_open(token)
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="unknown_doc_type")
    if timestamp_source not in {"camera", "exif"}:
        raise HTTPException(status_code=400, detail="bad_timestamp_source")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="photo_too_large")
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_image_type")

    if doc_type == "sp_manual" and not po_number:
        raise HTTPException(status_code=400, detail="sp_manual_needs_po")
    if po_number:
        known = await db.fetch_one(
            "SELECT 1 AS ok FROM po_line WHERE awb_id = %s AND po_number = %s",
            (awb["awb_id"], po_number),
        )
        if not known:
            raise HTTPException(status_code=400, detail="unknown_po")

    # Single-shot documents replace rather than accumulate, so a retake doesn't leave
    # the earlier (possibly bad) photo behind as evidence.
    if doc_type not in REPEATABLE:
        await db.execute(
            "DELETE FROM document_capture WHERE awb_id = %s AND doc_type = %s",
            (awb["awb_id"], doc_type),
        )
    elif doc_type == "sp_manual":
        await db.execute(
            "DELETE FROM document_capture WHERE awb_id = %s AND doc_type = 'sp_manual' AND po_number = %s",
            (awb["awb_id"], po_number),
        )

    ref = await store.put(data, content_type)
    capture_id = await db.execute(
        "INSERT INTO document_capture (awb_id, doc_type, po_number, photo_ref, signed_stamped, gps) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (awb["awb_id"], doc_type, po_number, ref,
         None if signed_stamped is None else int(signed_stamped), gps),
    )
    await db.execute(
        "UPDATE awb SET driver_submitted_at = COALESCE(driver_submitted_at, NOW()) WHERE awb_id = %s",
        (awb["awb_id"],),
    )
    return {
        "id": capture_id, "doc_type": doc_type, "po_number": po_number,
        "photo_url": f"/api/c/{token}/media/{ref}",
        "signed_stamped": signed_stamped,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp_source": timestamp_source,
    }


@router.patch("/{token}/capture/{capture_id}")
async def attest(token: str, capture_id: int, signed_stamped: bool = Body(..., embed=True)):
    """Tick/untick the signed+stamped attestation on an already-captured document."""
    awb = await _guard_open(token)
    row = await db.fetch_one(
        "SELECT id FROM document_capture WHERE id = %s AND awb_id = %s", (capture_id, awb["awb_id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    await db.execute(
        "UPDATE document_capture SET signed_stamped = %s WHERE id = %s",
        (int(signed_stamped), capture_id),
    )
    return {"id": capture_id, "signed_stamped": signed_stamped}


@router.delete("/{token}/capture/{capture_id}", status_code=204)
async def delete_capture(token: str, capture_id: int):
    """Discard a photo so the courier can retake it."""
    awb = await _guard_open(token)
    row = await db.fetch_one(
        "SELECT photo_ref FROM document_capture WHERE id = %s AND awb_id = %s",
        (capture_id, awb["awb_id"]),
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    await db.execute("DELETE FROM document_capture WHERE id = %s", (capture_id,))
    return Response(status_code=204)


@router.get("/{token}/gate")
async def gate(token: str, outcome: str = "delivered"):
    """What is still missing before `outcome` can be submitted. Drives the UI's
    disabled-confirm state; `submit` re-checks it regardless."""
    awb = await _load(token)
    if outcome not in {"delivered", "reject"}:
        raise HTTPException(status_code=400, detail="bad_outcome")
    missing = _requirements(awb, outcome, await _captures(awb["awb_id"], token))
    return {"outcome": outcome, "complete": not missing, "missing": missing}


@router.post("/{token}/submit")
async def submit(
    token: str,
    request: Request,
    outcome: str = Body(...),
    return_type: str | None = Body(default=None),
):
    """Confirm the delivery. `outcome` is `delivered` or `reject`.

    A reject also opens a row on the ops reject-return worklist (Lane 3) so the return
    is visible the moment the courier leaves the door, rather than when someone reads
    the WA group.
    """
    awb = await _guard_open(token)
    if outcome not in {"delivered", "reject"}:
        raise HTTPException(status_code=400, detail="bad_outcome")

    captures = await _captures(awb["awb_id"], token)
    missing = _requirements(awb, outcome, captures)
    if missing:
        raise HTTPException(status_code=422, detail={"error": "incomplete", "missing": missing})

    rtype = "none"
    if outcome == "reject":
        rtype = return_type if return_type in {"sebagian", "semua"} else "sebagian"

    await db.execute(
        "UPDATE awb SET status = 'delivered', return_type = %s, delivered_at = NOW(), "
        "driver_submitted_at = NOW(), submitted_by_ip = %s WHERE awb_id = %s",
        (rtype, request.client.host if request.client else None, awb["awb_id"]),
    )

    return_awbs: list[str] = []
    if outcome == "reject":
        existing = await db.fetch_one(
            "SELECT id FROM return_parcel WHERE original_awb_id = %s", (awb["awb_id"],)
        )
        if not existing:
            await db.execute(
                "INSERT INTO return_parcel (original_awb_id, return_type, service_id) "
                "VALUES (%s, %s, %s)",
                (awb["awb_id"], rtype, awb["service_id"]),
            )
        return_awbs = [awb["awb_id"]]

    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, %s, 'awb', %s)",
        (f"courier:{awb['awb_id']}", f"courier_{outcome}", awb["awb_id"]),
    )
    return {"status": "delivered", "return_flagged": outcome == "reject", "return_awbs": return_awbs}


@router.post("/{token}/fail")
async def fail(
    token: str,
    request: Request,
    fail_reason: str = Body(...),
    reason_note: str | None = Body(default=None),
    gps: str | None = Body(default=None),
):
    """Failed delivery — nothing was handed over, so there is no POD/RDO set.

    Two-step in the UI (reason → proof photo); the proof must already be uploaded via
    `/capture` with doc_type `awb_sticker`, which is the only shot this flow takes.
    No return track is opened: nothing was delivered, so there is nothing to reject.
    """
    awb = await _guard_open(token)
    if fail_reason not in FAIL_CODES:
        raise HTTPException(status_code=400, detail="unknown_fail_reason")

    proof = await db.fetch_one(
        "SELECT photo_ref, captured_at FROM document_capture "
        "WHERE awb_id = %s ORDER BY id DESC LIMIT 1", (awb["awb_id"],)
    )
    if not proof:
        raise HTTPException(status_code=422,
                            detail={"error": "incomplete", "missing": ["Foto bukti"]})

    await db.execute(
        "INSERT INTO failed_delivery (awb_id, fail_reason, reason_note, proof_photo_ref, "
        "proof_timestamp, timestamp_source, gps) VALUES (%s, %s, %s, %s, %s, 'camera', %s)",
        (awb["awb_id"], fail_reason, reason_note, proof["photo_ref"], proof["captured_at"], gps),
    )
    await db.execute(
        "UPDATE awb SET status = 'delivery_failed', fail_reason = %s, driver_submitted_at = NOW(), "
        "submitted_by_ip = %s WHERE awb_id = %s",
        (fail_reason, request.client.host if request.client else None, awb["awb_id"]),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'courier_failed', 'awb', %s)",
        (f"courier:{awb['awb_id']}", awb["awb_id"]),
    )
    return {"status": "delivery_failed", "return_flagged": False, "return_awbs": []}

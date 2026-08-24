"""M1 — OC intake & courier links.

Implant/DE uploads a SwipeRx TMP file and picks a service (S1/S2/S3); the engine parses
it, creates AWBs + PO lines with an unguessable per-AWB courier token, and stores the
generated Ninja Van upload .xlsx + links.csv. `/api/c/<token>` resolves a link to its AWB —
this is what makes a generated link open (fixes the prototype's dead link; the full
courier wizard arrives in M2).

Hub is NOT assigned here — NV assigns it after the OC is created; the Implant then
re-uploads AWB→hub separately (BUILD_HANDOFF §3.6).
"""
import secrets
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response

import config
import db
import oc_engine
from security import require_roles
from storage import store

router = APIRouter(prefix="/api/oc", tags=["oc"])
public_router = APIRouter(tags=["courier"])  # unauthenticated courier link entry
intake_roles = require_roles("implant", "de")

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _parse_delivery_date(value: str | None) -> str | None:
    """Validate the operator-chosen delivery day (ISO yyyy-mm-dd). None → engine uses today."""
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="bad_delivery_date") from None


def _parse_origin(value: str | None) -> str:
    """Which SwipeRx warehouse this batch ships out of.

    Stored on the intake AND on every AWB in it, so a return months later can address itself
    home without anyone looking the forward order up by hand — the manual step this lane
    exists to remove. Required: guessing it would send returns to the wrong city.
    """
    origins = oc_engine.CFG.get("origins", {})
    if not value or value not in origins:
        raise HTTPException(status_code=400, detail="bad_origin")
    return value


def _err_line(e: dict) -> str:
    where = e["awb"] or (f"row {e['row']}" if e.get("row") else "row ?")
    return f"{where}: {e['error']}"


def _awb_preview(a: dict) -> dict:
    return {
        "awb_id": a["awb_id"], "pharmacy_name": a["pharmacy_name"], "city": a["city"],
        "collies": a["collies"], "po_count": len(a["po_lines"]),
        "pieces": len(oc_engine.piece_trids(a)), "is_return": a["is_return"],
    }


async def _parse_upload(service: str, file: UploadFile) -> tuple[bytes, dict]:
    if service not in {s["code"] for s in oc_engine.services()}:
        raise HTTPException(status_code=400, detail="unknown_service")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")
    try:
        result = oc_engine.parse(data, service)
    except oc_engine.OcError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return data, result


@router.get("/services")
async def list_services(_: dict = Depends(intake_roles)):
    return {"services": oc_engine.services(), "origins": oc_engine.origins()}


@router.post("/preview")
async def preview(service: str = Form(...), file: UploadFile = File(...),
                  _: dict = Depends(intake_roles)):
    """Parse only — no DB writes. Lets the UI show AWBs + per-row errors before committing."""
    _, result = await _parse_upload(service, file)
    awbs = result["awbs"]
    return {
        "service": service,
        "awb_count": len(awbs),
        "piece_count": sum(len(oc_engine.piece_trids(a)) for a in awbs),
        "error_count": len(result["errors"]),
        "errors": result["errors"],
        "awbs": [_awb_preview(a) for a in awbs],
    }


@router.post("/create", status_code=201)
async def create(service: str = Form(...), file: UploadFile = File(...),
                 delivery_date: str | None = Form(default=None),
                 origin: str = Form(...),
                 user: dict = Depends(intake_roles)):
    """Commit the batch: persist AWBs + tokens and generate the NV upload .xlsx + links.csv.

    `delivery_date` is a SINGLE day (FR-OC1, Round 5 — not a range); it lands in col S
    of the upload. Omitted → today.
    """
    day = _parse_delivery_date(delivery_date)
    origin = _parse_origin(origin)
    data, result = await _parse_upload(service, file)
    awbs = result["awbs"]
    if not awbs:
        raise HTTPException(status_code=422, detail="no_valid_awbs")

    src_ref = await store.put(data, XLSX_CT)
    intake_id = await db.execute(
        "INSERT INTO order_intake (source_file_ref, service_code, uploaded_by, status, origin) "
        "VALUES (%s, %s, %s, 'processing', %s)",
        (src_ref, service, user["id"], origin),
    )

    committed, errors = [], list(result["errors"])
    for a in awbs:
        if await db.fetch_one("SELECT awb_id FROM awb WHERE awb_id = %s", (a["awb_id"],)):
            errors.append({"row": None, "awb": a["awb_id"], "error": "AWB already exists — skipped"})
            continue
        token = secrets.token_urlsafe(24)
        a["token"] = token
        # The courier link is the SPA wizard route: {base}/c/{token} (guide §2.4). Both
        # /c/* and /api/c/* are allowlisted past the platform SSO gateway, so a rider with
        # no Google account can open it. Links printed before 27 Jul used /api/c/<token>;
        # that route still resolves and 307s here, so old sheets keep working.
        a["url"] = f"{config.COURIER_BASE_URL}/c/{token}"
        a["delivery_instructions"] = oc_engine.delivery_instructions(service, a, a["url"])
        await db.execute(
            "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, city, "
            "postcode, phone, weight, koli, link_token, status, return_type, is_return, invoice, "
            "item_detail, delivery_instructions, created_by, intake_id, origin) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'created','none',%s,%s,%s,%s,%s,%s,%s)",
            (a["awb_id"], a["merchant_order_number"], service, a["pharmacy_name"], a["address"], a["city"],
             a["postcode"], a["phone"], a["weight"], a["collies"], token, 1 if a["is_return"] else 0,
             a["invoice"], a["item_detail"], a["delivery_instructions"], user["id"], intake_id, origin),
        )
        for p in a["po_lines"]:
            await db.execute(
                "INSERT INTO po_line (awb_id, po_number, koli) VALUES (%s, %s, %s)",
                (a["awb_id"], p["po_number"], p["koli"]),
            )
        committed.append(a)

    # Every AWB in the file already existed, so nothing was created. Without this the
    # intake closed as 'created' with awb_count 0 and handed back an upload.xlsx holding
    # only a header row — which reads like success and is the easiest way to ship nothing.
    # Re-uploading a corrected file lands here too: existing AWBs are skipped, never
    # updated, so the operator needs telling rather than a silent empty download.
    if not committed:
        await db.execute(
            "UPDATE order_intake SET status='no_new_awbs', row_count=0, error_summary=%s "
            "WHERE id=%s", ("; ".join(_err_line(e) for e in errors) or None, intake_id),
        )
        raise HTTPException(status_code=409, detail="all_awbs_already_exist")

    upload_ref = await store.put(oc_engine.build_upload_xlsx(service, committed, day), XLSX_CT)
    links_ref = await store.put(oc_engine.build_links_csv(committed), "text/csv")
    piece_count = sum(len(oc_engine.piece_trids(a)) for a in committed)
    err_text = "; ".join(_err_line(e) for e in errors) or None

    # Col R is compliance text with a hard 500-char cap; if the link pushed it over, the
    # engine trimmed the RDO wording. That must never pass unnoticed.
    truncated = [a["awb_id"] for a in committed
                 if oc_engine.instr_truncated(a["delivery_instructions"])]
    warn_text = (f"{len(truncated)} AWB(s) had the RDO instruction text truncated to fit the "
                 f"500-char limit: {', '.join(truncated[:5])}"
                 f"{'…' if len(truncated) > 5 else ''}") if truncated else None

    await db.execute(
        "UPDATE order_intake SET oc_template_ref=%s, links_file_ref=%s, awb_count=%s, piece_count=%s, "
        "row_count=%s, status='created', error_summary=%s, warning_summary=%s WHERE id=%s",
        (upload_ref, links_ref, len(committed), piece_count, len(committed), err_text, warn_text, intake_id),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'oc_create', 'order_intake', %s)",
        (user["email"], str(intake_id)),
    )
    return {
        "intake_id": intake_id, "service": service,
        "awb_count": len(committed), "piece_count": piece_count,
        "error_count": len(errors), "errors": errors,
        "warning": warn_text,
        "links": [{"awb_id": a["awb_id"], "pharmacy_name": a["pharmacy_name"],
                   "city": a["city"], "koli": a["collies"], "url": a["url"]} for a in committed],
        "upload_url": f"/api/oc/intakes/{intake_id}/upload.xlsx",
        "links_url": f"/api/oc/intakes/{intake_id}/links.csv",
    }


@router.get("/intakes")
async def list_intakes(_: dict = Depends(intake_roles)):
    rows = await db.fetch_all(
        "SELECT id, service_code, awb_count, piece_count, row_count, status, uploaded_at "
        "FROM order_intake ORDER BY id DESC LIMIT 100"
    )
    for r in rows:
        r["uploaded_at"] = str(r["uploaded_at"])
    return {"intakes": rows}


@router.get("/intakes/{intake_id}")
async def intake_detail(intake_id: int, _: dict = Depends(intake_roles)):
    intake = await db.fetch_one(
        "SELECT id, service_code, awb_count, piece_count, row_count, status, error_summary, uploaded_at "
        "FROM order_intake WHERE id = %s", (intake_id,)
    )
    if not intake:
        raise HTTPException(status_code=404, detail="not_found")
    intake["uploaded_at"] = str(intake["uploaded_at"])
    awbs = await db.fetch_all(
        "SELECT awb_id, pharmacy_name, city, koli, is_return, status, link_token FROM awb "
        "WHERE intake_id = %s ORDER BY awb_id", (intake_id,)
    )
    for a in awbs:
        a["is_return"] = bool(a["is_return"])
        a["courier_url"] = f"{config.COURIER_BASE_URL}/c/{a.pop('link_token')}"
    return {"intake": intake, "awbs": awbs}


@router.get("/links")
async def list_links(
    q: str | None = None,
    limit: int = 500,
    _: dict = Depends(intake_roles),
):
    """Every courier link created, newest first — the operator's copy-paste view.

    Same data as the links .csv, but on screen so a link can be found and copied without
    downloading anything (guide §5 step 8: "plus a copy-of-links view").
    """
    sql = (
        "SELECT a.awb_id, a.pharmacy_name, a.city, a.koli, a.status, a.is_return, "
        "a.link_token, a.service_id, a.intake_id, a.created_at "
        "FROM awb a"
    )
    params: tuple = ()
    if q:
        like = f"%{q.strip()}%"
        sql += " WHERE a.awb_id LIKE %s OR a.pharmacy_name LIKE %s OR a.city LIKE %s"
        params = (like, like, like)
    sql += " ORDER BY a.created_at DESC, a.awb_id DESC LIMIT %s"
    params = params + (max(1, min(limit, 2000)),)

    rows = await db.fetch_all(sql, params)
    for r in rows:
        r["is_return"] = bool(r["is_return"])
        r["created_at"] = str(r["created_at"])
        r["courier_url"] = f"{config.COURIER_BASE_URL}/c/{r.pop('link_token')}"
    return {"links": rows, "count": len(rows)}


def _slug(text: str) -> str:
    """Filesystem/Content-Disposition-safe fragment: keep word chars, collapse the rest."""
    out = "".join(c if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


async def _intake_filename(intake_id: int, kind: str, ext: str) -> str:
    """`<Service>-<kind>_<YYYYMMDD-HHMM>.<ext>` — the DE handles many of these a day.

    A bare intake id told them nothing once the file left the browser; the service and the
    moment it was generated are what they actually sort by. Falls back to the id if the
    row is somehow unreadable, so a download never fails over a filename.
    """
    row = await db.fetch_one(
        "SELECT service_code, uploaded_at FROM order_intake WHERE id = %s", (intake_id,)
    )
    if not row:
        return f"oc-{kind}-{intake_id}.{ext}"
    svc = oc_engine.CFG["services"].get(row["service_code"], {})
    name = _slug(svc.get("name") or row["service_code"] or "OC")
    stamp = str(row["uploaded_at"] or "").replace("-", "").replace(":", "")
    stamp = stamp.replace(" ", "-")[:13] or str(intake_id)  # YYYYMMDD-HHMM
    return f"{name}-{kind}_{stamp}.{ext}"


async def _download(intake_id: int, ref_col: str, filename: str, content_type: str) -> Response:
    row = await db.fetch_one(f"SELECT {ref_col} AS ref FROM order_intake WHERE id = %s", (intake_id,))
    if not row or not row["ref"]:
        raise HTTPException(status_code=404, detail="not_found")
    found = await store.get(row["ref"])
    if not found:
        raise HTTPException(status_code=404, detail="file_missing")
    data, _ct = found
    return Response(content=data, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.delete("/intakes/{intake_id}", status_code=204)
async def delete_intake(intake_id: int, user: dict = Depends(intake_roles)):
    """Delete an uploaded OC — the intake, its AWBs and their PO lines.

    This exists because existing AWBs are skipped on re-upload, never updated: the only
    way to correct a bad batch is to delete it and upload the fixed file, which re-frees
    every SwipeAWB in it.

    It refuses (409) the moment ANY courier work exists on ANY AWB in the batch — a photo,
    a submit, a reject row, or a status past 'created'. Deleting evidence a driver already
    filed would be destroying the audit trail, so that boundary is absolute; from there on
    the batch is history, not a draft. The generated files' blobs are left in media storage
    (orphaned, harmless) so nothing referenced elsewhere can dangle.
    """
    intake = await db.fetch_one("SELECT id FROM order_intake WHERE id = %s", (intake_id,))
    if not intake:
        raise HTTPException(status_code=404, detail="not_found")

    awbs = await db.fetch_all(
        "SELECT awb_id, status, driver_submitted_at FROM awb WHERE intake_id = %s", (intake_id,)
    )
    for a in awbs:
        if a["driver_submitted_at"] or a["status"] != "created":
            raise HTTPException(status_code=409, detail="intake_has_courier_activity")
        if await db.fetch_one(
            "SELECT 1 AS x FROM document_capture WHERE awb_id = %s", (a["awb_id"],)
        ) or await db.fetch_one(
            "SELECT 1 AS x FROM return_parcel WHERE original_awb_id = %s", (a["awb_id"],)
        ):
            raise HTTPException(status_code=409, detail="intake_has_courier_activity")

    for a in awbs:
        await db.execute("DELETE FROM po_line WHERE awb_id = %s", (a["awb_id"],))
        await db.execute("DELETE FROM awb WHERE awb_id = %s", (a["awb_id"],))
    await db.execute("DELETE FROM order_intake WHERE id = %s", (intake_id,))
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) "
        "VALUES (%s, 'oc_intake_delete', 'order_intake', %s)",
        (user["email"], str(intake_id)),
    )
    return Response(status_code=204)


@router.get("/intakes/{intake_id}/upload.xlsx")
async def download_upload(intake_id: int, _: dict = Depends(intake_roles)):
    name = await _intake_filename(intake_id, "upload", "xlsx")
    return await _download(intake_id, "oc_template_ref", name, XLSX_CT)


@router.get("/intakes/{intake_id}/links.csv")
async def download_links(intake_id: int, _: dict = Depends(intake_roles)):
    name = await _intake_filename(intake_id, "links", "csv")
    return await _download(intake_id, "links_file_ref", name, "text/csv")


# ---- Courier link entry (unauthenticated) ----------------------------------
# The link injected into col R points here. The capture API lives in courier.py under
# the same /api/c/<token> prefix; this route only bounces the courier into the SPA
# wizard, so links already printed on delivery instructions keep working unchanged.


@public_router.get("/api/c/{token}")
async def courier_landing(token: str):
    """Redirect the printed link to the courier wizard route served by the frontend."""
    exists = await db.fetch_one("SELECT 1 AS ok FROM awb WHERE link_token = %s", (token,))
    if not exists:
        raise HTTPException(status_code=404, detail="invalid_link")
    return RedirectResponse(url=f"/c/{token}", status_code=307)

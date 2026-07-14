"""M1 — OC intake & courier links.

Implant/DE uploads a SwipeRx TMP file and picks a service (S1/S2/S3); the engine parses
it, creates AWBs + PO lines with an unguessable per-AWB courier token, and stores the
generated Ninja Van upload .xlsx + links.csv. `/api/c/<token>` resolves a link to its AWB —
this is what makes a generated link open (fixes the prototype's dead link; the full
courier wizard arrives in M2).

Hub is NOT assigned here — NV assigns it after the OC is created; the Implant then
re-uploads AWB→hub separately (BUILD_HANDOFF §3.6).
"""
import html
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

import config
import db
import oc_engine
from security import require_roles
from storage import store

router = APIRouter(prefix="/api/oc", tags=["oc"])
public_router = APIRouter(tags=["courier"])  # unauthenticated courier link entry
intake_roles = require_roles("implant", "de")

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
    return {"services": oc_engine.services()}


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
                 user: dict = Depends(intake_roles)):
    """Commit the batch: persist AWBs + tokens and generate the NV upload .xlsx + links.csv."""
    data, result = await _parse_upload(service, file)
    awbs = result["awbs"]
    if not awbs:
        raise HTTPException(status_code=422, detail="no_valid_awbs")

    src_ref = await store.put(data, XLSX_CT)
    intake_id = await db.execute(
        "INSERT INTO order_intake (source_file_ref, service_code, uploaded_by, status) "
        "VALUES (%s, %s, %s, 'processing')",
        (src_ref, service, user["id"]),
    )

    committed, errors = [], list(result["errors"])
    for a in awbs:
        if await db.fetch_one("SELECT awb_id FROM awb WHERE awb_id = %s", (a["awb_id"],)):
            errors.append({"row": None, "awb": a["awb_id"], "error": "AWB already exists — skipped"})
            continue
        token = secrets.token_urlsafe(24)
        a["token"] = token
        # /api/* is the only path the ingress routes to the backend, so the courier link
        # lives under /api to guarantee it resolves (the M2 SPA can later own a /c/ route).
        a["url"] = f"{config.PUBLIC_BASE_URL}/api/c/{token}"
        a["delivery_instructions"] = oc_engine.delivery_instructions(service, a, a["url"])
        await db.execute(
            "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, city, "
            "postcode, phone, weight, koli, link_token, status, return_type, is_return, invoice, "
            "item_detail, delivery_instructions, created_by, intake_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'created','none',%s,%s,%s,%s,%s,%s)",
            (a["awb_id"], a["merchant_order_number"], service, a["pharmacy_name"], a["address"], a["city"],
             a["postcode"], a["phone"], a["weight"], a["collies"], token, 1 if a["is_return"] else 0,
             a["invoice"], a["item_detail"], a["delivery_instructions"], user["id"], intake_id),
        )
        for p in a["po_lines"]:
            await db.execute(
                "INSERT INTO po_line (awb_id, po_number, koli) VALUES (%s, %s, %s)",
                (a["awb_id"], p["po_number"], p["koli"]),
            )
        committed.append(a)

    upload_ref = await store.put(oc_engine.build_upload_xlsx(service, committed), XLSX_CT)
    links_ref = await store.put(oc_engine.build_links_csv(committed), "text/csv")
    piece_count = sum(len(oc_engine.piece_trids(a)) for a in committed)
    err_text = "; ".join(_err_line(e) for e in errors) or None
    await db.execute(
        "UPDATE order_intake SET oc_template_ref=%s, links_file_ref=%s, awb_count=%s, piece_count=%s, "
        "row_count=%s, status='created', error_summary=%s WHERE id=%s",
        (upload_ref, links_ref, len(committed), piece_count, len(committed), err_text, intake_id),
    )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'oc_create', 'order_intake', %s)",
        (user["email"], str(intake_id)),
    )
    return {
        "intake_id": intake_id, "service": service,
        "awb_count": len(committed), "piece_count": piece_count,
        "error_count": len(errors), "errors": errors,
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
        a["courier_url"] = f"{config.PUBLIC_BASE_URL}/api/c/{a.pop('link_token')}"
    return {"intake": intake, "awbs": awbs}


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


@router.get("/intakes/{intake_id}/upload.xlsx")
async def download_upload(intake_id: int, _: dict = Depends(intake_roles)):
    return await _download(intake_id, "oc_template_ref", f"oc-upload-{intake_id}.xlsx", XLSX_CT)


@router.get("/intakes/{intake_id}/links.csv")
async def download_links(intake_id: int, _: dict = Depends(intake_roles)):
    return await _download(intake_id, "links_file_ref", f"oc-links-{intake_id}.csv", "text/csv")


# ---- Courier link entry (unauthenticated) ----------------------------------
async def _resolve_token(token: str) -> dict:
    awb = await db.fetch_one(
        "SELECT awb_id, merchant_order_number, pharmacy_name, address, city, service_id, status, "
        "is_return, invoice, item_detail FROM awb WHERE link_token = %s", (token,)
    )
    if not awb:
        raise HTTPException(status_code=404, detail="invalid_link")
    awb["is_return"] = bool(awb["is_return"])
    awb["po_lines"] = await db.fetch_all(
        "SELECT po_number, koli FROM po_line WHERE awb_id = %s ORDER BY id", (awb["awb_id"],)
    )
    return awb


@public_router.get("/api/c/{token}/order")
async def courier_resolve(token: str):
    """JSON the courier app (M2) will render. Public — the token is the only credential."""
    return await _resolve_token(token)


@public_router.get("/api/c/{token}", response_class=HTMLResponse)
async def courier_landing(token: str):
    """The injected courier link target. Minimal standalone page so a link opens today;
    the M2 wizard (a frontend /c/ route calling /api/c/<token>/order) replaces this."""
    awb = await _resolve_token(token)
    e = html.escape
    pos = "".join(f"<li>{e(p['po_number'])} — {p['koli']} koli</li>" for p in awb["po_lines"])
    extra = (f"<p><b>Invoice:</b> {e(awb['invoice'] or '-')}</p>"
             f"<p><b>Detail:</b> {e(awb['item_detail'] or '-')}</p>") if awb["is_return"] else ""
    kind = "Pickup Return" if awb["is_return"] else "Delivery"
    page = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SwipeRx Operator — {e(awb['awb_id'])}</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f5f5f5;color:#222}}
.card{{max-width:520px;margin:16px auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
.tag{{display:inline-block;background:#EE1B2C;color:#fff;padding:2px 10px;border-radius:999px;font-size:12px}}
h1{{font-size:18px;margin:.4em 0}}ul{{padding-left:20px}}small{{color:#777}}</style></head>
<body><div class="card"><span class="tag">{e(kind)}</span>
<h1>{e(awb['pharmacy_name'])}</h1>
<p>{e(awb['address'] or '')}<br><small>{e(awb['city'] or '')}</small></p>
<p><b>AWB:</b> {e(awb['awb_id'])} &nbsp; <b>Status:</b> {e(awb['status'])}</p>
<p><b>PO / koli:</b></p><ul>{pos}</ul>{extra}
<p><small>Aplikasi kurir lengkap menyusul (M2). Link ini valid — pesanan ditemukan.</small></p>
</div></body></html>"""
    return HTMLResponse(content=page)

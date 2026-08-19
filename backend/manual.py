"""Manual link builder — phase-1 field testing.

Purpose: create ONE courier link from typed-in fields, without a TMP file, so a real
delivery can be trialled end to end before the OC intake path is trusted. The operator
pastes the generated link (or the whole col-R string) into the order's delivery
instructions by hand in Ninja's system, sends a driver, and sees what breaks.

It is deliberately a separate module from `oc.py`:
  - it is a TEST instrument, not a production path, and should be easy to delete after
    phase 1 without unpicking the intake code;
  - it lets the operator type values the TMP parser would never produce — a different
    parent TRID shape, a blank AC — which is the only way to settle the two questions
    still open in OC_AWB_PARENT_CHECK §8 (what column A accepts, and whether NV really
    auto-creates children when AC is blank).

Everything it writes lands in the same `awb`/`po_line` tables as a real intake, so the
generated link resolves through the ordinary /c/<token> courier wizard — the point is to
test the real path, not a mock of it.
"""
import secrets
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

import config
import db
import oc_engine
from security import require_roles

router = APIRouter(prefix="/api/manual", tags=["manual"])

# Superadmin is the owner of this tool; implant/DE are included so a test can be handed
# to the person who actually runs intake without granting them user administration.
tester_roles = require_roles("superadmin", "implant", "de")

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _awb_from_fields(
    service: str,
    awb_id: str,
    pharmacy_name: str,
    address: str,
    city: str,
    postcode: str,
    phone: str,
    weight: str,
    po_lines: list[dict],
    collies: int | None,
    is_return: bool,
    invoice: str,
    item_detail: str,
    children_mode: str,
) -> dict:
    """Assemble the same AWB dict shape `oc_engine.parse()` produces, from typed fields."""
    clean: list[dict] = []
    for p in po_lines or []:
        po = str(p.get("po_number", "")).strip()
        if not po:
            continue
        try:
            koli = int(p.get("koli") or 1)
        except (TypeError, ValueError):
            koli = 1
        clean.append({"po_number": po, "koli": max(1, koli)})

    # Collies drives AB and therefore the child count. Explicit wins so a tester can
    # deliberately mismatch it against the PO lines and watch what NV does.
    total = collies if collies is not None else (sum(p["koli"] for p in clean) or 1)
    if total < 1:
        raise HTTPException(status_code=400, detail="collies_must_be_positive")
    if total > oc_engine.CFG["max_collies_per_awb"]:
        raise HTTPException(status_code=400, detail="collies_above_cap")

    return {
        "awb_id": awb_id,
        "merchant_order_number": awb_id,
        "pharmacy_name": pharmacy_name,
        "phone": phone,
        "address": address,
        "city": city,
        "postcode": postcode,
        "weight": weight or "1",
        "po_lines": clean or [{"po_number": awb_id, "koli": total}],
        "collies": total,
        "is_return": is_return,
        "invoice": invoice,
        "item_detail": item_detail,
        "children_mode": children_mode,
    }


@router.post("/links", status_code=201)
async def create_manual_link(
    service: str = Body(...),
    awb_id: str = Body(...),
    pharmacy_name: str = Body(default="Uji Coba"),
    address: str = Body(default=""),
    city: str = Body(default=""),
    postcode: str = Body(default=""),
    phone: str = Body(default=""),
    weight: str = Body(default="1"),
    po_lines: list[dict] = Body(default=[]),
    collies: int | None = Body(default=None),
    is_return: bool = Body(default=False),
    invoice: str = Body(default=""),
    item_detail: str = Body(default=""),
    children_mode: str = Body(default="auto"),
    delivery_date: str | None = Body(default=None),
    user: dict = Depends(tester_roles),
):
    """Mint one courier link from typed fields and return everything needed to paste it.

    Returns the ready-made col-R string as well as the bare URL: pasting col R verbatim is
    what reproduces production most faithfully, because the 500-char budget and the RDO
    wording are part of what is being tested.
    """
    awb_id = awb_id.strip()
    if not awb_id:
        raise HTTPException(status_code=400, detail="awb_id_required")
    if len(awb_id) > 32:  # awb.awb_id is VARCHAR(32)
        raise HTTPException(status_code=400, detail="awb_id_too_long")
    if service not in {s["code"] for s in oc_engine.services()}:
        raise HTTPException(status_code=400, detail="unknown_service")
    if children_mode not in ("auto", "blank"):
        raise HTTPException(status_code=400, detail="bad_children_mode")
    if await db.fetch_one("SELECT awb_id FROM awb WHERE awb_id = %s", (awb_id,)):
        raise HTTPException(status_code=409, detail="awb_already_exists")

    day = delivery_date or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad_delivery_date") from None

    awb = _awb_from_fields(
        service, awb_id, pharmacy_name, address, city, postcode, phone, weight,
        po_lines, collies, is_return, invoice, item_detail, children_mode,
    )

    token = secrets.token_urlsafe(24)
    awb["token"] = token
    awb["url"] = f"{config.COURIER_BASE_URL}/c/{token}"
    awb["delivery_instructions"] = oc_engine.delivery_instructions(service, awb, awb["url"])

    await db.execute(
        "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, city, "
        "postcode, phone, weight, koli, link_token, status, return_type, is_return, invoice, "
        "item_detail, delivery_instructions, created_by, intake_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'created','none',%s,%s,%s,%s,%s,NULL)",
        (awb["awb_id"], awb["merchant_order_number"], service, awb["pharmacy_name"], awb["address"],
         awb["city"], awb["postcode"], awb["phone"], awb["weight"], awb["collies"], token,
         1 if is_return else 0, awb["invoice"], awb["item_detail"], awb["delivery_instructions"],
         user["id"]),
    )
    for p in awb["po_lines"]:
        await db.execute(
            "INSERT INTO po_line (awb_id, po_number, koli) VALUES (%s, %s, %s)",
            (awb["awb_id"], p["po_number"], p["koli"]),
        )
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'manual_link', 'awb', %s)",
        (user["email"], awb["awb_id"]),
    )

    children = [] if children_mode == "blank" else oc_engine.piece_trids(awb)
    instr = awb["delivery_instructions"]
    return {
        "awb_id": awb["awb_id"],
        "token": token,
        "url": awb["url"],
        "delivery_instructions": instr,
        "instr_length": len(instr),
        "instr_limit": oc_engine.CFG["link_char_limit"],
        "instr_truncated": oc_engine.instr_truncated(instr),
        # Exactly what to type into the Ninja upload, named by column so it can be
        # transcribed without cross-referencing the header row.
        "upload_columns": {
            "A_requested_tracking_number": awb["awb_id"],
            "D_merchant_order_number": awb["merchant_order_number"],
            "R_delivery_instructions": instr,
            "W_weight": awb["weight"],
            "AB_total_quantity": str(awb["collies"]),
            "AC_piece_tracking_numbers": ", ".join(children),
        },
        "children": children,
        "children_mode": children_mode,
        "download_url": f"/api/manual/links/{awb['awb_id']}/upload.xlsx",
    }


@router.get("/links")
async def list_manual_links(_: dict = Depends(tester_roles)):
    """Manual test AWBs only — those created outside any intake (intake_id IS NULL)."""
    rows = await db.fetch_all(
        "SELECT awb_id, pharmacy_name, city, koli, status, is_return, link_token, service_id, "
        "created_at FROM awb WHERE intake_id IS NULL ORDER BY created_at DESC, awb_id DESC LIMIT 200"
    )
    for r in rows:
        r["is_return"] = bool(r["is_return"])
        r["created_at"] = str(r["created_at"])
        r["courier_url"] = f"{config.COURIER_BASE_URL}/c/{r.pop('link_token')}"
    return {"links": rows, "count": len(rows)}


@router.get("/links/{awb_id}/upload.xlsx")
async def download_manual_row(awb_id: str, _: dict = Depends(tester_roles)):
    """A one-row Ninja upload workbook for this AWB — for uploading rather than typing."""
    row = await db.fetch_one(
        "SELECT awb_id, merchant_order_number, service_id, pharmacy_name, address, city, postcode, "
        "phone, weight, koli, is_return, invoice, item_detail, delivery_instructions "
        "FROM awb WHERE awb_id = %s AND intake_id IS NULL", (awb_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    pos = await db.fetch_all("SELECT po_number, koli FROM po_line WHERE awb_id = %s", (awb_id,))
    awb = {
        "awb_id": row["awb_id"], "merchant_order_number": row["merchant_order_number"],
        "pharmacy_name": row["pharmacy_name"], "address": row["address"], "city": row["city"],
        "postcode": row["postcode"], "phone": row["phone"], "weight": row["weight"],
        "collies": row["koli"], "is_return": bool(row["is_return"]),
        "invoice": row["invoice"], "item_detail": row["item_detail"],
        "delivery_instructions": row["delivery_instructions"],
        "po_lines": [{"po_number": p["po_number"], "koli": p["koli"]} for p in pos]
                    or [{"po_number": row["awb_id"], "koli": row["koli"]}],
    }
    data = oc_engine.build_upload_xlsx(row["service_id"], [awb])
    return Response(content=data, media_type=XLSX_CT,
                    headers={"Content-Disposition": f'attachment; filename="manual-{awb_id}.xlsx"'})


@router.delete("/links/{awb_id}", status_code=204)
async def delete_manual_link(awb_id: str, user: dict = Depends(tester_roles)):
    """Remove a test AWB so the same identifier can be retried.

    Scoped to `intake_id IS NULL` so this can never delete an AWB that came from a real
    TMP intake, whatever id is passed.
    """
    row = await db.fetch_one(
        "SELECT awb_id FROM awb WHERE awb_id = %s AND intake_id IS NULL", (awb_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    await db.execute("DELETE FROM po_line WHERE awb_id = %s", (awb_id,))
    await db.execute("DELETE FROM awb WHERE awb_id = %s AND intake_id IS NULL", (awb_id,))
    await db.execute(
        "INSERT INTO audit_log (actor, action, entity, entity_id) VALUES (%s, 'manual_link_delete', 'awb', %s)",
        (user["email"], awb_id),
    )
    return Response(status_code=204)

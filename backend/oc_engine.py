"""OC intake engine (Python port of the validated Node harness in ../oc-engine).

Pure transform, no DB/HTTP: parse a SwipeRx TMP .xlsx for a chosen service (S1/S2/S3),
group into AWBs + PO lines, MPS-expand per AWB, and emit the Ninja Van upload columns
(with the courier link injected into delivery_instructions). Rules + provenance:
../oc-engine/EXTRACTION_NOTES.md and ../OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md.

Tokens are assigned by the caller (oc.py) so they persist in the DB and back the /c/<token>
route — this module only builds the link string once a URL is known.
"""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import date

import openpyxl

_CFG_PATH = os.path.join(os.path.dirname(__file__), "oc_config.json")
with open(_CFG_PATH, encoding="utf-8") as _f:
    CFG = json.load(_f)

# NV upload column order (field names = the real template's header row).
FWD_COLS = [
    "requested_tracking_number", "global_shipper_id", "service_type", "reference.merchant_order_number",
    "service_level", "from.name", "from.phone_number", "from.address.address1", "from.address.country",
    "to.name", "to.phone_number", "to.address.address1", "to.address.country", "to.address.kecamatan",
    "to.address.city", "to.address.province", "to.address.postcode", "parcel_job.delivery_instructions",
    "parcel_job.delivery_start_date", "parcel_job.delivery_timeslot.start_time",
    "parcel_job.delivery_timeslot.end_time", "parcel_job.delivery_timeslot.timezone",
    "parcel_job.dimensions.weight", "parcel_job.is_pickup_required", "parcel_job.items.0.item_description",
    "parcel_job.items.0.is_dangerous_good", "b2b.documents_required", "bundle_information.total_quantity",
    "bundle_information.requested_piece_tracking_numbers", "parcel_job.insured_value", "corporate.branch_id",
]
RET_EXTRA_COLS = [
    "parcel_job.pickup_date", "parcel_job.pickup_timeslot.start_time", "parcel_job.pickup_timeslot.end_time",
    "parcel_job.pickup_timeslot.timezone", "parcel_job.pickup_instructions",
]


class OcError(ValueError):
    """Raised for problems that make the whole file unusable (bad service, unreadable xlsx)."""


def services() -> list[dict]:
    """Public service list for the intake UI (code, name, movement, service level)."""
    out = []
    for code, s in CFG["services"].items():
        out.append({"code": code, "name": s["name"], "movement": s["movement"],
                    "service_level": s["service_level"], "direction": s["direction"]})
    return out


def _norm(v) -> str:
    """Normalize an openpyxl cell value to a clean string (ints without .0, no sci-notation)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, int):
        return str(v)
    return str(v).strip()


def _fit_instr(free_text: str, suffix: str, url: str, limit: int) -> str:
    """Wrap fixed/free text + link in <updated_addr>…<a href=URL>URL</a>, trimming free text to fit.
    No separator is inserted between text and the anchor — rdo_text entries carry their own
    trailing punctuation/spacing (e.g. "...berikut:" attaches directly, "...Return. " has a
    trailing space)."""
    def build(t: str) -> str:
        head = "".join([x for x in (t, suffix) if x])
        return f'<updated_addr>{head}<a href="{url}">{url}</a></updated_addr>'

    if len(build(free_text)) <= limit:
        return build(free_text)
    t = free_text
    while t and len(build(t[:-1] + "…")) > limit:
        t = t[:-1]
    return build(t[:-1] + "…" if t else "")


def _load_ws(file_bytes: bytes):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:  # noqa: BLE001 — surface any xlsx failure as a clean error
        raise OcError(f"could not read .xlsx: {exc}") from exc
    return wb.worksheets[0]


def _get(ws, col: str, row: int) -> str:
    return _norm(ws[f"{col}{row}"].value)


def parse(file_bytes: bytes, service_code: str) -> dict:
    """Parse a TMP file into AWB entities (no tokens/links yet).

    Returns {service, direction, awbs:[...], errors:[...], warnings:[...]}.
    Each AWB dict carries the normalized fields + po_lines + total collies; the caller
    assigns a token/url and then calls build_outputs().
    """
    svc = CFG["services"].get(service_code)
    if not svc:
        raise OcError(f"unknown service {service_code!r} (expected S1|S2|S3)")
    layout = CFG["source_layouts"][svc["layout"]]
    ws = _load_ws(file_bytes)
    errors: list[dict] = []
    warnings: list[dict] = []
    awbs = _parse_return(ws, layout, errors) if svc["direction"] == "return" \
        else _parse_forward(ws, layout, errors)
    return {"service": service_code, "direction": svc["direction"],
            "awbs": awbs, "errors": errors, "warnings": warnings}


def _parse_forward(ws, layout, errors) -> list[dict]:
    c = layout["cols"]
    cap = CFG["max_collies_per_awb"]
    order: list[str] = []
    groups: dict[str, dict] = {}
    current = None
    for r in range(layout["data_start_row"], ws.max_row + 1):
        key = _get(ws, c["swipe_awb"], r)
        po = _get(ws, c["po"], r)
        koli_raw = _get(ws, c["koli"], r)
        if not (key or po or _get(ws, c["name"], r) or koli_raw):
            continue
        if key:
            current = key
            if key not in groups:
                groups[key] = {
                    "awb_id": key, "merchant_order_number": key,
                    "pharmacy_name": _get(ws, c["name"], r), "phone": _get(ws, c["phone"], r),
                    "address": _get(ws, c["address"], r), "city": _get(ws, c["city"], r),
                    "postcode": _get(ws, c["zip"], r), "weight": _get(ws, c["weight"], r),
                    "po_lines": [], "collies": 0, "is_return": False,
                    "invoice": "", "item_detail": "",
                }
                order.append(key)
        if current is None:
            errors.append({"row": r, "awb": "", "error": "orphan row before any SwipeAWB"})
            continue
        try:
            koli = int(float(koli_raw))
        except ValueError:
            koli = 0
        if not po:
            errors.append({"row": r, "awb": current, "error": "missing PO Number"})
            continue
        if koli <= 0:
            errors.append({"row": r, "awb": current, "error": f'koli must be > 0 (got "{koli_raw}")'})
            continue
        g = groups[current]
        g["po_lines"].append({"po_number": po, "koli": koli})
        g["collies"] += koli

    out = []
    for key in order:
        g = groups[key]
        total = g["collies"]
        if total <= 0:
            errors.append({"row": None, "awb": key, "error": "no valid collies"})
            continue
        if total > cap:
            errors.append({"row": None, "awb": key,
                           "error": f"collie count {total} exceeds cap {cap} — likely a layout mismatch; skipped"})
            continue
        g["collies"] = total
        out.append(g)
    return out


def _parse_return(ws, layout, errors) -> list[dict]:
    c = layout["cols"]
    out = []
    for r in range(layout["data_start_row"], ws.max_row + 1):
        return_awb = _get(ws, c["return_awb"], r)
        po = _get(ws, c["po"], r)
        if not return_awb and not po:
            continue
        row_err = []
        if not return_awb:
            row_err.append("missing return AWB")
        if not _get(ws, c["address"], r):
            row_err.append("missing pharmacy address")
        if row_err:
            errors.append({"row": r, "awb": return_awb, "error": "; ".join(row_err)})
            continue
        detail = " ".join(_get(ws, c["detail"], r).split())
        out.append({
            "awb_id": return_awb, "merchant_order_number": po,
            "pharmacy_name": _get(ws, c["pharmacy_name"], r), "phone": _get(ws, c["phone"], r),
            "address": _get(ws, c["address"], r), "city": _get(ws, c["city"], r),
            "postcode": "", "weight": "1",
            "po_lines": [{"po_number": po, "koli": 1}], "collies": 1, "is_return": True,
            "invoice": _get(ws, c["inv"], r), "item_detail": detail,
        })
    return out


def piece_trids(awb: dict) -> list[str]:
    """MPS pieces for an AWB: base = awb_id, children -1..-N (N = Σ collies); returns get -01."""
    base = awb["awb_id"]
    if awb["is_return"]:
        return [f"{base}-01"]
    total = awb["collies"]
    return [base] if total == 1 else [f"{base}-{i}" for i in range(1, total + 1)]


def delivery_instructions(service_code: str, awb: dict, url: str) -> str:
    """Build the col-R delivery_instructions (fixed text + injected courier link, ≤500 chars)."""
    svc = CFG["services"][service_code]
    limit = CFG["link_char_limit"]
    if svc["direction"] == "return":
        return _fit_instr(CFG["rdo_text"]["return_delivery_short"], "", url, limit)
    return _fit_instr(CFG["rdo_text"]["forward"], "", url, limit)


def _item_description(awb: dict) -> str:
    if awb["is_return"]:
        return CFG["fixed"]["item_description_return"]
    total = awb["collies"]
    parts = ", ".join(f'{p["po_number"]} ({p["koli"]})' for p in awb["po_lines"])
    return f"{parts} — {total} koli"


def _upload_row(service_code: str, awb: dict, trid: str, trids: list[str], today: str) -> dict:
    """One NV upload row (dict keyed by field name) for a single MPS piece."""
    svc = CFG["services"][service_code]
    wh = CFG["warehouse"]
    fx = CFG["fixed"]
    ts = fx["timeslot"]
    row = {
        "requested_tracking_number": trid,
        "global_shipper_id": CFG["master_shipper_id"],
        "service_type": fx["service_type"],
        "reference.merchant_order_number": awb["merchant_order_number"],
        "service_level": svc["service_level"],
        "to.address.country": "ID",
        "to.address.kecamatan": "",
        "to.address.province": "",
        "parcel_job.delivery_instructions": awb["delivery_instructions"],
        "parcel_job.delivery_start_date": today,
        "parcel_job.delivery_timeslot.start_time": ts["start_time"],
        "parcel_job.delivery_timeslot.end_time": ts["end_time"],
        "parcel_job.delivery_timeslot.timezone": ts["timezone"],
        "parcel_job.items.0.item_description": _item_description(awb),
        "parcel_job.items.0.is_dangerous_good": fx["is_dangerous_good"],
        "b2b.documents_required": fx["documents_required"],
        "bundle_information.total_quantity": str(awb["collies"]),
        "bundle_information.requested_piece_tracking_numbers": ", ".join(trids),
        "parcel_job.insured_value": fx["insured_value"],
        "corporate.branch_id": svc["branch_id"],
    }
    if awb["is_return"]:
        # Reverse job: from = pharmacy, to = SwipeRx WH.
        row.update({
            "from.name": awb["pharmacy_name"], "from.phone_number": awb["phone"],
            "from.address.address1": awb["address"], "from.address.country": "ID",
            "to.name": wh["name"], "to.phone_number": wh["phone"], "to.address.address1": wh["address1"],
            "to.address.kecamatan": wh["kecamatan"], "to.address.city": wh["city"],
            "to.address.province": wh["province"], "to.address.postcode": wh["postcode"],
            "parcel_job.dimensions.weight": "1", "parcel_job.is_pickup_required": fx["is_pickup_required_return"],
            "parcel_job.pickup_date": today, "parcel_job.pickup_timeslot.start_time": ts["start_time"],
            "parcel_job.pickup_timeslot.end_time": ts["end_time"], "parcel_job.pickup_timeslot.timezone": ts["timezone"],
            "parcel_job.pickup_instructions": CFG["rdo_text"]["return_pickup_instructions"],
        })
    else:
        # Forward: from = SwipeRx WH, to = pharmacy.
        row.update({
            "from.name": wh["name"], "from.phone_number": wh["phone"], "from.address.address1": wh["address1"],
            "from.address.country": wh["country"],
            "to.name": awb["pharmacy_name"], "to.phone_number": awb["phone"], "to.address.address1": awb["address"],
            "to.address.city": awb["city"], "to.address.postcode": awb["postcode"],
            "parcel_job.dimensions.weight": awb["weight"] or "1",
            "parcel_job.is_pickup_required": fx["is_pickup_required_forward"],
        })
    return row


def build_upload_xlsx(service_code: str, awbs: list[dict], today: str | None = None) -> bytes:
    """Build the Ninja Van upload workbook. Each AWB must already have delivery_instructions set."""
    today = today or date.today().isoformat()
    is_return = CFG["services"][service_code]["direction"] == "return"
    cols = FWD_COLS + RET_EXTRA_COLS if is_return else FWD_COLS
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Upload"
    ws.append(cols)
    for awb in awbs:
        trids = piece_trids(awb)
        for trid in trids:
            row = _upload_row(service_code, awb, trid, trids, today)
            ws.append([str(row.get(col, "")) for col in cols])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def build_links_csv(awbs: list[dict]) -> bytes:
    """AWB → courier link, plus the return item detail/invoice the courier app shows behind the link."""
    bio = io.StringIO()
    w = csv.writer(bio)
    w.writerow(["scope", "token", "url", "invoice", "item_detail"])
    for a in awbs:
        w.writerow([a["awb_id"], a.get("token", ""), a.get("url", ""), a.get("invoice", ""), a.get("item_detail", "")])
    return ("﻿" + bio.getvalue()).encode("utf-8")

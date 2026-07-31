"""OC engine — the MPS model from OC_TEMPLATE_AND_ENGINE_GUIDE.md §2.3 (rev. 27 Jul 2026).

These pin the rules that broke the DE team's spreadsheet converter, so a future change to
the tracking-number scheme has to break a test rather than a live upload.
"""
import io

import openpyxl
import pytest

import oc_engine as e


def _awb(**kw):
    base = {
        "awb_id": "AWB02U24V", "merchant_order_number": "AWB02U24V", "is_return": False,
        "pharmacy_name": "Apotek Uji", "address": "Jl. Uji 1", "city": "Depok",
        "postcode": "16451", "phone": "0812", "weight": "4.5", "collies": 4,
        "invoice": None, "item_detail": None, "delivery_instructions": "x",
        "po_lines": [{"po_number": "PO1", "koli": 2}, {"po_number": "PO2", "koli": 1},
                     {"po_number": "PO3", "koli": 1}],
    }
    base.update(kw)
    return base


def test_children_are_po_prefixed_and_numbered_continuously():
    """The guide's worked example, verbatim: numbering runs across the AWB, not per PO."""
    assert e.piece_trids(_awb()) == ["PO1-01", "PO1-02", "PO2-03", "PO3-04"]


def test_children_are_zero_padded_past_nine():
    awb = _awb(collies=12, po_lines=[{"po_number": "POA", "koli": 12}])
    trids = e.piece_trids(awb)
    assert trids[0] == "POA-01"
    assert trids[8] == "POA-09"
    assert trids[9] == "POA-10"  # zero-padded to 2, never "-9"/"-10" mixed widths
    assert len(trids) == 12


def test_single_koli_awb_still_gets_a_numbered_child():
    awb = _awb(collies=1, po_lines=[{"po_number": "POX", "koli": 1}])
    assert e.piece_trids(awb) == ["POX-01"]


def test_return_awb_gets_one_piece_off_the_presupplied_awb():
    awb = _awb(awb_id="AWBR-10909-2026-5-16", is_return=True, collies=1,
               po_lines=[{"po_number": "POR", "koli": 1}])
    assert e.piece_trids(awb) == ["AWBR-10909-2026-5-16-01"]


def _rows(service, awbs):
    wb = openpyxl.load_workbook(io.BytesIO(e.build_upload_xlsx(service, awbs, "2026-08-01")))
    ws = wb.worksheets[0]
    header = [c.value for c in ws[1]]
    return header, [dict(zip(header, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]


def test_upload_emits_exactly_one_row_per_awb():
    """1 WP = 1 MPS TRID = 1 SwipeAWB. The pre-27-Jul build emitted a row per collie,
    which would create N separate orders each claiming to be a bundle of N."""
    _, rows = _rows("S1", [_awb(), _awb(awb_id="AWB02U51N", merchant_order_number="AWB02U51N",
                                 collies=1, po_lines=[{"po_number": "POZ", "koli": 1}])])
    assert len(rows) == 2


def test_tracking_number_equals_the_swipe_awb_and_matches_merchant_order_number():
    _, rows = _rows("S1", [_awb()])
    r = rows[0]
    assert r["requested_tracking_number"] == "AWB02U24V"
    assert r["reference.merchant_order_number"] == "AWB02U24V"


def test_bundle_quantity_and_pieces_agree():
    _, rows = _rows("S1", [_awb()])
    r = rows[0]
    assert r["bundle_information.total_quantity"] == "4"
    pieces = r["bundle_information.requested_piece_tracking_numbers"].split(", ")
    assert pieces == ["PO1-01", "PO1-02", "PO2-03", "PO3-04"]
    assert len(pieces) == int(r["bundle_information.total_quantity"])


def test_weight_is_the_awb_total_not_a_hardcoded_one():
    """The sample templates hardcode W=1; the guide says read the real AWB weight."""
    _, rows = _rows("S1", [_awb(weight="16.1")])
    assert rows[0]["parcel_job.dimensions.weight"] == "16.1"


def test_item_description_carries_the_po_cross_check():
    _, rows = _rows("S1", [_awb()])
    assert rows[0]["parcel_job.items.0.item_description"] == "PO1 (2), PO2 (1), PO3 (1) — 4 koli"


@pytest.mark.parametrize(
    ("service", "level", "branch"), [("S1", "STANDARD", "1"), ("S2", "SAMEDAY", "3")]
)
def test_s1_and_s2_differ_only_by_service_level_and_branch(service, level, branch):
    _, rows = _rows(service, [_awb()])
    r = rows[0]
    assert r["service_level"] == level
    assert r["corporate.branch_id"] == branch
    # Col B is ALWAYS the master; the service is selected by the branch id, never here.
    assert r["global_shipper_id"] == "11398423"


def test_s1_is_named_regular_b2br():
    s1 = next(s for s in e.services() if s["code"] == "S1")
    assert s1["name"] == "Regular B2BR"


PROD_URL = "https://swiperx-operator.ninjavan.apps.substrait.build/c/" + "x" * 32


def test_forward_rdo_text_fits_the_500_char_column_without_truncation():
    """Col R is compliance text with a hard cap. Against the real production host the
    mandated wording must survive intact — if this fails, shorten the CTA, never the
    mandated wording."""
    out = e.delivery_instructions("S1", _awb(), PROD_URL)
    assert len(out) <= e.CFG["link_char_limit"]
    assert not e.instr_truncated(out), "mandated RDO wording was trimmed"
    assert e.CFG["rdo_text"]["forward"] in out, "mandated wording missing or altered"
    assert out.startswith("<updated_addr>") and out.endswith("</updated_addr>")
    assert f'<a href="{PROD_URL}">{PROD_URL}</a>' in out  # anchor text == the URL itself


def test_cta_is_dropped_whole_rather_than_trimming_mandated_wording():
    """A host long enough to squeeze the budget must cost the CTA, not the compliance
    text — the failure mode the 27 Jul hostname migration exposed.

    The URL is sized to land in the window where the mandated wording still fits but the
    CTA no longer does, derived from config rather than hardcoded so it tracks any future
    wording change."""
    limit = e.CFG["link_char_limit"]
    mandated, cta = e.CFG["rdo_text"]["forward"], e.CFG["rdo_text"]["forward_cta"]
    tags = len('<updated_addr></updated_addr>') + len('<a href=""></a>')
    # budget(L) = limit - 2L - tags, so the longest URL that still fits the mandated text
    # is L = (limit - tags - len(mandated)) // 2 — the top of the drop-the-CTA window.
    url_len = (limit - tags - len(mandated)) // 2
    url = "https://" + "h" * (url_len - len("https:///c/") - 32) + "/c/" + "x" * 32
    assert len(url) == url_len

    out = e.delivery_instructions("S1", _awb(), url)
    assert len(out) <= limit
    assert mandated in out, "mandated wording was trimmed instead of the CTA"
    assert cta not in out, "CTA should have been dropped whole"
    assert not e.instr_truncated(out)

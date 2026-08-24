"""Lane 1 — OC intake. Runs against the real SwipeRx TMP samples in ../../OC Template.

The engine's tracking-number scheme is deliberately NOT asserted here: it is the open
question in OC_AWB_PARENT_CHECK.md §3 and changes once the tech team confirms the
column-A format. These tests pin the intake CONTRACT (auth, validation, persistence,
generated files, courier links) so that change lands against a green suite.
"""
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "OC Template"
# The LOCKED TMP structure (1 header row, data from row 2, koli in col M). The older
# 10-06-26 sample is a different, pre-lock layout and no longer parses - see
# source_layouts._forward_layout_comment in oc_config.json.
REG_TMP = TEMPLATES / "[Template Swipe Fwd LOCKED] TMP Batch Ninja Depok (Order) 28-07-26.xlsx"

pytestmark = pytest.mark.skipif(not REG_TMP.exists(), reason="OC Template samples not present")


def tmp_upload():
    return {"file": (REG_TMP.name, REG_TMP.read_bytes(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def test_intake_requires_a_session(client):
    assert client.get("/api/oc/services").status_code == 401


def test_intake_requires_an_intake_role(client):
    client.post("/api/auth/dev-login", json={"email": "agus.s@ninjavan.co"})  # station_ic only
    assert client.get("/api/oc/services").status_code == 403


def test_services_expose_the_read_only_shipper_identity(de_client):
    """FR-OC1: picking a service must show shipper id + name + corporate branch.
    S3 (Return Pickup) is DISABLED (27 Jul) and must not be offered."""
    services = de_client.get("/api/oc/services").json()["services"]
    assert {s["code"] for s in services} == {"S1", "S2"}
    s1 = next(s for s in services if s["code"] == "S1")
    assert s1["name"] == "Regular B2BR"
    assert s1["shipper_id"] == "11398224"
    assert s1["branch_id"] == "1"
    # Col B is always the master, whichever service is chosen.
    assert all(s["master_shipper_id"] == "11398423" for s in services)


def test_preview_parses_without_writing(de_client):
    r = de_client.post("/api/oc/preview", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["awb_count"] > 0
    assert body["awbs"][0]["awb_id"].startswith("AWB")
    # Preview must not commit anything.
    assert de_client.get("/api/oc/intakes").json()["intakes"] == []


def test_unknown_service_and_empty_file_are_rejected(de_client):
    bad_service = de_client.post("/api/oc/preview", data={"service": "S9", "origin": "TMP_DEPOK"}, files=tmp_upload())
    assert bad_service.status_code == 400

    empty = de_client.post(
        "/api/oc/preview", data={"service": "S1", "origin": "TMP_DEPOK"},
        files={"file": ("empty.xlsx", b"", "application/octet-stream")},
    )
    assert empty.status_code == 400


def test_disabled_s3_is_rejected_outright(de_client):
    """S3 was the one layout where a wrong-service upload produced garbage AWBs with zero
    validation errors (the silent-commit gap found 26 Jul). Disabling S3 (27 Jul) closes
    that path: intake must refuse it as an unknown service, before parsing anything."""
    r = de_client.post("/api/oc/create", data={"service": "S3", "origin": "TMP_DEPOK"}, files=tmp_upload())
    assert r.status_code == 400
    assert r.json()["detail"] == "unknown_service"


def test_wrong_forward_service_does_not_silently_commit(de_client):
    """A Regular TMP parsed with the Sameday layout reads koli from a different column,
    so every row must error rather than commit garbage (FR-OC5 all-or-nothing)."""
    r = de_client.post("/api/oc/create", data={"service": "S2", "origin": "TMP_DEPOK"}, files=tmp_upload())
    body = r.json() if r.status_code in (201, 422) else {}
    committed = body.get("awb_count", 0)
    errors = body.get("error_count", 0)
    assert r.status_code == 422 or committed == 0 or errors > 0, \
        f"S1 TMP as S2 committed {committed} AWBs with no errors"


def test_create_persists_awbs_po_lines_and_courier_links(de_client):
    r = de_client.post(
        "/api/oc/create", data={"service": "S1", "delivery_date": "2026-08-01", "origin": "TMP_DEPOK"}, files=tmp_upload()
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["awb_count"] > 0
    intake_id = body["intake_id"]

    detail = de_client.get(f"/api/oc/intakes/{intake_id}").json()
    assert len(detail["awbs"]) == body["awb_count"]

    first = detail["awbs"][0]
    # Guide §2.4: the link is the SPA wizard route {base}/c/{token}, not the old /api/c/.
    assert "/c/" in first["courier_url"]
    assert "/api/c/" not in first["courier_url"]

    # FR-OC2: the link token must be unguessable, i.e. not derived from the AWB.
    token = first["courier_url"].rsplit("/", 1)[-1]
    assert first["awb_id"] not in token
    assert len(token) >= 24

    # The link resolves without a session, and carries this AWB's PO lines.
    order = de_client.get(f"/api/c/{token}/order").json()
    assert order["awb_id"] == first["awb_id"]
    assert len(order["po_lines"]) >= 1


def test_both_output_files_are_downloadable(de_client):
    intake_id = de_client.post(
        "/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()
    ).json()["intake_id"]

    xlsx = de_client.get(f"/api/oc/intakes/{intake_id}/upload.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"  # a real zip/xlsx, not an error page

    links = de_client.get(f"/api/oc/intakes/{intake_id}/links.csv")
    assert links.status_code == 200
    assert "text/csv" in links.headers["content-type"]


def test_bad_delivery_date_is_rejected(de_client):
    r = de_client.post(
        "/api/oc/create", data={"service": "S1", "delivery_date": "01-08-2026", "origin": "TMP_DEPOK"}, files=tmp_upload()
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "bad_delivery_date"


def test_reupload_skips_awbs_that_already_exist(de_client):
    """Existing AWBs are skipped, never updated — and when NOTHING is new, say so.

    Until 19 Aug this closed as 201 with awb_count 0 and produced an upload.xlsx holding
    only a header row, which reads like success while shipping nothing.
    """
    first = de_client.post("/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()).json()
    assert first["awb_count"] > 0

    again = de_client.post("/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload())
    assert again.status_code == 409
    assert again.json()["detail"] == "all_awbs_already_exist"


def test_printed_link_redirects_into_the_courier_wizard(de_client):
    intake_id = de_client.post(
        "/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()
    ).json()["intake_id"]
    detail = de_client.get(f"/api/oc/intakes/{intake_id}").json()
    token = detail["awbs"][0]["courier_url"].rsplit("/", 1)[-1]

    r = de_client.get(f"/api/c/{token}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == f"/c/{token}"


def test_delete_intake_frees_the_awbs_for_reupload(de_client):
    """The correction path: delete the bad batch, upload the fixed file."""
    first = de_client.post(
        "/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()
    ).json()
    iid = first["intake_id"]
    assert first["awb_count"] > 0

    assert de_client.delete(f"/api/oc/intakes/{iid}").status_code == 204
    assert de_client.get(f"/api/oc/intakes/{iid}").status_code == 404

    again = de_client.post(
        "/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()
    )
    assert again.status_code == 201
    assert again.json()["awb_count"] == first["awb_count"]


def test_delete_intake_refuses_once_a_courier_has_filed_anything(de_client):
    from conftest import photo

    created = de_client.post(
        "/api/oc/create", data={"service": "S1", "origin": "TMP_DEPOK"}, files=tmp_upload()
    ).json()
    iid = created["intake_id"]
    token = created["links"][0]["url"].rsplit("/c/", 1)[1]
    de_client.post(f"/api/c/{token}/capture", data={"doc_type": "delivery_note"}, files=photo())

    r = de_client.delete(f"/api/oc/intakes/{iid}")
    assert r.status_code == 409
    assert r.json()["detail"] == "intake_has_courier_activity"
    # And nothing was deleted.
    assert de_client.get(f"/api/oc/intakes/{iid}").status_code == 200

"""Migrate to Vasil Operator — a tracking list kept apart from the reject-returns lane.

The properties that matter: only superadmin/KAM reach it, ticking an AWB moves it between
tabs, hiding removes it from this page only, and none of it changes anything on the
other lane.
"""
import pytest

from test_returns import _reject


@pytest.fixture()
def rejected(client, awb):
    return _reject(client, awb, "sebagian")


def _login(client, email):
    assert client.post("/api/auth/dev-login", json={"email": email}).status_code == 200


def _rid(client):
    return client.get("/api/returns").json()["returns"][0]["id"]


def _ids(client, status):
    return [r["id"] for r in client.get(f"/api/vasil/returns?status={status}").json()["returns"]]


def test_only_superadmin_and_kam_reach_the_page(client, rejected):  # noqa: ARG001
    assert client.get("/api/vasil/returns").status_code == 401
    for email in ("dewi.k@ninjavan.co", "agus.s@ninjavan.co"):  # de+implant, station_ic
        _login(client, email)
        assert client.get("/api/vasil/returns").status_code == 403
        assert client.post("/api/vasil/mark-done", json={"ids": [1]}).status_code == 403
        assert client.get("/api/vasil/export.csv").status_code == 403
    for email in ("kam.k@ninjavan.co", "admin@ninjavan.co"):
        _login(client, email)
        assert client.get("/api/vasil/returns").status_code == 200


def test_kam_can_view_reject_returns_but_not_act_on_them(kam_client, rejected):  # noqa: ARG001
    assert kam_client.get("/api/returns").status_code == 200
    rid = _rid(kam_client)
    assert kam_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).status_code == 403


def test_done_and_back_to_pending(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    assert _ids(kam_client, "pending") == [rid]
    assert _ids(kam_client, "done") == []

    assert kam_client.post("/api/vasil/mark-done", json={"ids": [rid]}).json()["updated"] == 1
    assert _ids(kam_client, "pending") == []
    done = kam_client.get("/api/vasil/returns?status=done").json()["returns"][0]
    assert done["id"] == rid and done["vasil_status"] == "done"
    assert done["vasil_done_by_email"] == "kam.k@ninjavan.co"

    # A second tick is a no-op, and undoing a mis-click puts it back.
    assert kam_client.post("/api/vasil/mark-done", json={"ids": [rid]}).json()["updated"] == 0
    assert kam_client.post("/api/vasil/mark-pending", json={"ids": [rid]}).json()["updated"] == 1
    assert _ids(kam_client, "pending") == [rid]
    assert kam_client.get("/api/vasil/returns?status=pending").json()["returns"][0][
        "vasil_done_by_email"] is None
    assert _ids(kam_client, "all") == [rid]


def test_rows_carry_the_door_evidence_for_the_detail_panel(kam_client, rejected):  # noqa: ARG001
    row = kam_client.get("/api/vasil/returns?status=pending").json()["returns"][0]
    kinds = {p["doc_type"] for p in row["proof_photos"]}
    assert {"rejected_goods", "delivery_note", "awb_sticker"} <= kinds
    assert all(p["photo_url"].startswith("/api/media/") for p in row["proof_photos"])


def test_hide_removes_it_from_every_vasil_view_only(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    kam_client.post("/api/vasil/mark-done", json={"ids": [rid]})
    assert kam_client.post("/api/vasil/hide", json={"ids": [rid]}).json()["updated"] == 1
    for view in ("pending", "done", "all"):
        assert _ids(kam_client, view) == []
    # Nothing is deleted: the reject return is still on its own lane, and a hidden row
    # cannot be dragged back by a stray mark.
    assert kam_client.get("/api/returns").json()["returns"][0]["id"] == rid
    assert kam_client.post("/api/vasil/mark-pending", json={"ids": [rid]}).json()["updated"] == 0
    assert kam_client.post("/api/vasil/mark-done", json={"ids": [rid]}).json()["updated"] == 0
    assert "vasil-all.csv" in kam_client.get("/api/vasil/export.csv").headers["content-disposition"]
    assert str(rid) not in kam_client.get("/api/vasil/export.csv").text.splitlines()[-1].split(",")[:1]


def test_nothing_on_the_other_lane_changes(client, rejected):  # noqa: ARG001
    _login(client, "dewi.k@ninjavan.co")
    before = client.get("/api/returns").json()["returns"][0]
    rid = before["id"]
    _login(client, "kam.k@ninjavan.co")
    client.post("/api/vasil/mark-done", json={"ids": [rid]})
    client.post("/api/vasil/mark-pending", json={"ids": [rid]})
    client.post("/api/vasil/mark-done", json={"ids": [rid]})
    _login(client, "dewi.k@ninjavan.co")
    after = client.get("/api/returns").json()["returns"][0]
    assert after == before
    assert after["stage"] == "pending_de_upload"
    # DE can still export the return OC for it, exactly as before.
    assert client.get("/api/returns/export-oc.xlsx").status_code == 200


def test_export_matches_the_reject_returns_columns_and_filters(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    ref = kam_client.get("/api/returns/export.csv").text.splitlines()
    allf = kam_client.get("/api/vasil/export.csv?status=all").text.splitlines()
    assert allf[0] == ref[0]
    assert len(allf) == len(ref)
    assert len(kam_client.get("/api/vasil/export.csv?status=pending").text.splitlines()) == 2
    assert len(kam_client.get("/api/vasil/export.csv?status=done").text.splitlines()) == 1  # header only
    kam_client.post("/api/vasil/mark-done", json={"ids": [rid]})
    assert len(kam_client.get("/api/vasil/export.csv?status=pending").text.splitlines()) == 1
    assert len(kam_client.get("/api/vasil/export.csv?status=done").text.splitlines()) == 2
    assert kam_client.get("/api/vasil/export.csv?status=nope").status_code == 400


def test_every_move_is_audited_and_ids_are_required(kam_client, rejected, dbs):  # noqa: ARG001
    import asyncio

    rid = _rid(kam_client)
    assert kam_client.post("/api/vasil/mark-done", json={"ids": []}).status_code == 400
    kam_client.post("/api/vasil/mark-done", json={"ids": [rid]})
    kam_client.post("/api/vasil/hide", json={"ids": [rid]})

    async def acts():
        return await dbs.fetch_all(
            "SELECT action, actor FROM audit_log WHERE entity = 'vasil_migration' ORDER BY id", ())

    log = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(acts())
    assert [(a["action"], a["actor"]) for a in log] == [
        ("vasil_mark_done", "kam.k@ninjavan.co"), ("vasil_hide", "kam.k@ninjavan.co")]


# ---------------------------------------------------------------- unable to upload ----
def _unable(client, rid, reasons=("dn",)):
    return client.post("/api/vasil/mark-unable", json={"ids": [rid], "reasons": list(reasons)})


def test_unable_moves_the_row_out_of_pending_with_its_reasons(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    assert _unable(kam_client, rid, ["dn", "item"]).json()["updated"] == 1
    assert _ids(kam_client, "pending") == []
    body = kam_client.get("/api/vasil/returns?status=unable").json()
    assert [r["id"] for r in body["returns"]] == [rid]
    assert body["returns"][0]["unable_reasons"] == ["dn", "item"]
    assert body["reason_counts"] == {"dn": 1, "item": 1, "sp_manual": 0}
    assert [r["key"] for r in body["reasons"]] == ["dn", "item", "sp_manual"]
    assert _ids(kam_client, "all") == [rid]


def test_reasons_are_validated_editable_and_cleared_on_pending(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    for bad in ([], ["nope"], ["dn", "nope"]):
        assert _unable(kam_client, rid, bad).status_code == 400
    _unable(kam_client, rid, ["dn"])
    assert kam_client.post("/api/vasil/set-reasons",
                           json={"ids": [rid], "reasons": ["sp_manual", "item"]}).json()["updated"] == 1
    row = kam_client.get("/api/vasil/returns?status=unable").json()["returns"][0]
    assert row["unable_reasons"] == ["item", "sp_manual"]
    # Editing reasons only works on rows that are unable.
    kam_client.post("/api/vasil/mark-pending", json={"ids": [rid]})
    assert kam_client.post("/api/vasil/set-reasons",
                           json={"ids": [rid], "reasons": ["dn"]}).json()["updated"] == 0
    assert _ids(kam_client, "pending") == [rid]
    assert kam_client.get("/api/vasil/returns?status=pending").json()["returns"][0][
        "unable_reasons"] == []
    # Done can't be reached straight from unable — it goes back through pending.
    _unable(kam_client, rid)
    assert kam_client.post("/api/vasil/mark-done", json={"ids": [rid]}).json()["updated"] == 0


def test_reason_filter_and_unable_export_column(kam_client, rejected):  # noqa: ARG001
    rid = _rid(kam_client)
    _unable(kam_client, rid, ["dn", "sp_manual"])
    assert len(kam_client.get("/api/vasil/returns?status=unable&reason=dn").json()["returns"]) == 1
    only_item = kam_client.get("/api/vasil/returns?status=unable&reason=item").json()
    assert only_item["returns"] == [] and only_item["reason_counts"]["dn"] == 1
    assert kam_client.get("/api/vasil/returns?status=unable&reason=zzz").status_code == 400
    lines = kam_client.get("/api/vasil/export.csv?status=unable").text.splitlines()
    ref = kam_client.get("/api/returns/export.csv").text.splitlines()
    assert lines[0] == ref[0] + ",unable_reason"
    assert lines[1].endswith("no proper DN photos, no sp manual photos") or \
        lines[1].endswith('"no proper DN photos, no sp manual photos"')
    # Every other export keeps the Reject returns columns exactly.
    assert kam_client.get("/api/vasil/export.csv?status=all").text.splitlines()[0] == ref[0]


def test_date_filter_is_by_reject_date_on_every_tab(kam_client, rejected):  # noqa: ARG001
    from datetime import date, timedelta

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rid = _rid(kam_client)
    for status in ("pending", "all"):
        q = f"/api/vasil/returns?status={status}"
        assert _ids(kam_client, status) == [rid]
        assert [r["id"] for r in kam_client.get(f"{q}&date_from={today}&date_to={today}").json()["returns"]] == [rid]
        assert kam_client.get(f"{q}&date_from={tomorrow}").json()["returns"] == []
        assert kam_client.get(f"{q}&date_to=2000-01-01").json()["returns"] == []
    assert kam_client.get("/api/vasil/returns?date_from=31-12-2026").status_code == 400
    # The export follows the same window.
    assert len(kam_client.get(f"/api/vasil/export.csv?status=all&date_from={tomorrow}").text.splitlines()) == 1


# -------------------------------------------------------- Vasil-only photo fixes ----
def _photos(client, rid, status="pending"):
    row = next(r for r in client.get(f"/api/vasil/returns?status={status}").json()["returns"]
               if r["id"] == rid)
    return row["proof_photos"]


def _captures(dbs):
    import asyncio

    async def q():
        return await dbs.fetch_all("SELECT id, doc_type, photo_ref FROM document_capture ORDER BY id", ())

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(q())


def test_photo_fixes_stay_on_the_vasil_page(kam_client, rejected, dbs):  # noqa: ARG001
    from conftest import photo

    rid = _rid(kam_client)
    before_caps = _captures(dbs)
    orig = [p for p in _photos(kam_client, rid) if p["doc_type"] == "delivery_note"]
    assert orig and all(p["source"] == "original" and p["editable"] for p in orig)

    # Replace a DN photo: hide the courier's from this view, upload a new one.
    assert kam_client.post(f"/api/vasil/returns/{rid}/photos/remove",
                           json={"source": "original", "ref_id": orig[0]["ref_id"]}).status_code == 200
    up = kam_client.post(f"/api/vasil/returns/{rid}/photos", data={"doc_type": "delivery_note"},
                         files=photo("new.png"))
    assert up.status_code == 201, up.text
    now = [p for p in _photos(kam_client, rid) if p["doc_type"] == "delivery_note"]
    assert orig[0]["ref_id"] not in [p["ref_id"] for p in now if p["source"] == "original"]
    assert len(now) == len(orig) and [p["source"] for p in now].count("vasil") == 1
    mine = next(p for p in now if p["source"] == "vasil")

    # The main lane is untouched: same photos, same rows, nothing deleted.
    assert _captures(dbs) == before_caps
    main = kam_client.get("/api/returns").json()["returns"][0]
    assert any(p["doc_type"] == "delivery_note" for p in main["proof_photos"])

    # Removing the upload only marks it removed.
    assert kam_client.post(f"/api/vasil/returns/{rid}/photos/remove",
                           json={"source": "vasil", "ref_id": mine["ref_id"]}).status_code == 200
    assert not any(p["source"] == "vasil" for p in _photos(kam_client, rid))
    assert kam_client.post(f"/api/vasil/returns/{rid}/photos/remove",
                           json={"source": "vasil", "ref_id": mine["ref_id"]}).status_code == 404
    assert _captures(dbs) == before_caps


def test_photo_upload_rules(kam_client, rejected, client):  # noqa: ARG001
    from conftest import PNG_1PX, photo

    rid = _rid(kam_client)
    post = lambda data, files=None: kam_client.post(  # noqa: E731
        f"/api/vasil/returns/{rid}/photos", data=data, files=files or photo())
    assert post({"doc_type": "awb_sticker"}).status_code == 400          # not an editable kind
    assert post({"doc_type": "sp_manual"}).status_code == 400            # needs a PO
    assert post({"doc_type": "sp_manual", "po_number": "NOPE"}).status_code == 400
    ok = post({"doc_type": "sp_manual", "po_number": "PO-AAA"})
    assert ok.status_code == 201
    assert any(p["doc_type"] == "sp_manual" and p["po_number"] == "PO-AAA" and p["source"] == "vasil"
               for p in _photos(kam_client, rid))
    assert post({"doc_type": "rejected_goods"},
                {"file": ("x.txt", b"hi", "text/plain")}).status_code == 415
    assert post({"doc_type": "rejected_goods"}, {"file": ("e.png", b"", "image/png")}).status_code == 400
    assert kam_client.post(f"/api/vasil/returns/9999/photos", data={"doc_type": "delivery_note"},
                           files={"file": ("p.png", PNG_1PX, "image/png")}).status_code == 404
    _login(client, "dewi.k@ninjavan.co")
    assert client.post(f"/api/vasil/returns/{rid}/photos", data={"doc_type": "delivery_note"},
                       files=photo()).status_code == 403
    assert client.post(f"/api/vasil/returns/{rid}/photos/remove",
                       json={"source": "vasil", "ref_id": 1}).status_code == 403

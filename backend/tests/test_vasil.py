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

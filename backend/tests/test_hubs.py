"""Superadmin hub master (25 Sep 2026): the Order Creation hub list and the courier hub
picker are one table, edited in the app instead of by deploying oc_config.json."""
import asyncio

import pytest


@pytest.fixture
def admin_client(client):
    r = client.post("/api/auth/dev-login", json={"email": "admin@ninjavan.co"})
    assert r.status_code == 200
    return client


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _hub(dbs, name, origin=None, active=1, oc=0):
    _run(dbs.execute(
        "INSERT INTO hub (hub_name, origin, active, oc_enabled) VALUES (?, ?, ?, ?)",
        (name, origin, active, oc),
    ))


def test_hub_admin_requires_superadmin(client):
    assert client.get("/api/hubs").status_code == 401
    # DE runs Order Creation but must not be able to change what it offers.
    de_client = client
    assert de_client.post("/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"}).status_code == 200
    assert de_client.get("/api/hubs").status_code == 403
    assert de_client.post("/api/hubs", json={"hub_name": "SUB-GY5"}).status_code == 403
    assert de_client.patch("/api/hubs/MAC-KD5", json={"active": False}).status_code == 403
    assert de_client.delete("/api/hubs/MAC-KD5").status_code == 403


def test_superadmin_adds_a_hub_and_it_reaches_order_creation(admin_client):
    r = admin_client.post(
        "/api/hubs", json={"hub_name": " sub-gy5 ", "origin": "TMP_SURABAYA", "oc_enabled": True}
    )
    assert r.status_code == 201, r.text
    assert r.json() == {
        "hub_name": "SUB-GY5", "origin": "TMP_SURABAYA", "active": True, "oc_enabled": True,
        "awb_count": 0, "updated_at": r.json()["updated_at"],
    }
    # No deploy: the very next services call offers it.
    assert "SUB-GY5" in admin_client.get("/api/oc/services").json()["hubs"]


def test_new_hub_is_courier_only_unless_switched_on(admin_client):
    admin_client.post("/api/hubs", json={"hub_name": "SUB-GY5"})
    assert "SUB-GY5" not in admin_client.get("/api/oc/services").json()["hubs"]
    listed = {h["hub_name"]: h for h in admin_client.get("/api/hubs").json()["hubs"]}
    assert listed["SUB-GY5"]["active"] is True and listed["SUB-GY5"]["oc_enabled"] is False


@pytest.mark.parametrize("name", ["", "X", "SUB GY5", "SUB_GY5", "-SUB", "A" * 33])
def test_hub_name_is_validated(admin_client, name):
    r = admin_client.post("/api/hubs", json={"hub_name": name})
    assert r.status_code == 400 and r.json()["detail"] == "bad_hub_name"


def test_duplicate_hub_is_refused(admin_client, dbs):
    _hub(dbs, "SUB-GY5")
    r = admin_client.post("/api/hubs", json={"hub_name": "sub-gy5"})
    assert r.status_code == 409 and r.json()["detail"] == "already_exists"


def test_origin_must_be_a_configured_warehouse(admin_client, dbs):
    r = admin_client.post("/api/hubs", json={"hub_name": "SUB-GY5", "origin": "TMP_MARS"})
    assert r.status_code == 400 and r.json()["detail"] == "bad_origin"
    _hub(dbs, "SUB-GY5")
    r = admin_client.patch("/api/hubs/SUB-GY5", json={"origin": "TMP_MARS"})
    assert r.status_code == 400 and r.json()["detail"] == "bad_origin"


def test_patch_sets_and_clears_fields_independently(admin_client, dbs):
    _hub(dbs, "SUB-GY5", origin="TMP_SURABAYA", oc=1)
    r = admin_client.patch("/api/hubs/SUB-GY5", json={"oc_enabled": False})
    assert r.status_code == 200
    # Only the named field moved.
    assert r.json()["oc_enabled"] is False and r.json()["origin"] == "TMP_SURABAYA"
    # An explicit null clears origin; omitting it (above) left it alone.
    r = admin_client.patch("/api/hubs/sub-gy5", json={"origin": None, "active": False})
    assert r.json()["origin"] is None and r.json()["active"] is False


def test_patch_rejects_bad_input(admin_client, dbs):
    _hub(dbs, "SUB-GY5")
    assert admin_client.patch("/api/hubs/NOPE-NOPE", json={"active": False}).json()["detail"] == "not_found"
    assert admin_client.patch("/api/hubs/SUB-GY5", json={}).json()["detail"] == "nothing_to_update"
    assert admin_client.patch("/api/hubs/SUB-GY5", json={"active": "no"}).json()["detail"] == "bad_active"
    # A column name outside the allowed three is ignored, never written.
    r = admin_client.patch("/api/hubs/SUB-GY5", json={"hub_label": "x"})
    assert r.json()["detail"] == "nothing_to_update"


def test_deactivated_hub_leaves_both_pickers(admin_client, dbs, awb):
    _hub(dbs, "SUB-GY5", oc=1)
    admin_client.patch("/api/hubs/SUB-GY5", json={"active": False})
    assert "SUB-GY5" not in admin_client.get("/api/oc/services").json()["hubs"]
    assert "SUB-GY5" not in admin_client.get(f"/api/c/{awb['token']}/order").json()["hubs"]


def test_unused_hub_can_be_deleted(admin_client, dbs):
    _hub(dbs, "SUB-GY5")
    r = admin_client.delete("/api/hubs/SUB-GY5")
    assert r.status_code == 200 and r.json() == {"deleted": "SUB-GY5"}
    assert admin_client.delete("/api/hubs/SUB-GY5").json()["detail"] == "not_found"


def test_hub_on_an_awb_cannot_be_deleted_only_deactivated(admin_client, dbs, awb):
    _hub(dbs, "SUB-GY5")
    _run(dbs.execute("UPDATE awb SET hub_name = 'SUB-GY5' WHERE awb_id = ?", (awb["awb_id"],)))
    listed = {h["hub_name"]: h for h in admin_client.get("/api/hubs").json()["hubs"]}
    assert listed["SUB-GY5"]["awb_count"] == 1

    r = admin_client.delete("/api/hubs/SUB-GY5")
    assert r.status_code == 409 and r.json()["detail"] == "hub_in_use"
    assert admin_client.patch("/api/hubs/SUB-GY5", json={"active": False}).status_code == 200


def test_every_change_is_audited(admin_client, dbs):
    admin_client.post("/api/hubs", json={"hub_name": "SUB-GY5"})
    admin_client.patch("/api/hubs/SUB-GY5", json={"oc_enabled": True})
    admin_client.delete("/api/hubs/SUB-GY5")
    rows = _run(dbs.fetch_all(
        "SELECT actor, action, entity_id FROM audit_log WHERE entity = 'hub' ORDER BY id", ()
    ))
    assert [r["action"] for r in rows] == ["hub_create", "hub_update", "hub_delete"]
    assert all(r["actor"] == "admin@ninjavan.co" for r in rows)
    assert rows[1]["entity_id"] == "SUB-GY5: oc_enabled=True"


def test_list_offers_the_configured_origins(admin_client):
    codes = [o["code"] for o in admin_client.get("/api/hubs").json()["origins"]]
    assert "TMP_DEPOK" in codes and "TMP_SURABAYA" in codes

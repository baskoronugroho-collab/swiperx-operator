"""Lane 3 — the reject-return worklist: acknowledge, then record the replacement TIDs."""
import pytest

from conftest import photo


@pytest.fixture()
def rejected(client, awb):
    """Drive a real courier reject so the worklist row is created the way production
    creates it, rather than inserted behind the API's back."""
    t = awb["token"]
    for doc in ("pharmacy_pod", "receiver_pod"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    client.post(f"/api/c/{t}/submit", json={"outcome": "reject", "return_type": "sebagian"})
    return awb


def test_worklist_requires_a_session(client, rejected):  # noqa: ARG001
    assert client.get("/api/returns").status_code == 401


def test_row_starts_pending_and_carries_the_door_proof(de_client, rejected):  # noqa: ARG001
    body = de_client.get("/api/returns").json()
    assert body["rts_shipper_id"] == "11398434"
    row = body["returns"][0]
    assert row["stage"] == "pending_ack"
    assert row["acknowledged_at"] is None
    assert row["pharmacy_name"] == "Apotek Uji"
    # Ops must be able to see what they're acknowledging.
    kinds = {p["doc_type"] for p in row["proof_photos"]}
    assert {"rejected_goods", "awb_sticker", "delivery_note"} <= kinds


def test_default_filter_shows_only_unacknowledged(de_client, rejected):  # noqa: ARG001
    assert len(de_client.get("/api/returns?stage=pending_ack").json()["returns"]) == 1
    assert de_client.get("/api/returns?stage=acknowledged").json()["returns"] == []

    rid = de_client.get("/api/returns").json()["returns"][0]["id"]
    de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": True})

    assert de_client.get("/api/returns?stage=pending_ack").json()["returns"] == []
    assert len(de_client.get("/api/returns?stage=acknowledged").json()["returns"]) == 1


def test_acknowledge_records_who_and_when_and_can_be_undone(de_client, rejected):  # noqa: ARG001
    rid = de_client.get("/api/returns").json()["returns"][0]["id"]

    row = de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": True}).json()
    assert row["stage"] == "acknowledged"
    assert row["acknowledged_at"] is not None
    assert row["acknowledged_by_email"] == "dewi.k@ninjavan.co"

    row = de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": False}).json()
    assert row["stage"] == "pending_ack"
    assert row["acknowledged_by_email"] is None


def test_tids_cannot_be_recorded_before_acknowledging(de_client, rejected):  # noqa: ARG001
    rid = de_client.get("/api/returns").json()["returns"][0]["id"]
    r = de_client.post(f"/api/returns/{rid}/tids", json={"return_tids": "RTS-1"})
    assert r.status_code == 409
    assert r.json()["detail"] == "not_acknowledged"


def test_recording_tids_closes_the_row(de_client, rejected):  # noqa: ARG001
    rid = de_client.get("/api/returns").json()["returns"][0]["id"]
    de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": True})

    row = de_client.post(f"/api/returns/{rid}/tids", json={"return_tids": "RTS-77120043, RTS-77120044"}).json()
    assert row["stage"] == "tids_sent"
    assert row["return_tids"] == "RTS-77120043, RTS-77120044"
    assert row["tids_sent_by_email"] == "dewi.k@ninjavan.co"

    # A closed row must not be silently reopened by un-ticking acknowledge.
    assert de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": False}).status_code == 409


def test_blank_tids_are_rejected(de_client, rejected):  # noqa: ARG001
    rid = de_client.get("/api/returns").json()["returns"][0]["id"]
    de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": True})
    r = de_client.post(f"/api/returns/{rid}/tids", json={"return_tids": "  ,  ,"})
    assert r.status_code == 400


def test_bad_stage_filter_is_rejected(de_client, rejected):  # noqa: ARG001
    assert de_client.get("/api/returns?stage=nonsense").status_code == 400


def test_csv_export_carries_the_audit_trail(de_client, rejected):  # noqa: ARG001
    rid = de_client.get("/api/returns").json()["returns"][0]["id"]
    de_client.post(f"/api/returns/{rid}/acknowledge", json={"acknowledged": True})
    de_client.post(f"/api/returns/{rid}/tids", json={"return_tids": "RTS-999"})

    r = de_client.get("/api/returns/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert "forward_awb" in body
    assert "AWBTEST01" in body
    assert "RTS-999" in body
    assert "dewi.k@ninjavan.co" in body

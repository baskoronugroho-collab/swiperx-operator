"""Courier capture (M2) — the tokenized, unauthenticated surface.

The completeness gate is the compliance control (PRD §9), so most of these tests are
about what the API REFUSES rather than what it accepts.
"""
from conftest import photo


def test_order_resolves_without_a_session(client, awb):
    r = client.get(f"/api/c/{awb['token']}/order")
    assert r.status_code == 200
    body = r.json()
    assert body["awb_id"] == "AWBTEST01"
    assert [p["po_number"] for p in body["po_lines"]] == ["PO-AAA", "PO-BBB"]
    assert body["captures"] == []
    assert body["terminal"] is False
    # The 9 locked fail reasons ship with the order so the app needs no second call.
    assert len(body["fail_reasons"]) == 9
    assert body["fail_reasons"][0]["code"] == "cancelled"


def test_unknown_token_is_404(client, awb):  # noqa: ARG001
    assert client.get("/api/c/not-a-real-token/order").status_code == 404


def test_capture_stores_a_photo_and_scopes_media_to_the_awb(client, awb):
    t = awb["token"]
    r = client.post(f"/api/c/{t}/capture", data={"doc_type": "pharmacy_pod"}, files=photo())
    assert r.status_code == 201, r.text
    url = r.json()["photo_url"]
    assert url.startswith(f"/api/c/{t}/media/")

    assert client.get(url).status_code == 200

    # Same blob, wrong token → must not resolve. This is the whole security model.
    ref = url.rsplit("/", 1)[-1]
    assert client.get(f"/api/c/some-other-token/media/{ref}").status_code == 404


def test_capture_rejects_non_images_and_unknown_doc_types(client, awb):
    t = awb["token"]
    bad = client.post(
        f"/api/c/{t}/capture", data={"doc_type": "pharmacy_pod"},
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert bad.status_code == 415

    unknown = client.post(f"/api/c/{t}/capture", data={"doc_type": "selfie"}, files=photo())
    assert unknown.status_code == 400


def test_sp_manual_requires_a_known_po(client, awb):
    t = awb["token"]
    missing_po = client.post(f"/api/c/{t}/capture", data={"doc_type": "sp_manual"}, files=photo())
    assert missing_po.status_code == 400
    assert missing_po.json()["detail"] == "sp_manual_needs_po"

    wrong_po = client.post(
        f"/api/c/{t}/capture", data={"doc_type": "sp_manual", "po_number": "PO-NOPE"}, files=photo()
    )
    assert wrong_po.status_code == 400
    assert wrong_po.json()["detail"] == "unknown_po"

    ok = client.post(
        f"/api/c/{t}/capture", data={"doc_type": "sp_manual", "po_number": "PO-AAA"}, files=photo()
    )
    assert ok.status_code == 201


def test_single_shot_documents_replace_rather_than_accumulate(client, awb):
    t = awb["token"]
    for _ in range(3):
        client.post(f"/api/c/{t}/capture", data={"doc_type": "pharmacy_pod"}, files=photo())
    captures = client.get(f"/api/c/{t}/order").json()["captures"]
    assert len([c for c in captures if c["doc_type"] == "pharmacy_pod"]) == 1


def test_delivery_note_accumulates_because_reject_needs_two_shots(client, awb):
    t = awb["token"]
    for _ in range(2):
        client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo())
    captures = client.get(f"/api/c/{t}/order").json()["captures"]
    assert len([c for c in captures if c["doc_type"] == "delivery_note"]) == 2


def _complete_forward(client, t, *, attest=True):
    for doc in ("pharmacy_pod", "receiver_pod"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    if attest:
        client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    return dn


def test_gate_blocks_until_every_required_photo_exists(client, awb):
    t = awb["token"]
    g = client.get(f"/api/c/{t}/gate?outcome=delivered").json()
    assert g["complete"] is False
    assert len(g["missing"]) == 4  # 3 photos + the attestation

    _complete_forward(client, t)
    assert client.get(f"/api/c/{t}/gate?outcome=delivered").json()["complete"] is True


def test_attestation_alone_blocks_submission(client, awb):
    """Photos present but the signed+stamped tick missing — this is the control that
    reverses v2.1 and must not be bypassable."""
    t = awb["token"]
    _complete_forward(client, t, attest=False)
    g = client.get(f"/api/c/{t}/gate?outcome=delivered").json()
    assert g["complete"] is False
    assert any("distempel" in m for m in g["missing"])

    r = client.post(f"/api/c/{t}/submit", json={"outcome": "delivered"})
    assert r.status_code == 422


def test_submit_delivered_closes_the_awb(client, awb):
    t = awb["token"]
    _complete_forward(client, t)
    r = client.post(f"/api/c/{t}/submit", json={"outcome": "delivered"})
    assert r.status_code == 200
    assert r.json() == {"status": "delivered", "return_flagged": False, "return_awbs": []}

    order = client.get(f"/api/c/{t}/order").json()
    assert order["status"] == "delivered"
    assert order["terminal"] is True

    # A second submission must not reopen a closed AWB.
    assert client.post(f"/api/c/{t}/submit", json={"outcome": "delivered"}).status_code == 409


def test_reject_requires_the_full_reject_set(client, awb):
    t = awb["token"]
    _complete_forward(client, t)
    # Forward set is complete, but a reject needs more.
    g = client.get(f"/api/c/{t}/gate?outcome=reject").json()
    assert g["complete"] is False

    client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo())
    client.post(f"/api/c/{t}/capture", data={"doc_type": "rejected_goods"}, files=photo())
    client.post(f"/api/c/{t}/capture", data={"doc_type": "awb_sticker"}, files=photo())
    assert client.get(f"/api/c/{t}/gate?outcome=reject").json()["complete"] is True


def test_reject_opens_a_row_on_the_ops_worklist(client, de_client, awb):
    t = awb["token"]
    _complete_forward(client, t)
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())

    r = client.post(f"/api/c/{t}/submit", json={"outcome": "reject", "return_type": "sebagian"})
    assert r.status_code == 200
    assert r.json()["return_flagged"] is True
    assert r.json()["return_awbs"] == ["AWBTEST01"]

    rows = de_client.get("/api/returns").json()["returns"]
    assert len(rows) == 1
    assert rows[0]["original_awb_id"] == "AWBTEST01"
    assert rows[0]["stage"] == "pending_ack"
    assert rows[0]["return_type"] == "sebagian"


def test_failed_delivery_records_the_reason_and_opens_no_return(client, de_client, awb):
    t = awb["token"]
    client.post(f"/api/c/{t}/capture", data={"doc_type": "awb_sticker"}, files=photo())
    r = client.post(f"/api/c/{t}/fail", json={"fail_reason": "office_closed", "reason_note": "shutter down"})
    assert r.status_code == 200
    assert client.get(f"/api/c/{t}/order").json()["status"] == "delivery_failed"
    # Nothing was delivered → nothing to reject.
    assert de_client.get("/api/returns").json()["returns"] == []


def test_failed_delivery_needs_a_proof_photo(client, awb):
    r = client.post(f"/api/c/{awb['token']}/fail", json={"fail_reason": "office_closed"})
    assert r.status_code == 422


def test_unknown_fail_reason_is_rejected(client, awb):
    t = awb["token"]
    client.post(f"/api/c/{t}/capture", data={"doc_type": "awb_sticker"}, files=photo())
    r = client.post(f"/api/c/{t}/fail", json={"fail_reason": "bad_weather"})
    assert r.status_code == 400


def test_delete_capture_lets_the_courier_retake(client, awb):
    t = awb["token"]
    cap = client.post(f"/api/c/{t}/capture", data={"doc_type": "pharmacy_pod"}, files=photo()).json()
    assert client.delete(f"/api/c/{t}/capture/{cap['id']}").status_code == 204
    assert client.get(f"/api/c/{t}/order").json()["captures"] == []

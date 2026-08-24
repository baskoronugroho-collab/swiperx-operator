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


def _complete_reject(client, t, *, attest=True):
    """The full reject evidence set (19 Aug rework): DN twice (full page + return
    close-up), the attestation on one of them, the goods, and the AWB label."""
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    if attest:
        client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    return dn


def test_no_return_needs_no_photos_at_all(client, awb):
    """19 Aug rework: the link is opened only when a return needs reporting. 'Tidak ada
    retur' is a single confirm — forward-delivery proof lives in the Ninja driver app."""
    t = awb["token"]
    g = client.get(f"/api/c/{t}/gate?outcome=delivered").json()
    assert g["complete"] is True
    assert g["missing"] == []


def test_gate_blocks_a_reject_until_every_required_photo_exists(client, awb):
    t = awb["token"]
    g = client.get(f"/api/c/{t}/gate?outcome=reject").json()
    assert g["complete"] is False
    assert len(g["missing"]) == 4  # 2x DN, attestation, goods, label

    _complete_reject(client, t)
    assert client.get(f"/api/c/{t}/gate?outcome=reject").json()["complete"] is True


def test_attestation_alone_blocks_a_reject(client, awb):
    """Photos present but the signed+stamped tick missing — this is the control that
    reverses v2.1 and must not be bypassable."""
    t = awb["token"]
    _complete_reject(client, t, attest=False)
    g = client.get(f"/api/c/{t}/gate?outcome=reject").json()
    assert g["complete"] is False
    assert any("distempel" in m for m in g["missing"])

    r = client.post(f"/api/c/{t}/submit", json={"outcome": "reject", "return_type": "sebagian"})
    assert r.status_code == 422


def test_submit_delivered_closes_the_awb(client, awb):
    t = awb["token"]
    r = client.post(f"/api/c/{t}/submit", json={"outcome": "delivered"})
    assert r.status_code == 200
    assert r.json() == {"status": "delivered", "return_flagged": False, "return_awbs": []}

    order = client.get(f"/api/c/{t}/order").json()
    assert order["status"] == "delivered"
    assert order["terminal"] is True

    # A second submission must not reopen a closed AWB.
    assert client.post(f"/api/c/{t}/submit", json={"outcome": "delivered"}).status_code == 409


def test_one_dn_shot_is_not_enough_for_a_reject(client, awb):
    """The close-up of the return section is a SECOND delivery_note capture — one full-page
    shot alone must not pass the gate."""
    t = awb["token"]
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    client.post(f"/api/c/{t}/capture", data={"doc_type": "rejected_goods"}, files=photo())
    client.post(f"/api/c/{t}/capture", data={"doc_type": "awb_sticker"}, files=photo())
    g = client.get(f"/api/c/{t}/gate?outcome=reject").json()
    assert g["complete"] is False

    client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo())
    assert client.get(f"/api/c/{t}/gate?outcome=reject").json()["complete"] is True


def test_reject_opens_a_row_on_the_ops_worklist(client, de_client, awb):
    t = awb["token"]
    _complete_reject(client, t)
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


# --- driver identity: hub fallback (19 Aug 2026) ---


def _hub(dbs, name="MAC-KD5"):
    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        dbs.execute("INSERT INTO hub (hub_name, origin, active) VALUES (?, 'TMP_DEPOK', 1)", (name,))
    )


def test_identity_rejects_a_hub_not_on_the_list(client, dbs, awb):
    _hub(dbs)
    t = awb["token"]
    r = client.post(f"/api/c/{t}/identity", json={"driver_id": "123", "hub_name": "XXX-XXX"})
    assert r.status_code == 400
    assert r.json()["detail"] == "unknown_hub"


def test_identity_fallback_accepts_a_free_text_hub(client, dbs, awb):
    """The driver ticks 'hub saya tidak ada di daftar' — free text is accepted, uppercased,
    and stored, so IC can still find the row even before the hub master is updated."""
    _hub(dbs)
    t = awb["token"]
    r = client.post(
        f"/api/c/{t}/identity",
        json={"driver_id": "123", "hub_name": "bdo-baru", "hub_not_listed": True},
    )
    assert r.status_code == 200
    assert r.json()["hub_name"] == "BDO-BARU"
    assert client.get(f"/api/c/{t}/order").json()["hub_name"] == "BDO-BARU"

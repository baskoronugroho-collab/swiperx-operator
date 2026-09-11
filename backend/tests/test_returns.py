"""Lane 3 — the reject-return pipeline (validator gate removed 31 Aug 2026).

    pending_de_upload -> pending_print -> printed     (sebagian)
    pending_de_upload -> rts_triggered               (semua)

These pin the two properties that make the pipeline trustworthy: a submitted reject is
immediately actionable by DE with nothing queued in front of it, and each closing path
refuses the other type's rows.
"""
import io

import openpyxl
import pytest

from conftest import photo


# The `awb` fixture carries two PO lines; a partial reject must say which one came back,
# because the return OC's tracking number is built from it.
PO = "PO-AAA"


def _reject(client, awb, return_type, pcs=3, po=PO):
    """Drive a real courier reject end to end, the way production creates the row."""
    t = awb["token"]
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    r = client.post(
        f"/api/c/{t}/submit",
        json={"outcome": "reject", "return_type": return_type, "reject_pcs": pcs,
              "po_number": po if return_type == "sebagian" else None},
    )
    assert r.status_code == 200, r.text
    return awb


@pytest.fixture()
def rejected(client, awb):
    return _reject(client, awb, "sebagian")


@pytest.fixture()
def fully_rejected(client, awb):
    return _reject(client, awb, "semua")


def _row(c):
    return c.get("/api/returns").json()["returns"][0]


def _oc_rows(response):
    """The return OC export, read back as the workbook DE actually hands to Ninja.

    XLSX since 9 Sep 2026 — a CSV could not stop Excel retyping the sender phone and the
    delivery date when someone opened the download to check it.
    """
    ws = openpyxl.load_workbook(io.BytesIO(response.content)).active
    hdr = [c.value for c in ws[1]]
    return [dict(zip(hdr, [c.value for c in row])) for row in ws.iter_rows(min_row=2)]


# ------------------------------------------------------------ entry state ----
def test_worklist_requires_a_session(client, rejected):  # noqa: ARG001
    assert client.get("/api/returns").status_code == 401


def test_row_lands_on_de_with_the_door_evidence(de_client, rejected):  # noqa: ARG001
    """Submission IS the entry event — no queue sits in front of DE."""
    r = _row(de_client)
    assert r["stage"] == "pending_de_upload"
    assert r["reject_pcs"] == 3
    assert r["origin"] == "TMP_DEPOK" and r["origin_unknown"] is False
    # The photos still ride along; DE reads them before exporting, nobody signs them off.
    kinds = {p["doc_type"] for p in r["proof_photos"]}
    assert {"delivery_note", "rejected_goods", "awb_sticker"} <= kinds


def test_a_fresh_reject_is_immediately_actionable(de_client, rejected):  # noqa: ARG001
    """The old flow returned 404/0 here until a Validator ticked the row first."""
    rid = _row(de_client)["id"]
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 200
    assert de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).json()["updated"] == 1


def test_reject_submit_requires_the_pcs_count(client, awb):
    t = awb["token"]
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())
    r = client.post(f"/api/c/{t}/submit", json={"outcome": "reject", "return_type": "sebagian"})
    assert r.status_code == 422
    assert r.json()["detail"] == "reject_pcs_required"


# ------------------------------------------------- the retired validator ----
def test_the_validate_endpoint_is_gone(de_client, rejected):  # noqa: ARG001
    rid = _row(de_client)["id"]
    assert de_client.post("/api/returns/validate", json={"ids": [rid]}).status_code == 404


def test_validator_role_no_longer_reaches_the_lane(validator_client, rejected):  # noqa: ARG001
    """Vera holds ONLY `validator`, and the lane is now closed to it."""
    assert validator_client.get("/api/returns").status_code == 403


def test_pending_validator_is_not_a_stage_any_more(de_client, rejected):  # noqa: ARG001
    assert de_client.get("/api/returns?stage=pending_validator").status_code == 400


# --------------------------------------------------- sebagian: OC pipeline ----
def test_partial_walks_export_upload_print(de_client, rejected):
    rid = _row(de_client)["id"]

    # Export: one CSV row built from the PO the courier picked, addressed to the origin
    # warehouse, pcs in col Y. The parcel and its piece must NOT be the same string.
    r = de_client.get("/api/returns/export-oc.xlsx")
    assert r.status_code == 200
    # The workbook content type, so a browser hands it to Excel rather than showing it.
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "Return-OC-pending.xlsx" in r.headers["content-disposition"]
    rows = _oc_rows(r)
    assert len(rows) == 1
    row = rows[0]
    assert row["requested_tracking_number"] == f"{rejected['awb_id']}-R"
    assert row["bundle_information.requested_piece_tracking_numbers"] == f"{PO}1-R01"
    assert row["reference.merchant_order_number"] == rejected["awb_id"]
    assert row["to.address.city"] == "Depok"
    assert row["parcel_job.items.0.item_description"] == "3"

    # Mark uploaded -> Pending Print, with <AWB>-R stamped for IC's OPV2 search.
    assert de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).json()["updated"] == 1
    r2 = _row(de_client)
    assert r2["stage"] == "pending_print"
    assert r2["return_awb_id"] == f"{rejected['awb_id']}-R"
    # Once uploaded it leaves the export file.
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 404

    # Printed & labelled -> closed.
    assert de_client.post("/api/returns/mark-printed", json={"ids": [rid]}).json()["updated"] == 1
    assert _row(de_client)["stage"] == "printed"


def test_pending_print_can_be_sent_back_so_the_oc_csv_can_be_exported(de_client, rejected):
    """The real failure: DE marks the OC uploaded but never pulled the CSV.

    The export only ever contains `pending_de_upload` rows, so the row is stranded — the file
    Ninja needs cannot be produced from any stage it can now reach. Sending it back restores
    exactly that, and clears the upload stamp so nothing claims an upload that never happened.
    """
    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 404  # stranded

    assert de_client.post("/api/returns/reopen-upload", json={"ids": [rid]}).json()["updated"] == 1
    back = _row(de_client)
    assert back["stage"] == "pending_de_upload"
    assert back["de_uploaded_at"] is None
    assert back["return_awb_id"] is None  # the <AWB>-R was never really issued

    # The whole point: the OC CSV is exportable again, unchanged.
    r = de_client.get("/api/returns/export-oc.xlsx")
    assert r.status_code == 200
    assert _oc_rows(r)[0]["requested_tracking_number"] == f"{rejected['awb_id']}-R"

    # And the row walks forward again from there.
    assert de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).json()["updated"] == 1
    assert _row(de_client)["stage"] == "pending_print"


def test_station_ic_cannot_send_a_row_back(client, de_client, rejected):  # noqa: ARG001
    """IC finds out, DE moves. Un-doing DE's own upload claim stays on the DE desk."""
    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})

    client.post("/api/auth/dev-login", json={"email": "agus.s@ninjavan.co"})  # station_ic only
    assert client.post("/api/returns/reopen-upload", json={"ids": [rid]}).status_code == 403
    assert _row(client)["stage"] == "pending_print"


def test_station_ic_flags_the_row_and_de_sends_it_back(client, de_client, rejected):  # noqa: ARG001
    """The whole loop: IC can't find the AWB, says so on the row, DE reads it and acts.

    The flag is the IC's only move here, and it is a NOTE — the row does not budge. What it
    buys is that the reason reaches DE on the row itself instead of in a chat group.
    """
    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})

    client.post("/api/auth/dev-login", json={"email": "agus.s@ninjavan.co"})  # station_ic only
    r = client.post(
        "/api/returns/flag",
        json={"ids": [rid], "note": "AWB tidak ditemukan di NV / OPV2"},
    )
    assert r.status_code == 200, r.text
    flagged = _row(client)
    assert flagged["flagged"] is True
    assert flagged["flag_note"] == "AWB tidak ditemukan di NV / OPV2"
    assert flagged["flagged_by_email"] == "agus.s@ninjavan.co"
    assert flagged["stage"] == "pending_print"  # a note, not a stage

    # DE reads it and makes the move the IC could not.
    client.post("/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"})
    assert client.post("/api/returns/reopen-upload", json={"ids": [rid]}).json()["updated"] == 1
    back = _row(client)
    assert back["stage"] == "pending_de_upload"
    assert back["flagged"] is False  # answered — a stale flag would send DE looking twice
    assert client.get("/api/returns/export-oc.xlsx").status_code == 200


def test_superadmin_can_do_every_move_on_the_lane(client, de_client, rejected):  # noqa: ARG001
    """Superadmin is a SUPERSET of every role, never a role with a hole in it.

    It holds `superadmin` and nothing else, so every action here reaches it only through
    `require_roles`'s short-circuit. Pinned as a property of the lane rather than trusted:
    the person doing this job in the pilot may be standing at the station one day and at the
    DE desk the next, and an action they cannot reach is an action that does not happen.
    """
    rid = _row(de_client)["id"]
    client.post("/api/auth/dev-login", json={"email": "admin@ninjavan.co"})

    # DE's moves.
    assert client.get("/api/returns/export-oc.xlsx").status_code == 200
    assert client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).json()["updated"] == 1
    # Station IC's move — the one a DE-only account is offered but does not need.
    assert client.post("/api/returns/flag", json={"ids": [rid], "note": "cek"}).json()["updated"] == 1
    # Both answers to a flag, which sit on the DE desk.
    assert client.post("/api/returns/unflag", json={"ids": [rid]}).json()["updated"] == 1
    assert client.post("/api/returns/reopen-upload", json={"ids": [rid]}).json()["updated"] == 1
    assert _row(client)["stage"] == "pending_de_upload"
    # And IC's closing move, on a row walked back forward.
    client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    assert client.post("/api/returns/mark-printed", json={"ids": [rid]}).json()["updated"] == 1
    assert _row(client)["stage"] == "printed"


def test_a_flag_needs_a_note_and_only_sticks_to_pending_print(de_client, rejected):  # noqa: ARG001
    """Empty remarks say nothing, and no other stage has an AWB to fail to find."""
    rid = _row(de_client)["id"]
    # Still waiting on DE — nobody is hunting for an AWB yet.
    assert de_client.post("/api/returns/flag", json={"ids": [rid], "note": "x"}).json()["updated"] == 0

    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    assert de_client.post("/api/returns/flag", json={"ids": [rid], "note": "   "}).status_code == 400
    assert de_client.post("/api/returns/flag", json={"ids": [rid], "note": "x" * 501}).status_code == 400
    assert _row(de_client)["flagged"] is False


def test_de_can_clear_a_flag_without_moving_the_row(client, de_client, rejected):  # noqa: ARG001
    """The other answer: DE looked, the AWB is there, the IC should look again."""
    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    client.post("/api/auth/dev-login", json={"email": "agus.s@ninjavan.co"})
    client.post("/api/returns/flag", json={"ids": [rid], "note": "tidak ketemu"})
    # The raiser cannot withdraw it — a flag no one read would be worse than none.
    assert client.post("/api/returns/unflag", json={"ids": [rid]}).status_code == 403

    client.post("/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"})
    assert client.post("/api/returns/unflag", json={"ids": [rid]}).json()["updated"] == 1
    cleared = _row(client)
    assert cleared["flagged"] is False
    assert cleared["stage"] == "pending_print"  # still IC's to print


def test_send_back_only_moves_pending_print_rows(de_client, rejected):  # noqa: ARG001
    """One door, one direction: not a fresh reject, and not past a print that happened."""
    rid = _row(de_client)["id"]
    # Already waiting on DE — nothing to undo.
    assert de_client.post("/api/returns/reopen-upload", json={"ids": [rid]}).json()["updated"] == 0

    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    de_client.post("/api/returns/mark-printed", json={"ids": [rid]})
    # Printed and labelled — the label exists in the world, undoing here would lie about it.
    assert de_client.post("/api/returns/reopen-upload", json={"ids": [rid]}).json()["updated"] == 0
    assert _row(de_client)["stage"] == "printed"


def test_sending_back_is_recorded_in_the_audit_log(de_client, dbs, rejected):  # noqa: ARG001
    """Clearing the stamp erases the row's own trail — the audit log is where it survives."""
    import asyncio

    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    de_client.post("/api/returns/reopen-upload", json={"ids": [rid]})

    async def entries():
        return await dbs.fetch_all(
            "SELECT actor, entity_id FROM audit_log WHERE action = 'return_upload_reopened'", ()
        )

    rows = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(entries())
    assert len(rows) == 1
    assert rows[0]["actor"] == "dewi.k@ninjavan.co"
    assert str(rid) in rows[0]["entity_id"]


def test_a_partial_reject_must_name_the_po_it_came_from(client, awb):
    """Only the courier can answer this, so the door is where it is asked — and enforced.

    The return OC's `requested_tracking_number` IS `<PO>1`. Without a PO there is no number
    to issue, and no desk downstream can look at a box of returned strips and say which
    purchase order they were ordered under.
    """
    t = awb["token"]
    dn = client.post(f"/api/c/{t}/capture", data={"doc_type": "delivery_note"}, files=photo()).json()
    client.patch(f"/api/c/{t}/capture/{dn['id']}", json={"signed_stamped": True})
    for doc in ("delivery_note", "rejected_goods", "awb_sticker"):
        client.post(f"/api/c/{t}/capture", data={"doc_type": doc}, files=photo())

    body = {"outcome": "reject", "return_type": "sebagian", "reject_pcs": 3}
    assert client.post(f"/api/c/{t}/submit", json=body).status_code == 422
    # A PO that is not on this AWB would mint a number for an order that does not exist.
    r = client.post(f"/api/c/{t}/submit", json={**body, "po_number": "PO-NOT-HERE"})
    assert r.status_code == 422
    assert r.json()["detail"] == "po_number_not_on_awb"
    assert client.post(f"/api/c/{t}/submit", json={**body, "po_number": "PO-BBB"}).status_code == 200


def test_a_full_refusal_is_not_asked_for_a_po(client, de_client, awb):
    """`semua` closes by RTS on the forward number and never produces an OC row."""
    _reject(client, awb, "semua", po=None)
    row = _row(de_client)
    assert row["return_type"] == "semua"
    assert row["po_number"] is None
    assert row["po_unknown"] is False  # there is no field for a PO to be missing from


def test_a_row_with_no_po_is_held_out_of_the_export(de_client, dbs, rejected):
    """Legacy rows — filed before the courier was asked — cannot be exported or uploaded.

    Unlike origin-unknown there is deliberately NO bulk-set to clear this: origin is a fact
    about the warehouse a batch left, which a desk knows; the PO is a fact about what is in
    the box, which only the person holding it knew.
    """
    import asyncio

    async def forget():
        await dbs.execute("UPDATE return_parcel SET po_number = NULL WHERE original_awb_id = ?",
                          (rejected["awb_id"],))

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(forget())

    row = _row(de_client)
    assert row["po_unknown"] is True
    assert row["po_number"] is None  # two PO lines on the AWB — nothing to fall back to
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 404
    assert de_client.post(
        "/api/returns/mark-uploaded", json={"ids": [row["id"]]}
    ).status_code == 409


def _forget_po(dbs, awb_id):
    import asyncio

    async def go():
        await dbs.execute("UPDATE return_parcel SET po_number = NULL WHERE original_awb_id = ?",
                          (awb_id,))

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(go())


def test_superadmin_can_fill_in_a_missing_po_by_hand(client, de_client, dbs, rejected):
    """The way a stuck legacy row gets unstuck — one row, one person, logged.

    Without a PO there is no `requested_tracking_number` to issue, so the row sits on
    Pending DE upload forever. Somebody has to be able to answer for it; the answer is a
    reconstruction of a fact nobody recorded, so it is the superadmin who signs for it.
    """
    _forget_po(dbs, rejected["awb_id"])
    rid = _row(de_client)["id"]

    # DE holds the lane but not this — it is not a step in their daily work.
    assert de_client.post(
        "/api/returns/po", json={"id": rid, "po_number": "PO-BBB"}
    ).status_code == 403

    client.post("/api/auth/dev-login", json={"email": "admin@ninjavan.co"})
    # The picker offers the forward order's own PO lines — the same list the courier saw.
    stuck = _row(client)
    assert [p["po_number"] for p in stuck["po_options"]] == ["PO-AAA", "PO-BBB"]

    r = client.post("/api/returns/po", json={"id": rid, "po_number": "PO-BBB"})
    assert r.status_code == 200, r.text
    fixed = _row(client)
    assert fixed["po_number"] == "PO-BBB"
    assert fixed["po_unknown"] is False
    assert fixed["po_options"] == []  # nothing left to choose

    # Unstuck: it exports, with the tracking number built from the forward AWB.
    assert _oc_rows(client.get("/api/returns/export-oc.xlsx"))[0][
        "requested_tracking_number"] == f"{rejected['awb_id']}-R"


def test_filling_a_po_in_by_hand_is_bounded_and_logged(client, dbs, rejected):
    """Two limits, both deliberate: only a real PO on that AWB, and only into a gap."""
    import asyncio

    client.post("/api/auth/dev-login", json={"email": "admin@ninjavan.co"})
    rid = _row(client)["id"]

    # The courier already answered — a fact from the door is not overwritten from a desk.
    assert client.post(
        "/api/returns/po", json={"id": rid, "po_number": "PO-BBB"}
    ).status_code == 409

    _forget_po(dbs, rejected["awb_id"])
    # Free-typed values would mint a number for an order that does not exist.
    assert client.post(
        "/api/returns/po", json={"id": rid, "po_number": "PO-INVENTED"}
    ).status_code == 422
    assert _row(client)["po_unknown"] is True

    client.post("/api/returns/po", json={"id": rid, "po_number": "PO-AAA"})

    async def entries():
        return await dbs.fetch_all(
            "SELECT actor, entity_id FROM audit_log WHERE action = 'return_po_set_by_hand'", ()
        )

    log = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(entries())
    assert len(log) == 1
    assert log[0]["actor"] == "admin@ninjavan.co"
    assert "PO-AAA" in log[0]["entity_id"]


def test_a_full_refusal_has_no_po_to_fill(client, fully_rejected):  # noqa: ARG001
    """`semua` produces no OC row, so there is no field and no gap."""
    client.post("/api/auth/dev-login", json={"email": "admin@ninjavan.co"})
    rid = _row(client)["id"]
    assert client.post(
        "/api/returns/po", json={"id": rid, "po_number": "PO-AAA"}
    ).status_code == 409


def test_a_legacy_row_on_a_single_po_awb_needs_no_choice(de_client, dbs, rejected):
    """One PO line means there is nothing to choose — that is derivation, not a guess."""
    import asyncio

    async def one_po():
        await dbs.execute("UPDATE return_parcel SET po_number = NULL WHERE original_awb_id = ?",
                          (rejected["awb_id"],))
        await dbs.execute("DELETE FROM po_line WHERE awb_id = ? AND po_number = 'PO-BBB'",
                          (rejected["awb_id"],))

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(one_po())

    row = _row(de_client)
    assert row["po_number"] == "PO-AAA"
    assert row["po_unknown"] is False
    assert _oc_rows(de_client.get("/api/returns/export-oc.xlsx"))[0][
        "requested_tracking_number"] == f"{rejected['awb_id']}-R"


async def _strip(dbs, awb_id):
    await dbs.execute("UPDATE awb SET origin = NULL WHERE awb_id = ?", (awb_id,))
    await dbs.execute("UPDATE return_parcel SET origin = NULL WHERE original_awb_id = ?", (awb_id,))


def test_origin_unknown_blocks_the_oc_export_until_bulk_set(de_client, dbs, rejected):
    """DE's first move: set the OC origin on rows whose forward order never recorded one.

    The export SKIPS these rather than guessing, so clearing them is what puts the row in
    the file at all.
    """
    import asyncio

    rid = _row(de_client)["id"]
    # Strip the origin from both the row and its forward AWB — the pre-tracking case.
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        _strip(dbs, rejected["awb_id"])
    )
    r = _row(de_client)
    assert r["origin_unknown"] is True
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 404
    assert de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).status_code == 409

    assert de_client.post(
        "/api/returns/origin", json={"ids": [rid], "origin": "TMP_SURABAYA"}
    ).json()["updated"] == 1
    assert _row(de_client)["origin_unknown"] is False
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 200


# ------------------------------------------------------- semua: RTS pipeline --
def test_full_refusal_closes_by_rts_and_never_prints(de_client, fully_rejected):
    rid = _row(de_client)["id"]
    assert _row(de_client)["closes_by"] == "rts"

    # The full refusal never appears in the OC export — no new AWB exists for it.
    assert de_client.get("/api/returns/export-oc.xlsx").status_code == 404
    # And the print path refuses it outright.
    assert de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]}).json()["updated"] == 0

    csv_text = de_client.get("/api/returns/export-rts.csv").text
    assert fully_rejected["awb_id"] in csv_text and ",no" in csv_text

    assert de_client.post("/api/returns/rts", json={"ids": [rid]}).json()["updated"] == 1
    r = _row(de_client)
    assert r["stage"] == "rts_triggered"
    assert r["return_awb_id"] is None  # the whole point: no second tracking number
    # Still exportable, now flagged as marked — the list matches what was just done.
    assert ",yes" in de_client.get("/api/returns/export-rts.csv").text
    # Marking twice is a no-op.
    assert de_client.post("/api/returns/rts", json={"ids": [rid]}).json()["updated"] == 0


def test_partial_rejects_are_invisible_to_the_rts_path(de_client, rejected):  # noqa: ARG001
    rid = _row(de_client)["id"]
    assert de_client.post("/api/returns/rts", json={"ids": [rid]}).json()["updated"] == 0
    assert de_client.get("/api/returns/export-rts.csv").status_code == 404


# ------------------------------------------------------------------ misc ------
def test_stage_filter_and_bad_stage(de_client, rejected):  # noqa: ARG001
    rows = de_client.get("/api/returns?stage=pending_de_upload").json()["returns"]
    assert len(rows) == 1
    assert de_client.get("/api/returns?stage=pending_ack").status_code == 400


def test_csv_export_carries_the_full_trail(de_client, rejected):
    rid = _row(de_client)["id"]
    de_client.post("/api/returns/mark-uploaded", json={"ids": [rid]})
    text = de_client.get("/api/returns/export.csv").text
    assert f"{rejected['awb_id']}-R" in text
    assert PO in text  # the PO itself, so the trail says which one came back
    assert "pending_print" in text
    # The validator columns survive as history for rows stamped under the old flow.
    assert "legacy_validated_at" in text

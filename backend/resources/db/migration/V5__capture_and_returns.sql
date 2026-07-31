-- V5 — courier capture (M2) + the reject-return worklist (Lane 3 of SCOPE_V3_MVP.md).
-- OceanBase / MySQL dialect. Additive over V2/V4; no table is dropped.

-- ---- awb: courier submission outcome + link lifetime -----------------------
-- The 30-day courier-link window (PRD §10, LOCKED) is derived from created_at rather
-- than stored, so it can never drift from the row it belongs to. Only the terminal
-- outcome needs persisting.
ALTER TABLE awb
    ADD COLUMN fail_reason      VARCHAR(24) NULL,   -- set when status = delivery_failed
    ADD COLUMN submitted_by_ip  VARCHAR(45) NULL;   -- courier links are unauthenticated; keep a trace

-- ---- failed_delivery: adopt the LOCKED 9-code reason list ------------------
-- The V2 comment listed a pre-lock draft set. Codes (PRD §7.2.1, locked 09 Jul):
--   cancelled | not_ordered | address_wrong | moved | no_receiver
--   reschedule | office_closed | force_majeure | refused_sign
-- The V3 dummy row used the draft code 'closed'; remap it so the seed stays valid.
UPDATE failed_delivery SET fail_reason = 'office_closed' WHERE fail_reason = 'closed';
UPDATE failed_delivery SET fail_reason = 'no_receiver'   WHERE fail_reason = 'not_found';
UPDATE failed_delivery SET fail_reason = 'refused_sign'  WHERE fail_reason = 'refused';

-- ---- return_parcel: reject-return worklist ---------------------------------
-- Round 5 removed PDF-label printing, so awb_pdf_ref / awb_created are dead. They are
-- KEPT (not dropped) because V3__seed_dummy.sql still writes them and replaying the
-- migration set must stay green. New work uses the columns below.
--
-- Lane 3 flow: courier reject → row appears (pending_ack) → ops ticks acknowledge →
-- ops pastes the replacement TIDs minted on the RTS account 11398434 → row closes.
ALTER TABLE return_parcel
    ADD COLUMN return_type       VARCHAR(12)  NOT NULL DEFAULT 'sebagian', -- sebagian|semua
    ADD COLUMN acknowledged_at   DATETIME     NULL,
    ADD COLUMN acknowledged_by   BIGINT       NULL,
    ADD COLUMN return_tids       TEXT         NULL,   -- operator-entered; comma/newline separated
    ADD COLUMN tids_sent_at      DATETIME     NULL,
    ADD COLUMN tids_sent_by      BIGINT       NULL,
    ADD KEY ix_return_ack (acknowledged_at),
    ADD KEY ix_return_sent (tids_sent_at);

-- Carry the V3 dummy row forward: it already had a return AWB marked created, which is
-- the old spelling of "TIDs sent".
UPDATE return_parcel
   SET return_tids  = return_awb_id,
       tids_sent_at = COALESCE(updated_at, created_at)
 WHERE awb_created = 1 AND return_awb_id IS NOT NULL;

-- Mirror the reject type recorded on the forward AWB.
UPDATE return_parcel rp
  JOIN awb a ON a.awb_id = rp.original_awb_id
   SET rp.return_type = a.return_type
 WHERE a.return_type IN ('sebagian', 'semua');

-- ---- document_capture: guard against duplicate single-shot documents -------
-- sp_manual repeats per PO and the reject set allows two DN shots, so this is a
-- partial index on the doc types that must appear at most once per AWB. Enforced in
-- application code (oc/courier.py) rather than by constraint, since the rule differs
-- per doc_type; the index keeps the lookup cheap.
ALTER TABLE document_capture
    ADD KEY ix_doc_awb_type (awb_id, doc_type);

-- M1 — OC intake & courier links. OceanBase / MySQL dialect. Additive over V2/V3.
-- Reflects the 07-Jul rulings (BUILD_HANDOFF §3.6): per-AWB MPS (base=SwipeAWB),
-- sp_type no longer captured at intake (rider reads the Faktur), hub is NV-assigned
-- (not derived here), and the courier link is scoped per AWB (awb.link_token → /c/<token>).

-- ---- order_intake: batch summary + generated-file refs -----------------------
ALTER TABLE order_intake
    ADD COLUMN service_code    VARCHAR(4)  NULL AFTER shipper_service_id,  -- S1|S2|S3 chosen at upload
    ADD COLUMN awb_count       INT         NOT NULL DEFAULT 0,
    ADD COLUMN piece_count     INT         NOT NULL DEFAULT 0,             -- MPS TRID pieces
    ADD COLUMN links_file_ref  CHAR(36)    NULL,                          -- generated links.csv blob
    ADD COLUMN warning_summary TEXT        NULL;
-- oc_template_ref (already present) now holds the generated NV upload .xlsx blob.

-- ---- awb: fields needed to rebuild the upload + back the courier route --------
ALTER TABLE awb
    ADD COLUMN merchant_order_number VARCHAR(40)  NULL AFTER awb_id,   -- SwipeAWB (fwd) / PO number (return)
    ADD COLUMN phone                 VARCHAR(40)  NULL,
    ADD COLUMN postcode              VARCHAR(12)  NULL,
    ADD COLUMN weight                VARCHAR(16)  NULL,                 -- kept as text to preserve source formatting
    ADD COLUMN is_return             TINYINT(1)   NOT NULL DEFAULT 0,
    ADD COLUMN invoice               VARCHAR(80)  NULL,                 -- return only (Validator invoice-mismatch check)
    ADD COLUMN item_detail           TEXT         NULL,                 -- return item list shown behind the courier link
    ADD COLUMN delivery_instructions TEXT         NULL;                 -- col-R text incl. injected link (audit/courier display)

-- ---- po_line: sp_type is no longer captured at intake (rider reads Faktur) ----
-- Keep the column for back-compat with the V3 seed; make it optional going forward.
ALTER TABLE po_line
    MODIFY COLUMN sp_type VARCHAR(12) NULL;

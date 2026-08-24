-- V9 — origin tracking, driver identity, and the reject-return stage model (19 Aug 2026)
--
-- Four changes, all driven by the 19 Aug process review:
--
-- 1. ORIGIN. A delivery ships out of TMP Depok or TMP Surabaya. Until now nothing recorded
--    which, so when a partial return came back the DE had to look the forward TRID up by hand
--    to work out where to send it — the manual step this whole lane exists to remove. The
--    origin is now chosen at Order creation and stamped on every AWB in the batch, so a return
--    reads it straight off its own forward order. It fills cols J-Q (the `to.*` block) of the
--    return OC row, so a wrong value sends the parcel to the wrong city.
--
-- 2. DRIVER IDENTITY. The courier now states who they are and which hub they belong to before
--    capturing anything. Hub is picked from `hub` below, never typed free-hand, so the IC can
--    filter their worklist by it and it always matches.
--
-- 3. REJECT PIECE COUNT. The driver enters how many pieces came back (a count only — there is
--    no way to collect item names at the door). It lands in the return OC's item_description
--    and is what the final pre-handover check is reconciled against, alongside the goods photo
--    and the notes on the BA Retur.
--
-- 4. STAGES. pending_validator -> pending_de_upload -> pending_print -> printed. Both reject
--    types are validated; only `sebagian` reaches print, because `semua` travels back on its
--    original label. Stages are DERIVED from these timestamps, never stored as a string, so a
--    row can never claim a stage its own history does not support.
--
-- Every column is NULL-able and every existing row keeps working: an AWB with no origin simply
-- reports "origin unknown" and is fixed in bulk from the worklist.

-- ---- 1. origin -------------------------------------------------------------
ALTER TABLE order_intake ADD COLUMN origin VARCHAR(24) NULL;
ALTER TABLE awb          ADD COLUMN origin VARCHAR(24) NULL;
CREATE INDEX ix_awb_origin ON awb (origin);

-- ---- 2. driver identity ----------------------------------------------------
ALTER TABLE awb ADD COLUMN driver_id VARCHAR(32) NULL;
ALTER TABLE awb ADD COLUMN hub_name  VARCHAR(32) NULL;
CREATE INDEX ix_awb_hub_name ON awb (hub_name);

-- Hub master. Codes look like XXX-XXX or XXX-XXX-XX (e.g. MAC-KD5). `origin` is the FALLBACK
-- used when a return cannot be matched to its forward order; `active=0` hides a hub from the
-- driver's dropdown without deleting history.
CREATE TABLE hub (
    hub_name   VARCHAR(32)  NOT NULL,
    hub_label  VARCHAR(120) NULL,
    origin     VARCHAR(24)  NULL,
    active     TINYINT(1)   NOT NULL DEFAULT 1,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (hub_name),
    KEY ix_hub_active (active)
) DEFAULT CHARSET=utf8mb4;

-- ---- 3 + 4. reject count and the new stages --------------------------------
ALTER TABLE return_parcel ADD COLUMN reject_pcs      INT      NULL;
ALTER TABLE return_parcel ADD COLUMN validated_at    DATETIME NULL;
ALTER TABLE return_parcel ADD COLUMN validated_by    BIGINT   NULL;
ALTER TABLE return_parcel ADD COLUMN de_uploaded_at  DATETIME NULL;
ALTER TABLE return_parcel ADD COLUMN de_uploaded_by  BIGINT   NULL;
ALTER TABLE return_parcel ADD COLUMN printed_at      DATETIME NULL;
ALTER TABLE return_parcel ADD COLUMN printed_by      BIGINT   NULL;
ALTER TABLE return_parcel ADD COLUMN origin          VARCHAR(24) NULL;

CREATE INDEX ix_return_validated ON return_parcel (validated_at);
CREATE INDEX ix_return_printed   ON return_parcel (printed_at);

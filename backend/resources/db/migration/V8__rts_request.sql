-- V8 — RTS request for a full reject (19 Aug 2026)
--
-- When an apotek refuses the WHOLE delivery there is no point minting a fresh return TID:
-- the forward tracking number already exists and Ninja can simply be asked to trigger RTS
-- on it. Creating a second TID duplicated the parcel in NV's system and split its history
-- across two identifiers, which is what ops flagged on the 10 Aug walkthrough (deck slide 7).
--
-- So a `semua` row now closes by RECORDING AN RTS REQUEST instead of by pasting return TIDs.
-- `sebagian` is unchanged — a partial return still needs its own return TID, because only
-- part of the consignment travels back.
--
-- Existing rows are untouched: both columns are NULL, so every current row keeps whatever
-- stage it already had.
ALTER TABLE return_parcel
    ADD COLUMN rts_requested_at DATETIME NULL,
    ADD COLUMN rts_requested_by BIGINT   NULL;

CREATE INDEX ix_return_rts ON return_parcel (rts_requested_at);

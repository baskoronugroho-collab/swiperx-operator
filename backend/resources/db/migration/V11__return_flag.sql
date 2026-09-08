-- V11 — Station IC's "can't find this AWB in NV" flag (8 Sep 2026)
--
-- The gap this closes. A partial return moves to Pending Print once DE marks the OC uploaded,
-- and Station IC then searches the `-R01` in OPV2 to print the label. Sometimes it is not
-- there: DE pressed Mark OC uploaded without ever exporting the CSV, so nothing reached Ninja
-- and the tracking number was never issued. The IC had no way to say so inside the app — the
-- parcel sat on the bench and the news travelled by chat group, if at all.
--
-- So the IC now attaches a REMARK to the row instead. It is a note, not a stage: raising it
-- moves nothing and closes nothing. It exists so the row shows up on DE's screen with the
-- reason written on it, because only DE (or implant / program_manager) can send the row back
-- to Pending DE upload and re-run the export.
--
-- One flag per row, overwritten by the next one — the trail of who raised what and when lives
-- in `audit_log` (`return_flagged` / `return_unflagged`), which is never rewritten. The flag
-- clears when the row is sent back or when DE clears it by hand.
--
-- All three columns are NULL-able, so every existing row keeps working: no flag, no change.
ALTER TABLE return_parcel
    ADD COLUMN flag_note  VARCHAR(500) NULL,
    ADD COLUMN flagged_at DATETIME     NULL,
    ADD COLUMN flagged_by BIGINT       NULL;

CREATE INDEX ix_return_flagged ON return_parcel (flagged_at);

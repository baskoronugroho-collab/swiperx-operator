-- V15 — Vasil page: "unable to upload" status + Vasil-only photo fixes
--
-- Still separate from the reject-returns lane: nothing here touches `return_parcel` or
-- `document_capture`.
--
-- 1. `vasil_migration.status` gains a fourth value, 'unable' (VARCHAR(8) already fits),
--    with the reasons as a comma list of: dn, item, sp_manual.
-- 2. `vasil_photo` holds fixes made on the Vasil page only. A row with `photo_ref` is a
--    replacement photo uploaded here; a row with `original_capture_id` (and no photo_ref)
--    is a marker that hides one courier photo from the Vasil view. The courier's original
--    in `document_capture` is never changed or deleted.
ALTER TABLE vasil_migration ADD COLUMN unable_reasons VARCHAR(80) NULL;

CREATE TABLE vasil_photo (
    id                  BIGINT      NOT NULL AUTO_INCREMENT,
    return_parcel_id    BIGINT      NOT NULL,
    doc_type            VARCHAR(24) NOT NULL,
    po_number           VARCHAR(40) NULL,
    photo_ref           CHAR(36)    NULL,
    original_capture_id BIGINT      NULL,
    created_by          BIGINT      NULL,
    created_at          TIMESTAMP   NULL,
    removed_at          TIMESTAMP   NULL,
    removed_by          BIGINT      NULL,
    PRIMARY KEY (id),
    KEY ix_vasil_photo_return (return_parcel_id)
);

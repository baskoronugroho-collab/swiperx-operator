-- V14 — "Migrate to Vasil Operator" tracking (separate process, touches nothing else)
--
-- One row per reject return the Vasil migration page has been used on. No row means the
-- AWB is still pending. The row lives in its OWN table on purpose: marking an AWB done,
-- moving it back, or hiding it here must never change `return_parcel` or any stage on the
-- reject-returns lane.
--
--   pending  -> default, also what "Move to pending" returns to
--   done     -> ticked as uploaded to Vasil Operator
--   hidden   -> removed from the Vasil page only (never deleted from return_parcel)
CREATE TABLE vasil_migration (
    return_parcel_id BIGINT      NOT NULL,
    status           VARCHAR(8)  NOT NULL DEFAULT 'pending',
    done_at          TIMESTAMP   NULL,
    done_by          BIGINT      NULL,
    hidden_at        TIMESTAMP   NULL,
    hidden_by        BIGINT      NULL,
    updated_at       TIMESTAMP   NULL,
    PRIMARY KEY (return_parcel_id),
    KEY ix_vasil_migration_status (status)
);

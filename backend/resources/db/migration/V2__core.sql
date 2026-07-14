-- SwipeRx Operator core schema (Alpha 0.1). OceanBase / MySQL dialect.
-- Reflects the 03-Jul decision ledger (see BUILD_HANDOFF.md §3):
--   * reject = flag + proof only  → NO reject_line table; awb.return_type carries partial/full
--   * signed+stamped attestation  → document_capture.signed_stamped
--   * reprint tracking dropped     → return_parcel has NO printed/labelled columns
--   * multi-role accounts          → user_roles is many-to-one on users
--   * stopgap object storage       → media_blob holds bytes; keys used as *_ref everywhere

-- ---- Users & roles ---------------------------------------------------------
CREATE TABLE users (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    name         VARCHAR(120) NOT NULL,
    google_email VARCHAR(255) NOT NULL,
    active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (google_email)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE user_roles (
    id       BIGINT      NOT NULL AUTO_INCREMENT,
    user_id  BIGINT      NOT NULL,
    role     VARCHAR(32) NOT NULL,  -- superadmin|program_manager|de|implant|station_ic|validator|swiperx
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_role (user_id, role),
    KEY ix_user_roles_user (user_id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Media (stopgap: BLOB in-DB behind the storage adapter) -----------------
CREATE TABLE media_blob (
    id           CHAR(36)     NOT NULL,           -- uuid4; used as the *_ref value
    content_type VARCHAR(100) NOT NULL,
    byte_size    INT          NOT NULL,
    data         LONGBLOB     NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Order intake ----------------------------------------------------------
CREATE TABLE order_intake (
    id                 BIGINT       NOT NULL AUTO_INCREMENT,
    source_file_ref    CHAR(36)     NULL,
    oc_template_ref    CHAR(36)     NULL,
    shipper_service_id VARCHAR(20)  NULL,          -- chosen at upload (11398224/11549046/11398423)
    uploaded_by        BIGINT       NULL,
    uploaded_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_count          INT          NOT NULL DEFAULT 0,
    status             VARCHAR(24)  NOT NULL DEFAULT 'uploaded',
    error_summary      TEXT         NULL,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

-- ---- AWB + PO lines --------------------------------------------------------
CREATE TABLE awb (
    awb_id              VARCHAR(32)  NOT NULL,
    service_id          VARCHAR(20)  NOT NULL,
    pharmacy_id         VARCHAR(40)  NULL,
    pharmacy_name       VARCHAR(200) NOT NULL,
    address             VARCHAR(400) NULL,
    city                VARCHAR(120) NULL,          -- L2 (kota/kabupaten) — report grouping
    hub_code            VARCHAR(40)  NULL,
    destination_area    VARCHAR(120) NULL,
    koli                INT          NOT NULL DEFAULT 0,
    link_token          VARCHAR(64)  NOT NULL,      -- unguessable; not derived from awb_id
    status              VARCHAR(24)  NOT NULL DEFAULT 'created', -- created|delivered|arrived|handed_over|delivery_failed
    return_type         VARCHAR(12)  NOT NULL DEFAULT 'none',    -- none|sebagian|semua
    created_by          BIGINT       NULL,
    intake_id           BIGINT       NULL,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at        DATETIME     NULL,
    driver_submitted_at DATETIME     NULL,
    PRIMARY KEY (awb_id),
    UNIQUE KEY uq_awb_token (link_token),
    KEY ix_awb_status (status),
    KEY ix_awb_hub (hub_code),
    KEY ix_awb_service (service_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE po_line (
    id        BIGINT      NOT NULL AUTO_INCREMENT,
    awb_id    VARCHAR(32) NOT NULL,
    po_number VARCHAR(40) NOT NULL,
    koli      INT         NOT NULL DEFAULT 0,       -- collies (<=~10 per PO), NOT "units"
    sp_type   VARCHAR(12) NOT NULL,                 -- manual|electronic
    PRIMARY KEY (id),
    KEY ix_po_awb (awb_id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Courier capture -------------------------------------------------------
CREATE TABLE document_capture (
    id            BIGINT      NOT NULL AUTO_INCREMENT,
    awb_id        VARCHAR(32) NOT NULL,
    doc_type      VARCHAR(24) NOT NULL,  -- pharmacy_pod|receiver_pod|delivery_note|sp_manual|rejected_goods|awb_sticker|return_form
    po_number     VARCHAR(40) NULL,      -- set for sp_manual (which PO)
    photo_ref     CHAR(36)    NOT NULL,
    signed_stamped TINYINT(1) NULL,      -- attestation on delivery_note / return_form (NULL if N/A)
    captured_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    gps           VARCHAR(60) NULL,
    PRIMARY KEY (id),
    KEY ix_doc_awb (awb_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE failed_delivery (
    id               BIGINT      NOT NULL AUTO_INCREMENT,
    awb_id           VARCHAR(32) NOT NULL,
    fail_reason      VARCHAR(24) NOT NULL, -- closed|reschedule|refused|not_found|no_receiver|access_blocked|other
    reason_note      TEXT        NULL,
    proof_photo_ref  CHAR(36)    NOT NULL,
    proof_timestamp  DATETIME    NOT NULL,
    timestamp_source VARCHAR(10) NOT NULL, -- camera|exif
    gps              VARCHAR(60) NULL,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_fail_awb (awb_id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Return AWB (back office; NO print/label tracking) ---------------------
CREATE TABLE return_parcel (
    id              BIGINT      NOT NULL AUTO_INCREMENT,
    original_awb_id VARCHAR(32) NOT NULL,
    return_awb_id   VARCHAR(40) NULL,      -- created in NV's system
    awb_pdf_ref     CHAR(36)    NULL,      -- PDF sticker uploaded by DE
    awb_created     TINYINT(1)  NOT NULL DEFAULT 0,  -- DE marked "created in NV"
    created_by      BIGINT      NULL,
    hub_code        VARCHAR(40) NULL,
    service_id      VARCHAR(20) NULL,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    NULL,
    PRIMARY KEY (id),
    KEY ix_return_awb (original_awb_id),
    KEY ix_return_hub (hub_code)
) DEFAULT CHARSET=utf8mb4;

-- ---- Arrival scan & handover ----------------------------------------------
CREATE TABLE arrival_scan (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    awb_id     VARCHAR(32) NOT NULL,
    scanned_by BIGINT      NULL,
    scanned_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_arrival_awb (awb_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE handover_session (
    id               BIGINT     NOT NULL AUTO_INCREMENT,
    created_by       BIGINT     NULL,
    created_at       DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    handed_over      TINYINT(1) NOT NULL DEFAULT 0,
    handed_over_at   DATETIME   NULL,
    handover_rejected TINYINT(1) NOT NULL DEFAULT 0,
    rejection_note   TEXT       NULL,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE handover_item (
    id                  BIGINT      NOT NULL AUTO_INCREMENT,
    handover_session_id BIGINT      NOT NULL,
    awb_id              VARCHAR(32) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_hitem_session (handover_session_id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Validation (non-blocking; coded multi-select reasons) -----------------
CREATE TABLE validation_flag (
    id           BIGINT      NOT NULL AUTO_INCREMENT,
    awb_id       VARCHAR(32) NOT NULL,
    validated_by BIGINT      NULL,
    result       VARCHAR(10) NOT NULL, -- valid|invalid
    validated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_valid_awb (awb_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE validation_reason (
    id                 BIGINT      NOT NULL AUTO_INCREMENT,
    validation_flag_id BIGINT      NOT NULL,
    reason_code        VARCHAR(40) NOT NULL,
    -- dn_missing_unsigned | return_form_missing_unsigned | sp_manual_missing | invoice_mismatch
    PRIMARY KEY (id),
    KEY ix_reason_flag (validation_flag_id)
) DEFAULT CHARSET=utf8mb4;

-- ---- Hub distribution, notifications, audit, version -----------------------
CREATE TABLE hub_contact (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    hub_code    VARCHAR(40)  NOT NULL,
    email       VARCHAR(255) NOT NULL,
    name        VARCHAR(120) NULL,
    notify_role VARCHAR(12)  NOT NULL DEFAULT 'notify', -- action|notify
    active      TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    KEY ix_hub_contact_hub (hub_code)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE notification (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    recipient  VARCHAR(255) NOT NULL,
    hub_code   VARCHAR(40) NULL,
    type       VARCHAR(40) NOT NULL, -- return_to_print | ...
    awb_id     VARCHAR(32) NULL,
    channel    VARCHAR(12) NOT NULL DEFAULT 'email',
    sent_at    DATETIME    NULL,
    read_at    DATETIME    NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE audit_log (
    id        BIGINT      NOT NULL AUTO_INCREMENT,
    actor     VARCHAR(255) NULL,
    action    VARCHAR(80) NOT NULL,
    entity    VARCHAR(40) NULL,
    entity_id VARCHAR(64) NULL,
    created_at DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE app_version (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    version     VARCHAR(20)  NOT NULL,
    notes       TEXT         NOT NULL,
    released_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4;

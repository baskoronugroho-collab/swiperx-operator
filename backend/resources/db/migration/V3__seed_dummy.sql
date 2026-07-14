-- Dummy seed for Alpha 0.1 (PUBLIC PORTAL — no real pharmacy data).
-- Gives every role data on first run and exercises the multi-role model.
-- Replace/clear before moving to the NV self-hosted portal.

INSERT INTO users (id, name, google_email, active) VALUES
 (1, 'Rahmat A.', 'rahmat@ninjavan.co', 1),
 (2, 'Sari P.',   'sari.p@ninjavan.co', 1),
 (3, 'Dewi K.',   'dewi.k@ninjavan.co', 1),
 (4, 'Agus S.',   'agus.s@ninjavan.co', 1),
 (5, 'Lina W.',   'lina.w@ninjavan.co', 1);

-- Note: user 3 is DE + Implant, user 5 is Validator + Implant → multi-role demo.
INSERT INTO user_roles (user_id, role) VALUES
 (1, 'superadmin'),
 (2, 'program_manager'),
 (3, 'de'), (3, 'implant'),
 (4, 'station_ic'),
 (5, 'validator'), (5, 'implant');

INSERT INTO awb (awb_id, service_id, pharmacy_name, address, city, hub_code, koli, link_token, status, return_type, created_by, created_at, delivered_at, driver_submitted_at) VALUES
 ('NVIDMY0089241','11549046','Apotek Sehat Sentosa','Jl. Melati Raya No. 12, Cakung','Jakarta Timur','JKT-CKG',3,'tok_demo_sentosa_9241','handed_over','none',3,'2026-07-02 08:00:00','2026-07-02 13:24:00','2026-07-02 13:24:00'),
 ('NVIDMY0089242','11398224','Apotek Medika Jaya','Jl. Asia Afrika No. 8, Bandung','Kota Bandung','BDG-KRC',2,'tok_demo_medika_9242','delivered','none',3,'2026-07-02 08:05:00','2026-07-02 12:10:00','2026-07-02 12:10:00'),
 ('NVIDMY0089243','11549046','Apotek Prima Husada','Jl. Kenanga No. 21, Cakung','Jakarta Timur','JKT-CKG',4,'tok_demo_prima_9243','delivered','sebagian',3,'2026-07-02 08:10:00','2026-07-02 13:31:00','2026-07-02 13:31:00'),
 ('NVIDMY0089244','11549046','Apotek Kimia Sehat','Jl. Rungkut Industri No. 3, Surabaya','Kota Surabaya','SBY-RGK',2,'tok_demo_kimia_9244','delivery_failed','none',3,'2026-07-01 08:00:00',NULL,'2026-07-01 09:10:00'),
 ('NVIDMY0089245','11398224','Apotek Sumber Waras','Jl. Mawar No. 5, Cakung','Jakarta Timur','JKT-CKG',1,'tok_demo_sumber_9245','arrived','none',3,'2026-07-01 08:15:00','2026-07-01 11:40:00','2026-07-01 11:40:00'),
 ('NVIDMY0089246','11398224','Apotek Bahagia Farma','Jl. Dago No. 44, Bandung','Kota Bandung','BDG-KRC',3,'tok_demo_bahagia_9246','delivered','semua',3,'2026-07-01 08:20:00','2026-07-01 14:02:00','2026-07-01 14:02:00');

INSERT INTO po_line (awb_id, po_number, koli, sp_type) VALUES
 ('NVIDMY0089241','PO-2401',1,'manual'),
 ('NVIDMY0089241','PO-2402',1,'electronic'),
 ('NVIDMY0089241','PO-2403',1,'manual'),
 ('NVIDMY0089243','PO-2411',2,'manual'),
 ('NVIDMY0089243','PO-2412',2,'electronic'),
 ('NVIDMY0089246','PO-2421',1,'manual'),
 ('NVIDMY0089246','PO-2422',2,'manual');

-- One return awaiting the NV AWB, one already created.
INSERT INTO return_parcel (original_awb_id, return_awb_id, awb_created, created_by, hub_code, service_id, created_at) VALUES
 ('NVIDMY0089243', NULL, 0, 3, 'JKT-CKG', '11549046', '2026-07-02 13:40:00'),
 ('NVIDMY0089246', 'RTS-77120043', 1, 3, 'BDG-KRC', '11398224', '2026-07-01 15:00:00');

INSERT INTO failed_delivery (awb_id, fail_reason, reason_note, proof_photo_ref, proof_timestamp, timestamp_source, created_at) VALUES
 ('NVIDMY0089244','closed','Pharmacy shutter down on arrival','00000000-0000-0000-0000-000000000001','2026-07-01 09:10:00','camera','2026-07-01 09:11:00');

-- One validated (valid) and one invalid with two coded reasons.
INSERT INTO validation_flag (id, awb_id, validated_by, result, validated_at) VALUES
 (1,'NVIDMY0089241',5,'valid','2026-07-02 15:00:00'),
 (2,'NVIDMY0089243',5,'invalid','2026-07-02 15:05:00');
INSERT INTO validation_reason (validation_flag_id, reason_code) VALUES
 (2,'return_form_missing_unsigned'),
 (2,'invoice_mismatch');

INSERT INTO hub_contact (hub_code, email, name, notify_role, active) VALUES
 ('JKT-CKG','ic.cakung@ninjavan.co','Agus S.','action',1),
 ('JKT-CKG','spv.cakung@ninjavan.co','Cakung SPV','notify',1),
 ('BDG-KRC','ic.kircon@ninjavan.co','Kircon IC','action',1),
 ('SBY-RGK','ic.rungkut@ninjavan.co','Rungkut IC','action',1);

INSERT INTO app_version (version, notes, released_at) VALUES
 ('Alpha 0.1', 'First production foundation: Google SSO + multi-role accounts, OceanBase schema, stopgap in-DB media storage. Courier capture, OC intake, returns, handover, validation, and reporting land in following milestones.', '2026-07-03 00:00:00');

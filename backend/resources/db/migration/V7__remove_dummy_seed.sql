-- V7 — strip the Alpha-0.1 dummy seed (26 Jul 2026).
--
-- The app is going into real use, so the fake pharmacies, fake staff accounts and fake
-- rejects from V3__seed_dummy.sql must not be present. Every screen now starts empty and
-- fills from real Order creation.
--
-- Why a NEW migration instead of editing V3: Flyway fingerprints each file it has already
-- run. Editing V3 in place is what produced the "Migration checksum mismatch" that blocked
-- the 26 Jul deploys. Historical migrations are append-only — always add, never rewrite.
--
-- KEPT deliberately: the `app_version` row (the in-app changelog — product metadata, not
-- dummy data) and the real operator account added in V6.
--
-- Deletes are keyed to the exact seeded identifiers so a re-run is a no-op and nothing
-- created later can be caught by them.

-- ---- courier capture + validation attached to the dummy AWBs ----------------
DELETE FROM validation_reason
 WHERE validation_flag_id IN (
   SELECT id FROM (
     SELECT id FROM validation_flag
      WHERE awb_id LIKE 'NVIDMY00892%'
   ) AS f
 );

DELETE FROM validation_flag  WHERE awb_id LIKE 'NVIDMY00892%';
DELETE FROM failed_delivery  WHERE awb_id LIKE 'NVIDMY00892%';
DELETE FROM document_capture WHERE awb_id LIKE 'NVIDMY00892%';
DELETE FROM return_parcel    WHERE original_awb_id LIKE 'NVIDMY00892%';
DELETE FROM po_line          WHERE awb_id LIKE 'NVIDMY00892%';
DELETE FROM awb              WHERE awb_id LIKE 'NVIDMY00892%';

-- ---- dummy staff accounts ---------------------------------------------------
-- The real account (V6) is not in this list and survives.
DELETE FROM user_roles
 WHERE user_id IN (
   SELECT id FROM (
     SELECT id FROM users
      WHERE google_email IN (
        'rahmat@ninjavan.co', 'sari.p@ninjavan.co', 'dewi.k@ninjavan.co',
        'agus.s@ninjavan.co', 'lina.w@ninjavan.co'
      )
   ) AS u
 );

DELETE FROM users
 WHERE google_email IN (
   'rahmat@ninjavan.co', 'sari.p@ninjavan.co', 'dewi.k@ninjavan.co',
   'agus.s@ninjavan.co', 'lina.w@ninjavan.co'
 );

-- ---- placeholder hub distribution list --------------------------------------
-- Invented addresses for hubs that may not exist. The hub→email notification flow is
-- deferred (SCOPE_V3_MVP.md §4), so an empty table is the honest state.
DELETE FROM hub_contact
 WHERE email IN (
   'ic.cakung@ninjavan.co', 'spv.cakung@ninjavan.co',
   'ic.kircon@ninjavan.co', 'ic.rungkut@ninjavan.co'
 );

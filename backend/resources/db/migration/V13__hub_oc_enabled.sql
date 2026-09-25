-- V13 — the hub master becomes the ONE hub list, editable in the app (25 Sep 2026)
--
-- Until now there were two hub lists. The courier picker read this `hub` table; the Order
-- Creation dropdown read a hard-coded `hubs` array in backend/oc_config.json. Adding a hub
-- to Order Creation (SUB-GY5 was the first ask) therefore meant a code change, a deploy and
-- a production security review — for one row of data.
--
-- `oc_enabled` folds the second list into the first: a hub appears in the Order Creation
-- dropdown when it is active AND oc_enabled. Superadmin edits both flags (and the fallback
-- origin) on the Hubs page, with no deploy. The courier picker is unchanged: it still lists
-- every ACTIVE hub, whatever oc_enabled says.
--
-- The seven hubs below are exactly the oc_config.json list this replaces. They were all
-- seeded by V10, so the INSERT IGNORE is a guard, not a change: it only fires if a row has
-- somehow gone missing, and it would otherwise leave the dropdown empty after this deploy.
ALTER TABLE hub ADD COLUMN oc_enabled TINYINT(1) NOT NULL DEFAULT 0;

INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-UT5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-MA5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-KM5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-CB5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-KJ5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-KD5', 'TMP_DEPOK', 1);
INSERT IGNORE INTO hub (hub_name, origin, active) VALUES ('MAC-CP5', 'TMP_DEPOK', 1);

UPDATE hub SET oc_enabled = 1
 WHERE hub_name IN ('MAC-UT5', 'MAC-MA5', 'MAC-KM5', 'MAC-CB5', 'MAC-KJ5', 'MAC-KD5', 'MAC-CP5');

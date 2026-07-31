-- V6 — register the first real operator account (26 Jul 2026).
--
-- Both auth paths (`/api/auth/google/callback` and the dev-login stopgap) resolve the
-- signed-in email against `users`. An email with no row still gets a session, but with
-- roles = [] — which renders the "contact the Ninja Van team" screen and nothing else.
-- So SSO cannot be exercised end-to-end until a real account exists.
--
-- This registers the product owner as superadmin so every surface is reachable. It is
-- an ACCOUNT, not pharmacy data — the "dummy data only on the public portal" rule
-- (PRD §17) still stands for AWBs and photos.
--
-- Idempotent: safe if the row already exists.

-- NOTE: `FROM DUAL` is required — MySQL/OceanBase reject a WHERE clause on a SELECT
-- that has no FROM. Both tables carry a UNIQUE key on the target column
-- (uq_users_email, uq_user_role), so IGNORE keeps re-runs harmless either way.

INSERT IGNORE INTO users (name, google_email, active)
SELECT 'Baskoro Adi Nugroho', 'baskoro.nugroho@ninjavan.co', 1
  FROM DUAL
 WHERE NOT EXISTS (
   SELECT 1 FROM users WHERE google_email = 'baskoro.nugroho@ninjavan.co'
 );

INSERT IGNORE INTO user_roles (user_id, role)
SELECT u.id, 'superadmin'
  FROM users u
 WHERE u.google_email = 'baskoro.nugroho@ninjavan.co';

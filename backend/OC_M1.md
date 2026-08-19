# M1 — OC intake & courier links (backend)

Implements the TMP -> Ninja Van transform in FastAPI. (Originally ported from the `oc-engine/` Node
prototype, which was deleted 18 Aug 2026 once it went stale — this backend is now the only engine.) Reads a SwipeRx TMP `.xlsx`,
creates AWBs + PO lines with per-AWB courier tokens, stores the generated Ninja Van
upload `.xlsx` + `links.csv`, and resolves the courier link. No local Python on the
build machine — **verify at Substrait deploy time** (checklist below).

## Files
- `oc_engine.py` — pure transform (openpyxl read/write). **The authoritative engine.**
- `oc_config.json` — fixed config (no longer a synced copy; the Node original is gone).
- `oc.py` — routers: `/api/oc/*` (intake, staff) + `/api/c/*` (courier, public).
- `resources/db/migration/V4__oc.sql` — additive schema (order_intake summary + refs; awb OC fields; po_line.sp_type → nullable).

## Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/oc/services` | implant/de | List S1/S2/S3 (name, level, movement) |
| POST | `/api/oc/preview` | implant/de | Parse only (multipart: `service`, `file`) → AWBs + row errors, no writes |
| POST | `/api/oc/create` | implant/de | Commit: persist AWBs+tokens, generate upload.xlsx + links.csv |
| GET | `/api/oc/intakes` | implant/de | Recent intakes |
| GET | `/api/oc/intakes/{id}` | implant/de | Intake detail + AWBs (with courier_url) |
| GET | `/api/oc/intakes/{id}/upload.xlsx` | implant/de | Download the NV upload file |
| GET | `/api/oc/intakes/{id}/links.csv` | implant/de | Download the links file |
| GET | `/api/c/{token}` | public | **Courier link target** — HTML landing (M2 wizard replaces) |
| GET | `/api/c/{token}/order` | public | JSON order payload for the M2 SPA |

> Courier links are injected as `{PUBLIC_BASE_URL}/api/c/{token}` — under `/api` because
> that's the only path the Substrait ingress routes to the backend. When the M2 SPA lands,
> a frontend `/c/` route can call `/api/c/{token}/order`.

## Deploy smoke-test (run on the device with the Substrait plugin)
After deploy (Flyway applies V4; `DEV_LOGIN_ENABLED=true` for now):

1. **Health/migrate:** `GET /health` → `{"status":"ok"}`; app boots (V4 applied cleanly).
2. **Sign in:** `POST /api/auth/dev-login` with a registered implant/de email → session cookie.
3. **Services:** `GET /api/oc/services` → three services S1/S2/S3.
4. **Preview** (multipart `service=S1`, `file=` the real TMP) — expect the same counts the
   Node harness produced (identical rules):

   | Service | TMP sample | AWBs | pieces |
   |---|---|---|---|
   | S1 | `[Template Swipe Fwd Reg] …` | **57** | **144** |
   | S2 | `[Template Swipe FWD Sameday] …` | **79** | **210** |
   | S3 | `[Template Swipe PU Return] …` | **23** | **23** |

   Spot-check: S1 `AWB02S757` → 7 pieces; S2 `AWB02U24V` → 3.
5. **Create** (same multipart) → `201` with `intake_id`, `upload_url`, `links_url`.
6. **Download** `GET {upload_url}` — open the .xlsx: header row = NV field names; `global_shipper_id`=`11398423`;
   `corporate.branch_id`= 1/3/2 for S1/S2/S3; `parcel_job.delivery_instructions` wraps the link in
   `<updated_addr>…<a href="…/api/c/…">…</a></updated_addr>` and is ≤500 chars.
7. **Link opens (the M1 gate):** copy a `url` from `links.csv` (or `GET /api/oc/intakes/{id}`) and open it →
   the courier landing page shows the pharmacy + PO/koli (return: invoice + item detail). This is the
   prototype's dead link, now fixed.

## Not in M1 (later milestones)
Courier capture wizard (M2), returns/handover/validation (M3), PM/report (M4), and the
NV hub-assignment re-upload stage (§3.6). Real Google SSO needs the OAuth client (dev-login covers M1).

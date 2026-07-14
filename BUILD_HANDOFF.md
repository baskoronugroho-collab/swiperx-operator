# SwipeRx Operator — Build Handoff & Planning (Alpha 0.1)

> **Purpose:** self-contained context + instructions for continuing this project on another device / fresh Claude session (no access to prior conversation or memory). Read this file first, then `PRD.md`, then `PROTOTYPE_FEEDBACK.md`.
>
> Written 03 Jul 2026 · supersedes nothing — companion to PRD v2.1 (PRD v2.2 update is pending, see §6).

---

## 1. Project snapshot

**SwipeRx Operator** — delivery-compliance & returns web app for Ninja Van Indonesia's pharma-logistics partnership with SwipeRx. Product owner: **Baskoro Adi Nugroho** (baskoro.nugr@gmail.com). System name: **Alpha 0.1** (renamed from "v0.0.1").

**What exists today (in this folder):**

| Artifact | State |
|---|---|
| `PRD.md` | v2.1 — authoritative spec, but **not yet updated** with the 03-Jul decisions below (§3–§4). Trust this handoff over the PRD where they conflict |
| `PROTOTYPE_FEEDBACK.md` | Baskoro's written feedback on the deployed prototype, 03 Jul |
| `UNHAPPY_FLOWS.md` | **Unhappy-flow register (09 Jul audit)** — every failure path (real-life + in-app) with status, gaps, and the deduplicated decision batch for Baskoro. Live negative-path tests verified same day |
| `frontend/*.html` | **Clickable design prototypes only** (courier / operator / report). Self-contained demos, no backend calls, no persistence, fake data |
| `backend/main.py` + `V1__init.sql` | **Untouched Substrait scaffold** (sample `items` endpoints/table). The production backend is unbuilt |
| `cicd/` | Dockerfiles (backend :8000, static-nginx frontend :80) + nginx.conf — working, validated by the live deploy |
| `.substrait/config.json` | Live portal credentials (slug `swiperx-operator`, host `swiperx-operator.apps.substrait.build`, token `sbd_…`). **Needed to deploy; treat as a secret — rotate if this folder was shared** |
| `SwipeRx-app/app/` | Old demo build — **throwaway reference only**, never reuse |
| `deploy.sh` | **Missing from this folder** though PRD §17 references it (upload was incomplete). Recreate if needed: package via `git archive` (zip with forward-slash paths; PowerShell Compress-Archive makes backslash zips the platform rejects), upload to the portal API, watch the run |

**Deploy status:** the prototype is live at `swiperx-operator.apps.substrait.build` on the **public** Substrait portal. This validated the pipeline (build both images → Flyway migrate → serve `/health` + `/api` on OceanBase). The public portal **must never hold real pharmacy data** — Alpha 0.1 runs there with **dummy data only**; production moves to NV's self-hosted portal later (re-link with `--portal-url`, same contract, no code change).

**Known prototype bug (expected):** the generated driver link can't open — the operator prototype prints a fabricated URL and there is no backend token→courier route yet. First thing the real build fixes.

## 2. The Substrait contract (deployment platform)

Substrait is NV's internal deployment platform for Claude Code builds. Non-negotiables:

- **Backend** on **:8000**, `GET /health` probe, API under **`/api`**. FastAPI.
- **Frontend** on **:80**, same-origin relative `/api` calls. Swap the static prototype for **React + Vite + Tailwind** (two-stage node→nginx Dockerfile) for the real build.
- **DB: OceanBase, MySQL wire protocol** — injected `DATABASE_URL`. Use **`asyncmy`** with `%s` placeholders. **Never asyncpg/`$1`** — it is not Postgres.
- **All DDL in Flyway migrations** (`backend/resources/db/migration/V*.sql`, MySQL dialect). Never `CREATE TABLE` in code.
- **Redis** (`REDIS_URL`) — sessions, cache, email job queue. **`JWT_SECRET`** injected — signs session + courier tokens.
- Custom config/secrets declared in `backend/.env.example` (portal pre-creates entries; values filled in the portal). Public build-time frontend vars in `frontend/.env.production`.
- No `k8s/` in repo; ship source + Dockerfiles, ≤16 MB. Platform owns the cluster.
- **No object storage provided** — see stopgap decision §3.4.

## 3. Decision ledger (all locked — do not re-litigate)

### 3.1 From the PRD era (02 Jul)
~50 hubs. Failed-delivery flow: coded reason + timestamped proof photo (live-camera time or EXIF; force live capture if neither) → `DELIVERY_FAILED`. Station IC notified via per-hub multi-recipient email list. SwipeRx handover-rejection reason stays free text. Couriers tokenized, no login. 30-day retention + resubmit window. Bilingual ID/EN courier app. NV brand (red `#EE1B2C`, Montserrat).

### 3.2 Round 1 (03 Jul — from prototype feedback)
1. **Reject = flag + proof, not structured lines.** Courier indicates partial/full + proof photos (rejected-items photo, forward AWB sticker, DN box 2 = Return Form on forward). **No per-PO/qty reject entry; drop the `RejectLine` entity.** Problem #1 reframed: every return is *flagged with photographic proof at the door*, not captured as per-PO quantities.
2. **Signed+stamped = required attestation** on DN capture (reverses PRD §9's no-checkbox stance). Fast-follow: LLM/OCR check replaces the manual tick.
3. **Implant backlog view: kept in PRD but deferred** (no automated source yet; handover list is manual today). Remove the Backlog tab from the built SwipeRx report for now.
4. **Reprint/print tracking dropped** (drop FR-R4 ack/printed/labelled timestamps). Station IC just filters by hub + prints, or gets the email.
5. System named **Alpha 0.1** + in-app version-notes/changelog.
6. PO quantities are **koli (collies), ≤~10 per PO — never "units"**.
7. Courier UI = **phased wizard, no scrolling**.
8. **Role landing/launcher** on first open: who you are, your role(s), action-phrased starting points ("I want to create an OC", "I want to report a handover list").
9. **OC = 3 explicit steps**: upload SwipeRx template + select shipper/service ID (show name + service type) → app generates output with **driver link auto-injected into the delivery-instruction column** → download, upload into NV's internal system.
10. **Dedicated Validator page**, coded invalid reasons, **multi-select**: (a) DN missing / not signed+stamped; (b) Return Form missing / not signed+stamped — *only when a return was submitted*; (c) SP Manual missing vs DN; (d) invoice number mismatch. (c)+(d) split from Baskoro's combined phrasing.
11. **DE rejected-items queue**: view + download list → create real AWB in NV's system → mark "AWB created" → upload PDF sticker.
12. **Delivery data list** columns: order-creation datetime, driver-submitted, complete/fail, return (full/partial), RDO validity (– / valid / invalid), handover-by-Implant. Row click → detail + photos.
13. **PM metrics as rates**: % completed (of how many), % RDO validated, % return recorded; suggested adds: % failed, % invalid RDO, avg time-to-handover, backlog aging.
14. **SwipeRx report** grouped by **station + L2 (city/kabupaten)**; no backlog tab; no per-PO reject columns.
15. Courier submit = **confirmation preview → double-check → submit → Restart button** for misclicks.
16. Scope = original SwipeRx request, **all 3 movements** (regular 11398224 / instant 11549046 / return-pickup 11398423).

### 3.3 Round 2 (03 Jul — clarifications)
1. **Forward capture set UNCHANGED** — all 4 photo types stay (pharmacy storefront POD, receiver POD, DN, SP Manual × #Manual POs). The attestation is the *only* addition. ("Docs photo only" was a misread.)
2. **Arrival + handover KEPT** (FR-H1–H4). Implant surface = **one scan-input screen**: always-focused input, USB barcode scanner acts as keyboard, scan → `ARRIVED_AT_IMPLANT` → auto-built awaiting-handover queue → one-click handover (session) with optional rejection note. Value chain: arrival proof + **discrepancy alarms** (delivered-but-never-scanned = lost docs; scanned-but-never-delivered = courier skipped app) + backlog data accumulates for the deferred tab.
3. **Multi-role accounts**: `User.roles[]` — one person can hold e.g. Implant + Validator without superadmin. Landing page offers a starting point per hat. Superadmin assigns roles as checkboxes.
4. **Build Alpha 0.1 NOW with stopgaps**: public portal + **dummy data only**; photos stored as **OceanBase BLOBs behind a storage adapter** (S3-compatible interface so the real bucket drops in later with no schema churn).

### 3.4 Ripple effects (apply when building / updating PRD)
- Status lifecycle: `RETURN_LABELLED` **removed** → return track is `RETURN_AWB_PENDING → RETURN_AWB_CREATED` (DE marked created + uploaded PDF sticker).
- `ReturnParcel` loses `printed/printed_by/printed_at/labelled/labelled_by/labelled_at`.
- `User.role` → `roles` (many-to-many or JSON list).
- `.env.example` needs: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (secret), `ALLOWED_GOOGLE_DOMAINS`, SMTP host/user/pass (secrets). No S3 vars yet.
- SwipeRx CSV: **one row per AWB** (return_type + proof-photo URLs), not per reject line.

### 3.5 Defaults
**Confirmed by Baskoro (03 Jul):**
- Failed-delivery re-attempt: **same link re-opens** (no new AWB); prior attempts kept in history. ✅ LOCKED.
- Invalid verdict: **recorded-only** in v1 (no notification loop; appears in Validator download + PM view). ✅ LOCKED.

**Proposed — treat as decided unless vetoed:**
- Restart guard: allowed until Validator flags or DE acts on the return; then locked with "contact Implant".
- Station IC email content: AWB + hub + pharmacy + PDF link + hub-filtered worklist link. No ack.
- Service-3 capture set: BA photo (with attestation) + returned-goods photo, same wizard. *(Awaiting ops confirmation.)*
- Timezone: **WIB (Asia/Jakarta)** everywhere.
- Courier phases: order context → outcome → capture (one doc per screen, "step N of M") → reject proof (if any) → confirm preview → success + Restart.
- PM denominators: % completed = DELIVERED ÷ created in range; % RDO validated = (valid+invalid) ÷ delivered; % return recorded = AWB-created ÷ returns flagged.

**Pending input:**
- **Koli semantics** — AWB koli vs per-PO koli: **confirm from the real OC template** (Baskoro to send). Do not assume sum-of-PO-lines until the file confirms it. *(07 Jul: Regular = per-PO Koli count in col N, AWB = Σ; Sameday collie column still to confirm — see §3.6 / EXTRACTION_NOTES GAP-2.)*

### 3.6 Round 3 (07 Jul — from building the OC engine harness)
1. **S3 Return-Pickup branch_id = 2** (RTS `11398434`), master `11398423` in col B. LOCKED.
2. **Return delivery_instructions (R) = short "MUST open the link" text + link**; the variable-length item list + invoice live behind the link (courier-app payload), never crammed into R. Fixes the 500-char overflow with no truncation. Forward R keeps the fixed 214-char RDO. LOCKED.
3. **Hub is NV-assigned via a second upload flow — the engine does NOT derive the hub.** Round-trip: Implant uploads the OC file → NV creates the OC and **assigns a destination hub per piece** → Implant downloads the hub assignment → Implant **re-uploads** into a *different* NV upload section keyed on **[Ninja Van AWB/TRID] + [destination hub code]** (codes are `XXX-YYY`, e.g. `MAC-KD5`, `SUB-TBN`). **Drop the L2/postcode→hub map.** LOCKED. **Sample received:** `OC Template/AWB-hub assignment.csv` — cols `Shipper ID, Tracking ID, Origin Hub Name, Dest Hub Name, Count`; NV auto-adds a `-DO` document piece per PO (from `documents_required=RDO`). (EXTRACTION_NOTES §C.)
4. **Fixed values extracted** into `oc-engine/config.json`: forward RDO text (identical S1/S2), WH origin (F/G/H), S3 fixed pickup instruction (AJ), full S3 A–AJ map. See `oc-engine/EXTRACTION_NOTES.md`.
5. **Sameday collie count = col W** (`bundle_information.total_quantity`); same per-PO-line/count structure as Regular (koli in N). RESOLVED — a parser bug had been dropping col W (see EXTRACTION_NOTES GAP-2). LOCKED.

### 3.7 Round 4 (09 Jul 2026 — Baskoro)
1. **Forward `delivery_instructions` (col R) reworded — LOCKED & APPLIED.** New text (replaces the extracted Faktur/TTF/SP wording): *"Semua dokumen wajib ada nama penerima, ditandatangani dan distempel penerima. Jika di label tertera \"SP Manual\", maka dokumen SP Manual harus diminta ke penerima. Silahkan selesaikan delivery melalui link berikut:"* — the `<a>` anchor now attaches **directly** (no space after the colon). Applied in `backend/oc_config.json` + `oc-engine/config.json`; `_fit_instr`/`fitInstr` no longer inject a separator before the anchor. Return R wording unchanged (kept its trailing space).
2. **Failed-delivery reason list — LOCKED** (was PRD C2 / inputs #7; replaces the old `closed|reschedule|refused|not_found|no_receiver|access_blocked|other` prototype codes). Bilingual, for the M2 courier wizard:

   | code | ID (courier UI) | EN |
   |---|---|---|
   | `cancelled` | Penerima membatalkan pesanan | Recipient cancels the order |
   | `not_ordered` | Penerima tidak memesan paket | Recipient did not order the package |
   | `address_wrong` | Alamat tidak lengkap atau salah | Address incomplete or wrong |
   | `moved` | Penerima sudah pindah dari lokasi | Recipient has moved from the location |
   | `no_receiver` | Penerima tidak ada di lokasi | Recipient not at the location |
   | `reschedule` | Penerima meminta untuk penjadwalan ulang | Recipient asks for a reschedule |
   | `office_closed` | Kantor tutup | Office closed |
   | `force_majeure` | Bencana alam, huru-hara, atau terkena musibah/kecelakaan | Natural disaster, riot, or accident/misfortune |
   | `refused_sign` | Penerima tidak mau menandatangani dokumen | Recipient refuses to sign the documents *(added 09 Jul)* |

3. **"No return to collect" is NOT a failure — it's a SUCCESS path with a mandatory blank-signed return form. LOCKED.** When the consignee has no goods to return, the courier chooses **complete/success** delivery in the driver app (not a fail reason), **but must still collect the return form with the consignee's signature even though the form is left blank**. → M2 success flow must require a signed (blank-allowed) return-form photo in this branch. *(Distinct from `refused_sign`, which is an outright failure.)*
4. **Hub-assignment re-upload key = the AWB naming system.** The second NV upload (AWB↔hub round-trip) keys on **our AWB naming system** (not the old per-PO `-01/-DO` TRIDs in the sample). This is tied to inputs #4 — build the hub-assignment stage only **after** the AWB naming scheme is team-confirmed. Resolves EXTRACTION_NOTES §C's open "TRID vs AWB" question. LOCKED (pending the naming scheme itself).

5. **Photo timestamp = force live in-app capture + app-stamped time. LOCKED (09 Jul).** M2 courier capture uses the in-app camera (getUserMedia), the app stamps the capture moment (`timestamp_source=camera`); gallery/file upload with EXIF is only a fallback if we ever allow it (`timestamp_source=exif`), and re-capture is required if neither is present. Not forensic proof (no hardware attestation) — it's deterrence. **Show drivers a friendly "this is recorded" note at capture** (locked microcopy, bilingual):
   - **ID:** *"Semua foto diambil langsung dari kamera aplikasi dan waktunya tercatat otomatis untuk pengecekan. Foto tidak bisa diambil dari galeri — cukup ambil di lokasi seperti biasa 🙂"*
   - **EN:** *"All photos are taken live in the app and the time is logged automatically for review. You can't upload from your gallery — just snap it at the location 🙂"*
6. **Implant and DE are the SAME team — treat as interchangeable operators.** Baskoro (09 Jul): Implant = DE, both people can do either job. Validates the multi-role model (seed already has a de+implant user). Where a flow says "DE" or "Implant", either can perform it; no need to gate these two apart in practice.

**Open (Baskoro still deciding — do NOT build):**
- **Partial-reject → return-creation flow (may change §3.2 #11).** On a partial reject, the operator (Implant/DE — same team, §3.7 #6) checks and uploads into NV's system to create the OC/return template. **Flow mechanism left open** — Baskoro needs to see how NV generates the AWB inside their system first. Keep the current DE-creates-return-AWB flow until he confirms. *(Separate from the still-open "notify-only hub recipients" question.)*

## 4. Build plan — Alpha 0.1 milestones

Work P0-first; each milestone is deployable to the public portal with dummy data.

**M0 — Foundation** *(gate: sign-in works end-to-end on Substrait)* — **backend DONE + DEPLOYED/VERIFIED (09 Jul); React frontend still PENDING**
- [x] Replace scaffold backend with a modular FastAPI app: `config.py`, `db.py` (asyncmy pool + helpers), `storage.py` (adapter), `security.py` (JWT session + role gates), `auth.py`, `users.py`, `main.py`. Sample `hello`/`items` endpoints removed.
- [x] Flyway `V2__core.sql`: users(+`user_roles`), awb, po_line, document_capture, failed_delivery, return_parcel (no print/label fields), arrival_scan, handover_session/item, validation_flag (+`validation_reason` coded multi-select), hub_contact, notification, audit_log, app_version, media_blob (stopgap). `V1__init.sql` left intact (already applied — never edit applied migrations).
- [x] `V3__seed_dummy.sql`: 5 users incl. two multi-role, 6 AWBs across services/statuses (delivered, arrived, handed_over, delivery_failed, partial + full return), po_lines, return_parcels, one failed delivery, valid + invalid validation, hub contacts, Alpha 0.1 changelog. **Dummy data — public-portal safe only.**
- [x] Storage adapter: `StorageAdapter` (put/get/url) with `BlobStorage` (in-DB LONGBLOB) now; `S3Storage` presigned-URL impl later, no call-site change (`*_ref` cols hold opaque keys).
- [x] Google OIDC under `/api/auth/*` → session-cookie JWT (roles baked in) → unregistered gets roles=[] session; `/api/auth/me` exposes `has_access`; domain restriction via `ALLOWED_GOOGLE_DOMAINS`. **Dev-login fallback** (`POST /api/auth/dev-login`, gated by `DEV_LOGIN_ENABLED`) for building before the OAuth client exists.
- [x] Multi-role user management (`/api/users`, superadmin-only): register by email + roles[], patch roles/active.
- [x] `/api/version` endpoint returns system name + changelog (feeds the in-app "What's new" panel).
- [x] `requirements.txt` (+httpx, PyJWT, redis, python-multipart) and `.env.example` (OIDC/dev-login/SMTP) updated.
- [ ] **NOT DONE — React+Vite+Tailwind frontend scaffold** (swap static Dockerfile back to two-stage node→nginx); port NV tokens + the prototype login/landing/user-mgmt screens; wire `/api/auth`. This is the next step to reach the M0 gate.
- [x] **DEPLOYED & VERIFIED (09 Jul)** on the public portal. Flyway V2/V3 applied, `/api/version` returns the Alpha 0.1 changelog, dev-login mints a session. `deploy.sh` recreated at repo root (uses the portal upload API `POST /api/deploy`; see HANDOVER §0 deploy note — the Substrait plugin is not on this device).

*Local note: this Windows machine has NO Python installed — backend can't be run/tested locally. Verification happens at Substrait deploy time (platform builds the image) or needs a local Python + OceanBase/MySQL.*

**M1 — OC intake & courier links** *(gate: a generated link opens the courier app)* — **BACKEND DEPLOYED & VERIFIED (09 Jul) — GATE MET** (courier links open live)
- Full spec: **`OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md`**. Backend port lives in `backend/oc_engine.py` (+ synced `backend/oc_config.json`), `backend/oc.py` (routers), `backend/resources/db/migration/V4__oc.sql`. Run/verify guide: **`backend/OC_M1.md`**.
- [x] Upload SwipeRx TMP → Implant selects service (S1/S2/S3) → parse (openpyxl, skip header rows) → per-row errors, valid rows commit. `POST /api/oc/preview` (no writes) + `POST /api/oc/create` (commit).
- [x] Group by SwipeAWB → AWB + PO lines; per-AWB MPS (base=SwipeAWB, children `-1…-N`); unguessable `secrets.token_urlsafe` tokens; **`/api/c/<token>` resolves to the AWB** (HTML landing now; M2 wizard later) — fixes the prototype dead link. *(Link path is `/api/c/…` because only `/api/*` reaches the backend through the ingress.)*
- [x] Build NV upload `.xlsx`: B=master 11398423, AE=branch, E=service_level, W=TMP weight, Y=PO+collie list, link in col R (≤500); store + download `upload.xlsx` + `links.csv`; retain source file + `order_intake` log + `audit_log`.
- [x] **DEPLOYED & VERIFIED (09 Jul)** on Substrait. All expected counts matched exactly (S1 57/144, S2 79/210, S3 23/23; spot-checks AWB02S757→7, AWB02U24V→3). create→upload.xlsx (B=11398423, AE=1/3/2, R≤500 with `<updated_addr>` link)→courier link opens, incl. S3 return (invoice+item behind link). Checklist in `backend/OC_M1.md`.
- [ ] Single manual order entry (P1). Frontend intake UI (part of the React build). Hub-assignment re-upload stage (§3.6).

**M1 — LOCAL TRIAL PLAN — ✅ BUILT & VERIFIED (07 Jul 2026), in `oc-engine/`:**
- **Status:** extractions (HANDOVER §4.A) DONE and the Node harness (§4.B) built + run against all three real TMPs. Fixed values extracted into `oc-engine/config.json`; provenance + open GAPs in `oc-engine/EXTRACTION_NOTES.md`; run guide in `oc-engine/README.md`. Sample outputs in `oc-engine/out-S1|S2|S3/`.
- **Verified:** S1 57 AWBs→144 pieces (`AWB02S757` expands to 7; real weight not the hardcoded-1 bug; R=419/500, link format per guide §2.4). S2 79 AWBs→210 pieces (koli in col W; `AWB02U24V`→3). S3 23 returns (R = short must-open-link + link; full detail/invoice in links.csv; AJ pickup instruction; branch=2). MPS is per-AWB, base=SwipeAWB, children `-1…-N`.
- **GAPs + Baskoro's rulings (07 Jul, full detail in EXTRACTION_NOTES §B/§C):**
  - **S3 branch_id — RESOLVED: AE=2** (RTS `11398434`, per guide; the sample's AE=1 was a fill error).
  - **Return R over-500 — RESOLVED:** R is now a short fixed "you MUST open the link" instruction; the full item list + invoice ride in the courier-app payload (`links.csv`), not in R. No truncation.
  - **Regular vs Sameday layouts DIFFER (guide was wrong they're the same) — RESOLVED via per-service `source_layouts`.** Sameday koli = col **W** (Baskoro confirmed); a parser bug had been dropping col W (fixed in `xlsx-read.mjs` + `tools/xlsx.js`). Same per-PO-line/count structure as Regular.
- **NEW LOCKED DECISION — hub is NV-assigned via a second upload flow (see §3.6):** the engine does NOT derive the hub. Drop the L2→hub map idea (the return file's `Mapping Area`/`GJ` zone codes are NOT the hub source).
- **Next (M1 backend port):** carry these validated rules + the per-layout source maps into the FastAPI backend (real tokens, DB persistence, `/c/<token>` route, `.xlsx` output); add the hub-assignment second-upload stage.

**Original harness plan (for reference):**
- **Why a harness:** no Python locally, but Node v24 is available + we already have a Node xlsx reader (`scratchpad/xlsx.js`). The OC transform is pure logic (xlsx-in → output), no DB/auth needed → validate it locally first, then port the same rules into the FastAPI backend (Python).
- **Harness:** a standalone Node CLI `oc-engine/oc-engine.mjs` — args `--in <TMP.xlsx> --service S1|S2|S3`. Reads the TMP file, applies all guide rules, writes: (1) `out/upload.csv` (NV upload columns A–AE), (2) `out/links.csv` (SwipeAWB → token URL), (3) a summary (AWB count, TRID count, per-row errors).
- **Config file** `oc-engine/config.json`: master shipper, per-service branch id + service_level, WH origin (F/G/H — extract exact values from samples), the **exact fixed RDO text per movement** (still to extract — I truncated it), PUBLIC_BASE_URL for the fake link.
- **Stubs for the trial:** dummy L2→hub map; randomly-generated SP-Manual flag per PO; fake token (`crypto.randomUUID()`), real tokens come from the backend later.
- **Verify by:** opening `upload.csv` and diffing columns/MPS expansion/`R` hyperlink string against the real `[Template DE FWD]` sample. (Clickability itself is an NV-system behavior — the trial only checks the string is well-formed + ≤500 chars.)
- **Output format:** CSV for the trial (simplest, Excel-openable). Real engine emits the proper `.xlsx`. 
- **Not covered by the harness** (Python backend only): DB persistence, auth, real tokens, `.xlsx` with live array formulas, actual NV upload.

**M2 — Courier app** *(gate: full capture on a phone via a real link)*
- Phased wizard per §3.5; ID/EN; ≥48px targets; camera capture + file fallback + client-side downscale.
- Forward set (4 photo types, dynamic SP count) + **required signed+stamped attestation** on DN.
- Outcomes: normal / partial (flag + 3 proofs) / full (flag + proofs) / failed (coded reason + timestamped proof, EXIF/live logic).
- Completeness gate with stated reason; confirm preview; submit; Restart (with guard); resume/resubmit within 30 days.

**M3 — Back office** *(gate: reject→return→print path works)*
- DE return queue: list, CSV download, mark AWB-created, upload PDF sticker.
- Station IC: hub-filtered worklist + print (PDF); email notification via Redis job (log-only until SMTP creds arrive).
- Implant: scan-input arrival screen + one-click handover session (+ rejection note); discrepancy lists (delivered-never-scanned / scanned-never-delivered).
- Validator page: queue of submissions, valid/invalid + multi-select coded reasons; validity download.
- Delivery data list (columns per §3.2 #12) + detail drawer with photos.

**M4 — Oversight & report** *(gate: SwipeRx can self-serve a CSV)*
- PM overview: rate KPIs + clickable drill-downs, date/service filters.
- SwipeRx report: read-only, filters (service/status/return/pharmacy/hub/date/validity), grouped by station + L2, CSV (one row per AWB, signed photo URLs). No backlog tab.

**M5 — Guidance, polish, hardening**
- Role landing/launcher (multi-hat aware) + "How this works" per role + courier example images (pending DN mockup — placeholder until then).
- Audit log wiring; server-side role enforcement review; rotate the Substrait token; recreate `deploy.sh`.
- Update `PRD.md` → v2.2 folding in this ledger (see §6).

## 4b. OC template — RECEIVED & analysed (03 Jul)

Real files are in `SwipeRx/OC Template/`. Full analysis + engine spec: **`OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md`** (read before building intake). Headlines that change the model:
- **SwipeAWB** (`AWB02S5X7`) = the AWB grouping key + courier-link scope (one DN per SwipeAWB). **PO Number** = a long TRID code (`26060908042940Pt0L9chLQ`), many per AWB, each with its own **Koli**. AWB koli = Σ PO koli (koli question RESOLVED: per-PO, summed).
- **`sp_type` is NOT in the data** — rider reads the Faktur at the door (Bible Open Item #4). → drop sp_type from `po_line`; courier SP-Manual capture becomes rider-driven, not a pre-counted set.
- **L2 (kota/kabupaten)** = source **City** column. **Hub is NOT in the file** (only L2+postcode) → *(RESOLVED 07 Jul, §3.6: hub is NV-assigned via a second upload flow; engine does not derive it — no L2→hub map needed.)*
- Upload col **R `delivery_instructions`** = fixed RDO text (**≤500 chars**) → courier link appended as `<updated_addr>…<a href="{URL}">{URL}</a></updated_addr>` (**anchor text = the URL itself**). **MPS bundles per AWB**: **TRID base = SwipeAWB**, children `SwipeAWB-1…-N` (flat, no zero-pad, N=Σ collies) → one DN + one link per AWB. **AE always set from the service the Implant picks up front.**
- **Shipper model (corrected):** col B (`global_shipper_id`) is **always the master `11398423`**; the service is selected by **branch id in col AE**: **1 = Regular (11398224) · 2 = Return-Pickup RTS (11398434) · 3 = Instant/Sameday (11549046)**. `service_level` = STANDARD (S1/S3) / SAMEDAY (S2). *(Earlier "wrong shipper" note retracted — 11398423 is the master, correctly used.)*
- Resolved GAP cols: **W = TMP D weight**, **Y = PO list + total collies** (courier cross-check), **AE = branch id**. S1↔S2 differ only by service_level + branch_id.
- **Movement 3 (Return Pickup)**: SwipeRx **pre-supplies the return AWB** (`AWBR-…`) + invoice number; from=pharmacy, to=SwipeRx WH; courier brings BA Return form. It's its own intake flow, separate from forward-reject returns (which DE creates).
- GAPs to confirm: col W weight bug (hardcoded 1), col Y item_description, col AE branch_id, S2 fixed-field deltas, NV delivery-instruction length.

## 5. Inputs needed (ordered by blocking power)

| # | Input | Owner | Blocks |
|---|---|---|---|
| 1 | ~~OC template sample~~ **RECEIVED & analysed** (§4b + OC guide). Remaining sub-questions: hub mapping, SP-type add, GAP fields | Baskoro ← SwipeRx | mostly unblocked; hub map still open |
| 2 | **DN mockup** — layout, two sign+stamp boxes, barcode? | SwipeRx | Courier example images (M2 polish); what Implant scans (M3) |
| 3 | **Google OAuth client** for `swiperx-operator.apps.substrait.build` + approved Workspace domains | Baskoro | M0 real SSO (dev-login fallback exists) |
| 4 | **Hub → email distribution list** (+ who maintains it) | Baskoro | M3 Station IC emails |
| 5 | **SMTP/email provider creds** | Baskoro / NV infra | M3 (log-only fallback exists) |
| 6 | Confirm two flagged defaults: failed re-attempt = same link? invalid = recorded-only? | Baskoro | M2 / M3 detail |
| 7 | ~~**Fail-reason final list**~~ **LOCKED 09 Jul** (§3.7 #2 — 9 coded reasons incl. `refused_sign`; plus the "no return → success + blank-signed form" rule §3.7 #3). **Service-3 capture set** still open. | Baskoro + ops | S3 capture set → M2 |
| 8 | NV delivery-instruction **char limit** + driver's opening context (NV-app webview vs browser) | Baskoro + ops | M1 link format; M2 camera behavior |
| 9 | What Implant physically scans (NV AWB sticker vs DN barcode) | Baskoro | M3 arrival scan |
| 10 | **S3 bucket + creds**; **NV self-hosted portal URL/access**; data-residency ruling | Baskoro / NV infra | Production only — Alpha 0.1 unblocked by stopgaps |
| 11 | **Specific AWB naming system** — Baskoro flagged (09 Jul) this is pending his confirmation to the team. **Do not change the current AWB/TRID naming** (`SwipeAWB` base, MPS children `-1…-N`, flat/no-pad, locked §3 headline) until confirmed. Blocks the **hub-assignment re-upload stage** too (its key = this naming system, §3.7 #4). | Baskoro → team | M1 AWB/TRID generation (`oc_engine.piece_trids`) + hub-assignment stage — pending this |

## 6. Instructions for the next session/device

0. **Entry point:** open **`CONTINUE_HERE.md`** first (device-handover state as of 09 Jul + how to carry the assistant memory across, since it lives outside this folder — bundled in `_handover/memory/`).
1. **Read order:** this file → `UNHAPPY_FLOWS.md` → `PRD.md` (v2.1) → `PROTOTYPE_FEEDBACK.md`. Where the PRD conflicts with §3 here, **§3 wins** — the PRD hasn't been updated yet.
2. **First deliverable candidate:** update `PRD.md` to **v2.2** by folding in §3–§5 (rewrite §2 problem framing, §7.2, §9, §10 lifecycle, §11 FRs, §12 data model, §13 CSV, Appendix A matrix, Appendix C log; rename to Alpha 0.1). Baskoro has already approved the content — cutting v2.2 needs no further sign-off, but **show him the diff summary**.
3. **How Baskoro works:** discussion-first; confirm before changing locked decisions; he answers structured either/or questions well (give options + a recommendation). Keep a running open-questions log (PRD Appendix C); blocking items graduate to §19. Convert relative dates to absolute. He may add inline comments to the PRD.
4. **Build conventions:** demo at `SwipeRx-app/app/` is throwaway — never copy from it. The `frontend/*.html` prototypes are the **design reference** (tokens, layouts, ID/EN dictionaries are worth porting). asyncmy + `%s`; Flyway-only DDL; keep the storage/email/OIDC providers behind thin adapters (NV self-hosted equivalents drop in later).
5. **Deploy:** use the `.substrait/config.json` credentials against `api.substrait.build`. On Windows/Git-Bash the stock `/substrait:deploy` fails (no `zip`; Compress-Archive backslash paths) — package with `git archive`. `deploy.sh` did this; recreate it if absent.
6. **Never** put real pharmacy data on the public portal. Dummy data only until the NV self-hosted portal exists.
7. **Security notes:** `.substrait/config.json` token is live — don't publish this folder; rotate if shared. Real secrets go in the portal, never in the repo.

## 7. Memory export (verbatim from the assistant's persistent memory, 03 Jul 2026)

### 7.1 `user-baskoro.md` (type: user)
> Baskoro Adi Nugroho (baskoro.nugr@gmail.com) is the Product owner/author of **SwipeRx Operator**, a delivery-compliance & returns web app for Ninja Van Indonesia's pharma-logistics partnership with SwipeRx. He drives the product spec and coordinates the open dependencies (deployment stack, DN mockup, OC template, hub email lists) with ops/PM/SwipeRx.

### 7.2 `project-swiperx-operator.md` (type: project)
> **SwipeRx Operator** — production web app (PRD at `SwipeRx/PRD.md`, v2.0) for Ninja Van ID: enforce complete photographic POD/RDO capture (completeness gate, no ML in v1), structured reject capture, delivery→arrival→handover tracking, and a read-only SwipeRx report. Roles: Superadmin, PM, DE, Implant, Station IC, Validator, Courier (tokenized), SwipeRx. From-scratch build starting at **v0.0.1** (demo at `SwipeRx/SwipeRx-app/app/` is throwaway reference only).
>
> **Why / how to work with him:** As of 02 Jul 2026 Baskoro wants **discussion-first, no app code yet** — the build is blocked on two external items he's chasing: (1) NV's internal "DIY" deployment stack details (his meeting) → all stack decisions wait; (2) the new single-Delivery-Note (DN) mockup from SwipeRx → courier capture UI + example images wait. He also owes the **OC template** fields and the **hub→email distribution list**. Keep a running follow-up open-questions log at the bottom of the PRD (Appendix C); blocking items graduate to §19. He may add inline comments on the PRD.
>
> Decisions locked (02 Jul): ~50 hubs (not 100); failed-delivery flow added (coded reason + timestamped proof photo via live-camera or EXIF → status DELIVERY_FAILED); Station IC notified via per-hub email list (multi-recipient, action vs notify-only); SwipeRx handover-rejection stays free text.
>
> **Decisions locked (03 Jul 2026)** — from reviewing the deployed prototype + Baskoro's feedback (captured in `SwipeRx/PROTOTYPE_FEEDBACK.md`, PRD not yet updated): (1) **Reject = flag + proof only** — courier indicates partial/full + proof photos (item, forward AWB sticker, DN box2/Return Form); **drop `RejectLine` per-PO/qty capture**; problem #1 reframed to "every return flagged w/ proof at door". (2) **Signed+stamped = required attestation** on DN capture (reverses §9's no-attestation; future LLM/OCR to replace manual tick). (3) **Implant backlog kept but deferred** (no auto arrival/handover source; manual today) — remove Backlog tab from built report. (4) **Reprint/print tracking dropped** (drop FR-R4 ack/printed timestamps); Station IC just filters-by-hub+prints or emails. Also: system renamed **Alpha 0.1** (+ in-app changelog); PO qty is **koli ≤10, never "units"**; courier UI = phased wizard no-scroll; add role landing/launcher; OC = 3 steps (pick shipper/service ID w/ name+type → link injected into delivery-instruction column → download→upload to NV); dedicated Validator page w/ coded multi-select invalid reasons; DE rejected-items queue (download→mark AWB created→upload PDF sticker); PM metrics as rates; report grouped by station + L2. **Reality: only design prototypes + deploy pipeline exist — production app (schema/auth/storage/intake/capture) still unbuilt; scaffold backend untouched. Driver link can't open (no token→courier route yet).** SSO confirmed feasible on Substrait (wire Google OIDC ourselves; only dep = OAuth client registration).
>
> **Decisions round 2 (03 Jul):** forward capture set UNCHANGED (all 4 photo types; attestation is the only addition). Arrival+handover KEPT — Implant surface = one scan-input screen (USB scanner as keyboard) → ARRIVED_AT_IMPLANT → auto queue → one-click handover session; value = arrival proof + discrepancy alarms (delivered-never-scanned / scanned-never-delivered); backlog data accumulates for the deferred tab. **Multi-role accounts** (`User.roles[]`, landing offers each hat). **Alpha 0.1 builds NOW with stopgaps**: public portal + dummy data only, photos as OceanBase BLOBs behind a storage adapter (S3 later). Lifecycle: RETURN_LABELLED dropped → RETURN_AWB_PENDING → RETURN_AWB_CREATED; ReturnParcel loses printed/labelled fields. Proposed defaults (unvetoed): same-link re-open for failed re-attempt; restart guard until Validator/DE acts; invalid verdict recorded-only; WIB. Gaps in uploaded folder: `deploy.sh` missing (PRD §17 references it), React/Vite scaffold absent, `.substrait/config.json` holds live token in plaintext (rotate if shared). Open fact: what Implant scans (NV AWB sticker vs barcode-on-DN — DN mockup); NV delivery-instruction char limit + driver webview.

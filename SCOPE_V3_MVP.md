# SwipeRx Operator — v3 MVP scope (26 Jul 2026)

> **Supersedes PRD §4 Goals for build purposes.** The PRD stays the full specification; this document
> is the **shipping target**: the smallest end-to-end system that is genuinely usable in the field.
> Anything not listed under §3 is **explicitly out** of this cut.

---

## 1. Why re-scope

PRD v2.3 specifies seven roles and ~60 P0 requirements across order creation, courier capture,
validator, arrival scan, handover sessions, SwipeRx receipt loop, and reporting. Actual build state:

| Layer | State |
|---|---|
| Backend M0 — auth, users, sessions | ✅ built + deployed |
| Backend M1 — OC preview/create, upload+links download, courier token resolve | ✅ built + deployed, ⚠️ **child-TID output is wrong** (`OC_LINKING_BUG.md` §4) |
| Courier **capture** endpoints (photo upload, submit, reject flag) | ❌ **not built** — no POST route exists |
| Reject-return worklist | ❌ not built |
| Arrival scan / handover / SwipeRx receipt | ❌ not built |
| Validator, PM dashboard, report | ❌ not built |
| Frontend | ⚠️ **static design mockups only** — `courier.html` / `operator.html` / `report.html` have **0 API calls** between them |
| Backend tests | ⚠️ **source files missing** — `backend/tests/` holds only `__pycache__`, nothing tracked in git |

The gap between spec and build is now the main risk. Three lanes, end-to-end, beat seven lanes at 40%.

---

## 2. The v3 goal — one sentence

**One AWB can travel the full loop in production: Implant creates the order and its link → the driver
opens that link and files what we need → Ops sees any partial reject, acknowledges it, and confirms
the replacement TIDs were sent.**

Everything else waits.

---

## 3. The three lanes

### Lane 1 — Implant: order creation + link creation

| ID | Requirement | State |
|---|---|---|
| V3-OC1 | Upload SwipeRx TMP, pick service **by name** (no S1/S2/S3 in the UI), pick a **single** delivery date | backend ✅ / UI ❌ |
| V3-OC2 | **Emit an upload file Ninja actually accepts** — one row per bundle, `AC = A-01…A-0N`, zero-padded, restart at 01. Resolve the model per `OC_LINKING_BUG.md` §3 before wiring the UI | ❌ **blocking** |
| V3-OC3 | Every AWB gets an unguessable token link (`secrets.token_urlsafe`), injected into `parcel_job.delivery_instructions` (col R), ≤500 chars | ✅ |
| V3-OC4 | Two downloads: OC upload file + link-map CSV; both retained in an upload-history table | backend ✅ / UI ❌ |
| V3-OC5 | All-or-nothing commit; per-row error report on failure | ✅ |
| V3-OC6 | Operator UI: upload → preview (errors visible) → create → download. Real screens, wired to the API | ❌ |

**Done when:** a DE uploads a real TMP, downloads the file, uploads it into Ninja's system, and
**every parent–child link resolves**. That last clause is the whole point — verify it on a live batch,
not in a spreadsheet.

### Lane 2 — Driver: open the link, file the entries

| ID | Requirement | State |
|---|---|---|
| V3-D1 | Token link resolves with no login → AWB header (AWB line 1, pharmacy line 2), service, address, total koli, per-PO koli | ✅ (backend + placeholder page) |
| V3-D2 | Phased capture wizard: **pharmacy POD → receiver POD → Delivery Note (whole doc) → SP-Manual photos per flagged PO → "any partial reject?"** | ❌ |
| V3-D3 | **Photo upload endpoint + media storage** — live in-app camera default, "upload instead" fallback, server-stamped capture time | ❌ **blocking** |
| V3-D4 | Signed + stamped attestation tick on the DN; completeness gate blocks confirm until every required photo + the tick are present | ❌ |
| V3-D5 | Partial-reject branch (inline): DN return section close-up + full page + rejected-goods photo + forward AWB sticker photo → final screen **lists the AWBs to be returned** and tells the courier to screenshot + inform Station IC | ❌ |
| V3-D6 | Failed delivery: 9-code reason list + one proof photo | ❌ |
| V3-D7 | Success screen reminds the courier to **also confirm in the Ninja driver app**; link resumes in place for 30 days | ❌ |

**Cut from Lane 2 for v3:** GPS capture, offline/sync, image OCR detection, "Something wrong?"
resubmit guard (a plain read-only terminal state is enough for the first cut).

### Lane 3 — Ops: reject-return acknowledge + TID confirmation

This is the lane the field asked for, and it is the one with the least written down. Concretely:

| ID | Requirement | State |
|---|---|---|
| V3-R1 | A courier reject (V3-D5) **creates a reject-return row** carrying: forward AWB, pharmacy, service, reject photos, timestamp, courier | ❌ |
| V3-R2 | **Ops worklist** of open reject-returns with a **"Not yet acknowledged"** filter — the default view | ❌ |
| V3-R3 | **Acknowledge checkbox** per row — Ops ticks it to confirm they have seen the reject and are handling it. Records who + when | ❌ |
| V3-R4 | **"New TIDs sent" confirmation** — Ops enters/pastes the replacement return TID(s) created on the **RTS account `11398434` (branch 2)** and marks them sent. Records the TID(s), who, and when. This closes the row | ❌ |
| V3-R5 | Row stays visible with its full audit trail (reject → acknowledged → TIDs sent) and is exportable to CSV | ❌ |

**Deliberately simple:** in v3 Ops **types or pastes** the return TIDs. Generating them from a reject
OC template engine (PRD FR-R4 / §19 #23) is **deferred** — it is a second template engine that
nobody has specified, and the WA-group workaround it replaces already works. The value here is the
**visibility and the audit trail**, not the generation.

> Confirms the deck (slide 16): *"Jika ada partial reject, kurir/Spv harus lapor ke group WA Internal,
> agar tim DE membuatkan TRID baru... menggunakan account 11398434 - PT Teknologi Medika Pratama - HW -
> RTS Account (B2BR)."* Lane 3 replaces the WA group with a tracked worklist; DE still mints the TID
> in NV's system exactly as today.

---

## 4. Explicitly deferred (was P0 in PRD v2.3)

| Deferred | PRD ref | Why |
|---|---|---|
| Arrival scan + handover sessions + SwipeRx receipt loop | §11.5, FR-H1–H6 | large surface, no field pressure yet; the WA/manual process holds |
| Validator role + flagging | §11.6 | non-blocking by design → not on the critical path |
| Program Manager dashboard | §11.7 | consumes data the three lanes must produce first |
| SwipeRx report (grouped Forward/Reject/Special-case) | §11.8 | replace with a **CSV export** per lane in v3 |
| Reject-item OC template engine | FR-R4, §19 #23 | superseded for v3 by V3-R4 (paste the TIDs) |
| Return Pickup / Special-Case (`AWBR`) service | §7.4 | separate flow; forward + reject first |
| Hub-assignment re-upload | FR-OC7 | second upload flow, NV-side dependency |
| Image sign/stamp detection | §16 | already a fast-follow |
| Google Workspace SSO | FR-A1 | keep the **dev-login stopgap** for v3; SSO before real data |
| Single manual order entry | FR-OC8 | P1 already |

---

## 4b. Build status — 26 Jul 2026

All three lanes are built and verified end-to-end against a running stack.

| Piece | State |
|---|---|
| React + Vite + Tailwind frontend (`frontend/`) | ✅ real project — router, typed API client, auth context, role-gated shell |
| Lane 1 — Order creation UI | ✅ 3-step flow, service by name + read-only shipper id/name/branch, single date, preview with per-row errors, all-or-nothing gate, both downloads, upload history + detail with copyable courier links |
| Lane 2 — courier backend (`backend/courier.py`) | ✅ token-scoped capture, media scoped per AWB, server-side completeness gate, 9 locked fail reasons, 30-day expiry, resume-in-place |
| Lane 2 — courier wizard (`frontend/src/pages/courier/`) | ✅ phased no-scroll wizard, camera-first with gallery fallback, DN attestation, rider-driven SP-Manual per PO, inline partial-reject branch, failed-delivery flow, Ninja-driver-app reminder |
| Lane 3 — reject worklist (`backend/returns.py` + `RejectReturns.tsx`) | ✅ stage tabs, acknowledge checkbox with who/when, TID entry gated on acknowledge, audit trail, CSV export |
| Migration `V5__capture_and_returns.sql` | ✅ fail-reason remap + return_parcel acknowledge/TID columns |
| Backend tests (`backend/tests/`) | ✅ restored — **35 passed, 1 xfail** (SQLite harness; only the driver is swapped) |
| `cicd/Dockerfile.frontend` + `nginx.conf` | ✅ two-stage node build → nginx, SPA fallback covers `/c/<token>` |

**Verified live**, not just unit-tested: full courier flow driven through a running backend
(capture → attest → gate refuses reject set → complete → submit) landing a row on the Ops
worklist, then acknowledge → TIDs → closed with the audit trail, all through the real UI.

**Deferred, deliberately:** GPS capture, offline/sync, the "Something wrong?" resubmit guard
(terminal state is read-only instead), and the S3 Return-Pickup capture set (§4).

Run it locally:

```bash
python backend/tests/devserver.py
```

```bash
npm run dev --prefix frontend
```

## 4c. Deployment — BLOCKED, needs portal access (26 Jul 2026)

### The platform SSO gateway (new since 09 Jul — important)

`swiperx-operator.apps.substrait.build` now sits behind Substrait's own Google SSO
gateway. Verified allowlist, probed against the live host:

| Path | Behaviour |
|---|---|
| `/c/*` | **exempt** — reaches the app unauthenticated |
| `/api/c/*` | **exempt** — reaches the app unauthenticated |
| everything else (`/`, `/assets/*`, `/index.html`, `/favicon.ico`, `/api/version`) | 302 → `accounts.google.com`, or 401 for `/api/*` |

**This dictates the frontend build layout.** The default Vite output at `/assets/*` is
SSO-gated, so a courier would load `index.html` and then get bounced to a Google login
they have no account for — a blank page at the door. `frontend/vite.config.ts` therefore
sets `build.assetsDir = "c/assets"`, putting the bundle inside the exempt prefix
(`/c/assets/index.js` → 200 unauthenticated, confirmed live). Drop this once the portal
allowlists `/assets/`.

**One auth layer, since 28 Aug 2026 (C33 CLOSED).** Platform SSO authenticates the staff
user and injects `x-forwarded-email`; `security.current_user` resolves that to a
registered user and their roles. The app no longer runs a login of its own, needs no
OAuth client, and `DEV_LOGIN_ENABLED` has no effect on a gated request. Superseded text:
*"Two independent auth layers ... the app still needs either `GOOGLE_CLIENT_ID` /
`GOOGLE_CLIENT_SECRET` configured on the portal, or `DEV_LOGIN_ENABLED`."*

### ✅ DEPLOYED — run 2001186, live 26 Jul 2026 15:19

Verified against the live host after rollout:

| Check | Result |
|---|---|
| SPA bundle path | `/c/assets/index-C1n3oXnc.js` — matches the local build hash |
| Bundle loads with **no** login | 200 ✅ (the courier-blank-page trap is closed) |
| Dummy AWB token | 404 ✅ (`V7` ran — seed data gone) |
| Courier API on a bad token | 404 `invalid_link` ✅ (`courier.py` is routing) |
| Staff route `/orders/new` | 302 → Google ✅ (still gated) |

**`substrait.yaml` is required at the repo root** (new ~26 Jul; the plugin docs on this
machine are dated 26 Jun and predate it). Two things it must get right:

```yaml
description: >-           # 1–3 sentences; shown in the portal + API Library
  …
services:                 # a MAPPING, never a list — a list is rejected outright
  redis: {}
```

`services` is **authoritative, not additive**: omitting a service the app has **removes**
it. Redis was genuinely provisioned (the build log shows `Provisioning redis`), so it is
declared even though no application code reads `REDIS_URL` today.

### What the four failed runs actually were

Runs 2001174 / 2001177 / 2001179 / 2001184 all died in **1 second** — rejected at
validation, before any build. Two distinct causes, in sequence:

1. **missing `substrait.yaml`** (first three),
2. **`services` written as a list** instead of a mapping (the fourth).

Neither was visible from outside: the upload returns `202 + run_id` either way, and the
failure reason exists **only in the portal**. The `sbd_` token cannot read run status
(`GET /api/runs/<id>` → 401). *Lesson: on a 1-second failure, ask for the portal log
immediately — do not iterate blind.*

A fifth run then failed on a Flyway **checksum mismatch** — an older migration file no
longer matched the fingerprint recorded when it was first applied. Resolved by resetting
the database. **Never edit an applied migration**; `V7__remove_dummy_seed.sql` deletes the
seed data with a new migration instead of rewriting `V3`.

Also corrected: the 22 Jul deploy did **not** fail. Run 2000874 succeeded in 34s — the
"timeout" was purely the broken watcher below.

### Superseded — the blind-diagnosis notes

Three uploads accepted, none went live (`/api/c/<token>` still answers with the pre-26-Jul
build after 15 min each):

| run | change under test | result |
|---|---|---|
| 2001174 | full v3 build, two-stage node Docker build | never rolled out |
| 2001177 | + `V6` fixed (`FROM DUAL`) | never rolled out |
| 2001179 | + prebuilt `dist`, no node step in the image | never rolled out |

**No build logs are reachable:** the `sbd_` token is deploy-scoped — `GET /api/runs/<id>`
returns `401 invalid token`, sibling endpoints 404, and the linked GitHub repo
(`gotchykid/substrait-swiperx-operator`) is private (404 unauthenticated).

Ruled out locally: a clean `npm ci` + `npm run build` from exactly the zipped files
succeeds, and the zip contains all expected files. Run 2001179 removed the node build
entirely and still didn't land, so the frontend image is **not** the cause.

Remaining suspects, in order: **(1)** `V5`/`V6` failing in the platform's Flyway step —
and note a failed migration can leave Flyway needing a `repair` before any later deploy
succeeds; **(2)** the backend image; **(3)** a platform-side pipeline problem. Worth
noting a **deploy on 22 Jul also timed out**, before any of this work existed.

**Next step is yours:** open runs `2001174` / `2001177` / `2001179` in the Substrait portal
and read the build log. That answers in seconds what cannot be inferred from outside.

### `deploy.sh` fixes made along the way
- Python path was hardcoded to `C:/Users/NXP/anaconda3/python.exe` (the old handover machine).
- git-bash `/c/Users/…` paths were passed to a Windows Python, which cannot open them.
- The rollout watcher polled `/api/version`, which now always 401s behind the gateway — it
  could never succeed and always reported a false timeout. Now polls the SSO-exempt
  `/api/c/<token>`, expecting the new 307 redirect.


## 4d. OC engine updated to guide rev. 27 Jul 2026

`OC_TEMPLATE_AND_ENGINE_GUIDE.md` §2.3 settled the tracking-number question that was
parked. Implemented for **S1 + S2** (S3 unchanged):

| Rule | Implementation |
|---|---|
| **One upload row per AWB** (1 WP = 1 MPS TRID = 1 SwipeAWB) | `build_upload_xlsx` emits one row per AWB — was one row per collie |
| `A` = `D` = SwipeAWB | `_upload_row` takes `awb_id` as the bundle TRID |
| Children = `PO_Number-01…-NN`, **continuous across the AWB**, zero-padded | `piece_trids()` |
| `AB` = Σ koli · `W` = AWB total weight · `Y` = PO list + total koli | unchanged fields, now AWB-grained |
| Link = `{base}/c/{token}` | `oc.py` — was `/api/c/{token}` (old links still 307 to the new route) |
| RDO wording per the New RDO deck | `oc_config.json` `rdo_text.forward` |
| **S1 renamed `Regular B2BR`** | `oc_config.json` |

Verified against the guide's worked example and a real 57-AWB TMP: 57 rows, `AWB02S757`
→ 7 pieces `…Xp3cOoIZ-01, …Cd4TW12aas-02, …OsBIgygMR-03, -04, …QdGxl7HjpI-05, -06,
…R3g3X2E5cC-07`. Pinned in `backend/tests/test_oc_engine.py`.

> ⚠️ **Col R sits at exactly 500/500** in production (267-char mandated text + 29-char CTA
> + an 80-char URL counted twice + 44 chars of tags). Zero headroom: a longer
> `PUBLIC_BASE_URL` or token silently trims the compliance wording. The engine now flags
> this — `instr_truncated()` → `order_intake.warning_summary` → an operator-visible banner.

> ⚠️ **Unresolved:** the guide says `A` = the bare SwipeAWB (9 chars), but the confirmed
> tracking-number rule is **min 11 / max 29** with no prefix allowed. Every SwipeAWB
> observed is exactly 9 characters. These cannot both hold — raise with the tech team.

**New: Courier links page** (`/links`) — every link on screen, searchable, copy-one or
copy-all, no download needed (guide §5 step 8). Links also appear immediately on the
create-success screen.

## 5. Build order

1. **Fix the OC output** (`OC_LINKING_BUG.md` §3 + §4) and **prove it on a live Ninja upload**.
   Nothing downstream matters if the links don't attach. *Also ship Fix A to the DE team's Excel today.*
2. **Media storage + photo upload endpoint** (V3-D3) — every Lane-2 screen depends on it.
3. **Courier capture endpoints + wizard** (V3-D2/D4/D5/D6/D7), wiring the existing `courier.html` design.
4. **Reject-return worklist** (Lane 3) — small, and it is what Ops asked for.
5. **Operator OC UI** (V3-OC6), wiring `operator.html`.
6. **Restore `backend/tests/`** — the test sources are gone from git; regression cover is needed before
   this touches real pharmacy data.

**Non-negotiable gate before real data:** dummy data only on the public Substrait portal until SSO
lands and the deployment moves to NV self-hosted.

---

## 6. RDO document changes from the new deck (`Modul 1 — Pengantaran Paket Shipper SwipeRX [New RDO]`)

Checked against PRD §7.1 / §3 — **the PRD is already aligned on the headline change**, with three
additions worth folding in:

| Deck | PRD status |
|---|---|
| RDO returning to shipper is now **Delivery Note + SP Manual (if manual)**; **Faktur/Invoice is left at the pharmacy** (slides 12, 21, 37) | ✅ already PRD §7.1 / §1.1 ("no separate Faktur", confirmed 14 Jul) |
| TTTF **dropped** from the returning set | ✅ already dropped in PRD |
| DN now prints **Jumlah Invoice, Jumlah Koli, Tipe Dokumen (Manual/Elektronik)** (slide 13) | 🆕 **PRD FR-OC3 says "SP type is not stored — the rider identifies it at the door."** Still true, but the rider now **reads it off the DN** rather than guessing. Worth adding to the V3-D2 SP-Manual step copy. |
| **Faktur Prekursor + SP Manual → the SP must use the Prekursor template** (slide 37) | 🆕 not in PRD. Add as a courier-app hint on the SP-Manual step. |
| Non-Prekursor + SP Elektronik → **no SP needed at all**, rider must not ask (slide 27) | 🆕 not in PRD. Prevents a common wasted ask — add to the same step. |
| Pharmacy fills the **kondisi penerimaan + kolom retur** section of the DN (slide 14) | ✅ matches PRD's "DN two sections" model |
| Reject → report → **DE mints a new TRID on account `11398434` (RTS, branch 2)** (slides 16, 19) | ✅ matches `oc-engine/config.json` S3 (branch 2). Now formalised as **Lane 3 / V3-R4**. |

**No PRD flow rewrite needed** — the deck confirms the direction PRD v2.3 already took. The three 🆕
rows are courier-app microcopy, folded into V3-D2.

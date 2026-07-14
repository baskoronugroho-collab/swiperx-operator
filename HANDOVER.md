# SwipeRx Operator — Handover (continue on another device)

> Quick-start entry point. Dated **07 Jul 2026**. Read this first, then the linked docs.
> Everything decided lives in the repo — no dependency on the previous chat session.

---

## 0. Transfer — which folder to send & first steps

**Send the entire `SwipeRx` folder** (currently `C:\Users\NXP\.claudeai\SwipeRx\`, ~6.3 MB) to the device that has the Substrait plugin. It is self-contained — code, docs, real sample files, and deploy creds all live inside it.

- **Include** `.substrait/` (holds the deploy creds — needed to deploy). ⚠ It contains a **live portal token**: transfer over a private channel and **rotate the token** afterwards if the channel was shared (see §7).
- **Optional to skip:** `SwipeRx-app/` (2.5 MB — the throwaway old demo, never reused) and `oc-engine/out-S1|S2|S3/` (regenerable sample outputs). Everything else is needed. Keep `OC Template/` — the real sample files are used to smoke-test M1.
- **No secrets to set before sending** — real values (OAuth, SMTP) go into the Substrait portal after upload, not into the repo.

**First steps on the new device:**
1. Read this file, then `BUILD_HANDOFF.md` (§1 read order below).
2. **Deploy + verify the M1 backend** — the immediate goal. Follow **`backend/OC_M1.md`** (deploy via the Substrait plugin; then health → dev-login → preview → create → open a courier link). Expected engine counts are in that doc.
3. If Node is available there, you can also re-run the local OC harness (`oc-engine/README.md`) to re-confirm the transform independently of Python.

**Latest state (09 Jul):** M0 backend + M1 OC-intake backend are now **DEPLOYED & VERIFIED** on the public portal (`swiperx-operator.apps.substrait.build`). All smoke-test counts matched (S1 57/144, S2 79/210, S3 23/23; spot-checks AWB02S757→7, AWB02U24V→3); create/download/courier-link all work end-to-end, including the S3 return path (branch_id=2, invoice+item behind the link). **React frontend is the next big unbuilt piece.** Details in §2/§4.

> **Deploy mechanism note (09 Jul):** the Substrait *plugin is NOT installed on this device* and `git archive` doesn't apply (folder isn't a git repo). Deploy was done via the portal's upload API directly — `POST https://api.substrait.build/api/deploy` (Bearer token from `.substrait/config.json`, multipart field `file` = a forward-slash `.zip` built with Python's `zipfile`). This is now captured in the **recreated `deploy.sh`** at the repo root — run it to redeploy. The `sbd_` token is deploy-scoped (POST-only); run-status polling uses the app's own `/api/version`. ⚠ The live token was used from this device — rotate it per §7 if this folder's channel was shared.

---

## 1. Read order (all in the `SwipeRx/` folder)

1. **`BUILD_HANDOFF.md`** — the cross-device source of truth: full decision ledger, milestone plan (M0–M5), inputs table, working conventions, memory export. **Where it conflicts with `PRD.md`, the handoff wins** (PRD v2.2 not yet cut).
2. **`OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md`** — build-ready spec for the OC intake engine (source→target mapping, per-AWB MPS, master/branch shipper, link injection, all 3 movements). Read before touching the engine.
3. **`PROTOTYPE_FEEDBACK.md`** — Baskoro's feedback on the deployed prototype + the 4 locked decisions.
4. **`PRD.md`** (v2.1) — original spec; still to be updated to v2.2.
5. **`backend/OC_M1.md`** — M1 backend: endpoint reference + the deploy smoke-test (start here to deploy/verify).
6. **`oc-engine/EXTRACTION_NOTES.md`** — extracted fixed values + resolved GAPs + the hub-assignment file format.
7. **`UNHAPPY_FLOWS.md`** — unhappy-flow register (09 Jul audit): every failure path with status + the open decision batch for Baskoro.

## 2. Where we are right now

- **Design prototypes** (`frontend/*.html`) + **Substrait deploy pipeline** are live/validated (public portal, dummy data only). Prototype driver link can't open — expected; the real build fixes it.
- **M0 backend foundation: DONE + DEPLOYED (09 Jul)** (in `backend/`) — modular FastAPI, Flyway schema `V2__core.sql` + seed `V3__seed_dummy.sql`, Google SSO + dev-login, multi-role users, storage adapter, `/api/version`. Verified live: `/api/version` returns Alpha 0.1 + changelog; dev-login mints a session (dewi.k = de+implant).
- **M0 frontend (React/Vite) + deploy-verify: NOT done** — needed to reach the "sign-in works end-to-end" gate.
- **OC engine (M1): local-trial harness verified** (`oc-engine/`) **AND FastAPI backend port BUILT** (07 Jul, `backend/oc.py`, `oc_engine.py`, `V4__oc.sql`) — intake, per-AWB MPS, tokens, `.xlsx` output, `/api/c/<token>`. **DEPLOYED & VERIFIED 09 Jul** — all `backend/OC_M1.md` smoke-test counts matched exactly; courier links open (prototype dead-link fixed).

## 3. Decisions locked (don't re-litigate — full list in BUILD_HANDOFF §3)

Headlines most relevant to what's next:
- **Reject = flag + proof only** (no per-PO/qty capture; drop `RejectLine`).
- **Signed+stamped = required attestation** on DN (LLM/OCR later).
- **Multi-role accounts** (`User.roles[]`); Alpha 0.1 builds now with **stopgaps** (public portal + dummy data + OceanBase BLOB storage).
- **OC engine specifics:** Implant picks service (S1/S2/S3) up front. Col B always master `11398423`; branch id in col AE (1 Regular / 2 Return-Pickup 11398434 / 3 Sameday). **TRID base = SwipeAWB**, MPS children `SwipeAWB-1…-N` (flat, no pad, N=Σ collies). Link in col R as `<updated_addr>…<a href="{URL}">{URL}</a></updated_addr>` (anchor text = URL), ≤500 chars. L2 = source City col.
- **Failed re-attempt = same link re-opens; invalid verdict = recorded-only.**

## 4. Immediate next actions (in order)

**A. Two data extractions — ✅ DONE (07 Jul 2026).** Values in `oc-engine/config.json`; provenance in `oc-engine/EXTRACTION_NOTES.md`.
1. ~~Exact fixed RDO text per movement~~ — extracted (forward RDO identical for S1/S2, 214 chars; S3 has a fixed AJ pickup instruction + data-driven R).
2. ~~WH origin (F/G/H) + full S3 A–AJ mapping~~ — extracted.

**B. OC engine local-trial harness — ✅ BUILT & VERIFIED (07 Jul 2026), in `oc-engine/`.** Runs on all three real TMPs (see `oc-engine/README.md`). Turned up 3 GAPs + a candidate hub map — **needs Baskoro input** (EXTRACTION_NOTES §B/§C): S3 branch_id 1-vs-2, Regular/Sameday layout divergence + Sameday collie model, return-instruction 500-char truncation.

**C. FastAPI backend port — ✅ BUILT (07 Jul), in `backend/`.** `oc_engine.py` (transform, openpyxl), `oc.py` (routers), `V4__oc.sql` (schema), synced `oc_config.json`. Endpoints + deploy smoke-test in **`backend/OC_M1.md`**. **Deploy-verify pending** (no local Python — verify at Substrait deploy on the device with the plugin).

**D. NEXT after deploy:** React/Vite frontend (M0 login/landing + M1 OC intake UI) to reach the M0 sign-in gate and give Implant a UI; then courier wizard (M2). Frontend still unbuilt.

## 5. Environment notes (this machine — may differ on the next device)

- **Windows 10, PowerShell + Git-Bash.** **No Python installed** → backend can't run locally here; verify at Substrait deploy time, or install Python + a MySQL/OceanBase locally.
- **Node v24 present** at `C:\Users\NXP\Documents\NXP\node.exe`. Parser scripts saved in **`SwipeRx/tools/`** (`xlsx.js`, `docx.js`). Run e.g.:
  `& "C:\Users\NXP\Documents\NXP\node.exe" "SwipeRx\tools\xlsx.js" "SwipeRx\OC Template\<file>.xlsx"`
  (pass Windows paths with forward slashes; git-bash `/c/…` paths get mangled by node.)
- **Deploy:** creds in `.substrait/config.json` (portal `api.substrait.build`, slug `swiperx-operator`). Stock `/substrait:deploy` fails on Windows (no `zip`); package with `git archive`. `deploy.sh` is missing — recreate it.

## 6. Open items / pending decisions

- **Hub map — RESOLVED (07 Jul):** hub is **NV-assigned** via a second upload flow (AWB/TRID + `XXX-YYY` hub code like `MAC-KD5`); engine does NOT derive it. Sample received: `OC Template/AWB-hub assignment.csv` (cols: Shipper ID, Tracking ID, Origin Hub, Dest Hub, Count). *(Confirm whether the re-upload keys on the piece TRID or the AWB — EXTRACTION_NOTES §C.)*
- **Sameday collie column — RESOLVED:** koli is in col **W**; a parser bug had been dropping it (now fixed). Engine sums W per AWB, same as Regular's col N.
- **SP Manual detection** — not in data; rider reads Faktur at door; Baskoro checking with SwipeRx.
- **Local-trial language** — Node harness done & verified (no installs). Backend port (Python/FastAPI) is next.
- **Production infra** (not blocking Alpha): S3 bucket, NV self-hosted portal, data-residency ruling, Google OAuth client, SMTP creds, hub→email list.
- **PRD v2.2** — fold in the decision ledger when ready (content already approved).

## 7. Security

- `.substrait/config.json` holds a **live portal token** — don't publish this folder; rotate the token if it's been shared. Keep real secrets in the Substrait portal, never in the repo.
- Public portal = **dummy data only** until the NV self-hosted portal exists.

## 8. How Baskoro works

Discussion-first; confirm before changing locked decisions; answers structured either/or questions well (give options + a recommendation). Keep the open-questions log current. **If you make decisions on the other device, write them back into `BUILD_HANDOFF.md`** so this machine (which holds the assistant's memory) can re-sync.

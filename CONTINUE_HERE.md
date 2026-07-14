# ▶ CONTINUE HERE — SwipeRx Operator device handover

> **Written 09 Jul 2026.** This is the single entry point when you open the project on another
> device. Read this first; it tells you the state, the read order, and — importantly — **how to
> carry the assistant's memory across** since it lives *outside* this folder.

---

## 1. What to upload

**Upload the entire `SwipeRx\` folder.** It is self-contained: code, docs, real sample files,
deploy creds, and now a copy of the assistant memory (`_handover/memory/`).

- **Must include:** `backend/`, `cicd/`, `frontend/`, `OC Template/`, `oc-engine/`, `.substrait/`
  (deploy creds — ⚠ live token, transfer privately + rotate if the channel was shared), all root
  `*.md` docs, and **`_handover/`** (the memory bundle — see §4).
- **Optional to skip:** `SwipeRx-app/` (throwaway old demo) and `oc-engine/out-S1|S2|S3/`
  (regenerable). Everything else is needed.
- **No secrets to set before sending** — real OAuth/SMTP values go into the Substrait portal, not the repo.

## 2. Read order on the new device

1. **`CONTINUE_HERE.md`** (this file).
2. **`BUILD_HANDOFF.md`** — cross-device source of truth: decision ledger (§3), milestones (M0–M5),
   inputs table, memory export. **Where it conflicts with `PRD.md`, the handoff wins.**
3. **`UNHAPPY_FLOWS.md`** — the 09-Jul failure-path audit: every unhappy flow (real-life + in-app)
   with status + gaps + the open decision batch for Baskoro. **Read before building M2/M3.**
4. **`HANDOVER.md`** — prior transfer notes + deploy mechanism detail.
5. **`OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md`** — the OC engine spec (before touching intake).
6. **`backend/OC_M1.md`** — M1 endpoints + deploy smoke-test.
7. **`PRD.md`** (v2.1) — original spec; still to be cut to v2.2.

## 3. Where the build stands (verified live 09 Jul 2026)

- **M0 backend + M1 OC-intake backend: DEPLOYED & VERIFIED** on the public portal
  `swiperx-operator.apps.substrait.build` (dummy data only). M1 gate MET — courier links open.
- **Re-checked live today** — all happy paths green (version, dev-login, services, both intakes,
  courier link opens) **and** negative paths fail safe (401 no-session, 400 bad-service,
  422 corrupt-file, 404 bad-token, wrong-service → 0 commits). See `UNHAPPY_FLOWS.md`.
- **Next unbuilt piece:** the **React + Vite + Tailwind frontend** (M0 login/landing + M1 OC intake
  UI). It's the only major piece fully unblocked → the recommended next task.
- **Small backend gaps found today** (in `UNHAPPY_FLOWS.md`, worth folding into the frontend pass):
  B6 empty-upload guard (all-duplicate `create` still returns an empty `upload.xlsx`); B5 wrong-service
  UX hint; A10 courier-link 30-day expiry not yet enforced.
- **M2 courier wizard stays PARKED** until Baskoro's design update lands (his explicit instruction).

## 4. ⚠ Carrying the assistant's memory across devices

**The problem you flagged:** the assistant's persistent memory is **not inside this folder**. On this
device it lives at:

```
C:\Users\NXP\.claude\projects\C--Users-NXP--claudeai-SwipeRx\memory\
  MEMORY.md                       (the index, auto-loaded each session)
  swiperx-m1-deployed.md
  swiperx-deploy-api.md
  swiperx-working-conventions.md
```

The folder name `C--Users-NXP--claudeai-SwipeRx` is **derived from this machine's project path**, so
it won't match on another device, and that device has **its own separate `.claude`** with its own
memories. Uploading `SwipeRx\` alone would leave the memory behind.

**Fix — the memory is now copied into the repo** at **`_handover/memory/`** so it travels with the
upload. To merge it on the new device, pick whichever is easier:

### Option A (recommended) — let the new Claude session do it
In the new session, opened in the SwipeRx folder, just say:

> "Read `_handover/memory/*.md` and save each one into your project memory, merging `MEMORY.md`
> (append these entries to the index, don't overwrite my other projects' lines)."

Claude knows the correct memory path **for that device** and will write them there. This is the
robust choice because it doesn't depend on you knowing where that device keeps `.claude`.

### Option B — manual copy
1. On the new device, open Claude Code **once** in the SwipeRx folder (this creates that device's
   project-memory dir, e.g. `<home>\.claude\projects\<slug>\memory\`, where `<slug>` is derived from
   the new path).
2. Copy the four files from `_handover/memory/` into that dir.
3. **Merge `MEMORY.md`, don't replace it:** if the new device's `MEMORY.md` already has other
   projects' lines, append the four SwipeRx bullet lines under its `# Memory index`. If it's a fresh
   dir, copy the whole file.

### Key reassurance
**The memory is a convenience layer, not the source of truth.** Everything in those four memory files
is also captured in `BUILD_HANDOFF.md` + `UNHAPPY_FLOWS.md` + `HANDOVER.md`. If the merge is skipped
or goes wrong, **no knowledge is lost** — the repo docs stand alone. Memory just gives the next
session instant context without re-reading everything.

### About the other device's different `.claude`
- **Project memory won't collide.** Memory is namespaced per project-folder slug, so SwipeRx
  memories live in their own dir and never mix with that device's other projects.
- **A different global `CLAUDE.md` / different skills on that device don't matter** for this work —
  they're the device's own tooling. Nothing in this project depends on them.
- **Only merge the four files above.** Don't copy this device's whole `.claude` over — that would
  clobber the other device's global settings.

## 5. Deploy on the new device

- Creds in `.substrait/config.json` (portal `api.substrait.build`, slug `swiperx-operator`).
- **If the Substrait plugin is installed there:** use `/substrait:deploy`.
- **If not** (as on this device): run **`deploy.sh`** — it zips (forward-slash paths via Python
  `zipfile`), POSTs to `https://api.substrait.build/api/deploy` with the Bearer token, and polls
  `/api/version` for rollout. Details in `_handover/memory/swiperx-deploy-api.md` and HANDOVER §0.
- ⚠ **Rotate the `sbd_` token** (HANDOVER §7) if this folder's transfer channel was shared.
- **Never** put real pharmacy data on the public portal — dummy data only until NV self-hosted.

## 6. Suggested first actions on the new device (in order)

1. Merge memory (§4), then re-run the live re-check in `UNHAPPY_FLOWS.md` §A/B to confirm the deploy
   is still green from the new device.
2. **Build the React frontend** (M0 login/landing + M1 OC intake UI) — the unblocked critical path.
   Fold in the B5/B6/A10 fixes noted in §3.
3. **Send Baskoro the decision batch** at the bottom of `UNHAPPY_FLOWS.md` (10 items, his either/or
   format) — unblocks M2/M3 in parallel.
4. **Cut PRD v2.2** (content approved; add the Validator-reason fix, gap A5). Show Baskoro the diff.
5. Keep M2 parked until his design update lands.

## 7. How Baskoro works
Discussion-first; confirm before changing locked decisions; give options + a recommendation for
either/or questions. Keep the open-questions log (PRD Appendix C) current. **If you make decisions on
the new device, write them back into `BUILD_HANDOFF.md` §3** so the memory-holding machine can re-sync.

---
name: swiperx-m1-deployed
description: SwipeRx Operator M0+M1 backend is deployed & verified on the public Substrait portal (09 Jul 2026)
metadata: 
  node_type: memory
  type: project
  originSessionId: bb5aaf7e-508a-4be9-a254-9fc7790b3b8c
---

As of **09 Jul 2026**, SwipeRx Operator's **M0 foundation + M1 OC-intake backend are DEPLOYED & VERIFIED** on the public portal `swiperx-operator.apps.substrait.build` (previously built-but-not-deployed).

Verified live end-to-end: `/api/version` = Alpha 0.1 + changelog (Flyway V2/V3/V4 applied); dev-login (`dewi.k@ninjavan.co` = de+implant) mints a session; `/api/oc/services` = S1/S2/S3. Preview counts matched the expected engine numbers **exactly**: S1 57/144, S2 79/210, S3 23/23 (spot-checks AWB02S757→7, AWB02U24V→3). create→`upload.xlsx` (B=`11398423` master, AE=1/3/2 per service, R≤500 with `<updated_addr>…<a href=".../api/c/…">` link)→**courier link opens** (the prototype's dead link, now fixed), including the S3 return path (branch_id=2, invoice+item detail behind the link).

**M1 gate is MET.** Next unbuilt piece: the **React+Vite+Tailwind frontend** (M0 login/landing + M1 OC intake UI). Deploy currently ships the static HTML prototype as the frontend, so public `/` and `/health` serve that prototype — verify backend health via `/api/version`, not public `/health`.

Deploy mechanism: [[swiperx-deploy-api]]. Handover docs (`HANDOVER.md`, `BUILD_HANDOFF.md`) updated to reflect this state.

**09 Jul re-check + unhappy-flow audit done.** Re-verified live (happy + negative paths all correct: 401/400/422/404, wrong-service → 0 commits). New repo docs: **`UNHAPPY_FLOWS.md`** (every failure path + gaps + Baskoro decision batch) and **`CONTINUE_HERE.md`** (device-handover entry point). Found small backend gaps to fold into the frontend pass: empty all-duplicate `create` still emits an empty upload.xlsx (B6); wrong-service gives no UX hint (B5); courier-link 30-day expiry not enforced (A10). Memory bundled into `SwipeRx/_handover/memory/` so it travels with the folder upload (real memory dir is outside the project).

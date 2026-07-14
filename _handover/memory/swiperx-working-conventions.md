---
name: swiperx-working-conventions
description: "Standing conventions Baskoro gave for SwipeRx Operator — requirements/design churn is expected, and the courier link's driver-app module isn't to be built yet"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb5aaf7e-508a-4be9-a254-9fc7790b3b8c
---

**Requirements and design will keep changing over time (09 Jul 2026 onward).** Baskoro
said he'll update the requirement further as things change, and the design will be
updated too.
**Why:** this is an evolving product spec, not a one-shot build — treat current specs
(PRD, OC guide, BUILD_HANDOFF decision ledger) as the current snapshot, not final.
**How to apply:** don't hard-code assumptions as immutable; when a spec changes, update
the relevant doc (BUILD_HANDOFF §3 decision ledger, PRD) rather than treating old
decisions as sacred. Expect re-verification after design updates land.

**The courier link (`/api/c/<token>`) must eventually open the real driver/courier app
module — do NOT build that module yet.** Baskoro is still updating the design; keep the
M1 landing page as the placeholder and leave the M2 courier wizard build for later,
after the design update lands.
**Why:** he called this out explicitly after seeing the M1 landing page work — don't
jump ahead to M2 before the new design is ready.
**How to apply:** M1's `/api/c/<token>` HTML/JSON landing (`backend/oc.py`) stays as-is.
Do not start the phased-wizard courier capture UI (M2, [[swiperx-m1-deployed]]) until
Baskoro gives the go-ahead post-design-update.

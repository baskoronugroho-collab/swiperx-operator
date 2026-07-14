---
name: swiperx-deploy-api
description: "How to deploy SwipeRx Operator to Substrait when the plugin isn't installed — the raw portal upload API"
metadata: 
  node_type: memory
  type: reference
  originSessionId: bb5aaf7e-508a-4be9-a254-9fc7790b3b8c
---

Deploying **SwipeRx Operator** (`.claudeai/SwipeRx`) to the Substrait public portal without the Substrait plugin (it's not installed on the NXP Windows device, and the folder is not a git repo so `git archive` doesn't apply).

**Deploy API** (verified working 09 Jul 2026):
- `POST https://api.substrait.build/api/deploy`
- Header `Authorization: Bearer <token>` — token in `SwipeRx/.substrait/config.json` (`sbd_…`, slug `swiperx-operator`, host `swiperx-operator.apps.substrait.build`).
- multipart form field **`file`** = a **forward-slash `.zip`** of the source (`backend/`, `cicd/`, `frontend/` at zip root; build it with Python `zipfile` to avoid Windows backslash paths). Zip ~75KB, well under the 16MB cap.
- Returns `202 {"project":{…},"run_id":<int>}`.

The `sbd_` token is **deploy-scoped (POST /api/deploy only)** — it 401s on `GET /api/runs/{id}` (that needs a portal user session). So **watch rollout by polling the app's own `/api/version`** until it returns the Alpha 0.1 changelog (was 404 on the old scaffold). Rollout is fast (~seconds to a couple min).

Runnable script: **`SwipeRx/deploy.sh`** (recreated 09 Jul) does zip→POST→poll. Uses anaconda python `C:/Users/NXP/anaconda3/python.exe` (system `python` is the Windows Store stub; no `zip`/no standalone Python on PATH). See [[swiperx-m1-deployed]].

⚠ The live token was used from this device — rotate it if the folder's transfer channel was shared (HANDOVER §7).

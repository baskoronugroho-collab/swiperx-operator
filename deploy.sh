#!/usr/bin/env bash
# Recreated deploy.sh (09 Jul 2026) — packages the app source and uploads it to the
# Substrait portal's upload-mode deploy API. Replaces the missing script the handover
# kept referencing, and encodes the API the (uninstalled) Substrait plugin wraps.
#
# Why not the stock plugin / git archive?
#   - The Substrait plugin is NOT installed on this device (it lives in an NV-internal
#     marketplace). The stock /substrait:deploy also fails on Windows (no `zip`).
#   - This folder is not a git repo, so `git archive` doesn't apply either.
#   - Instead we build a proper forward-slash .zip with Python's zipfile (avoids the
#     backslash-path zips Windows tooling produces) and POST it to the deploy API.
#
# Deploy API (discovered from the live portal, confirmed working 09 Jul 2026):
#   POST https://api.substrait.build/api/deploy
#     Authorization: Bearer <token from .substrait/config.json>
#     multipart form field `file` = the source .zip
#   -> 202 Accepted {"project":{...}, "run_id":<int>}
#   The `sbd_` token is DEPLOY-SCOPED (POST /api/deploy only). It does NOT authorize the
#   portal's GET /api/runs/{id} status endpoint (that needs a portal user session / 401),
#   so we watch the rollout by polling the app's own /api/version instead.
#
# Requirements on this machine: bash, curl, and a Python (anaconda at the path below).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-C:/Users/NXP/anaconda3/python.exe}"
CFG="$ROOT/.substrait/config.json"
ZIP="${ZIP:-$ROOT/.deploy.zip}"

TOKEN=$("$PYTHON" -c "import json;print(json.load(open(r'$CFG'))['token'])")
PORTAL=$("$PYTHON" -c "import json;print(json.load(open(r'$CFG')).get('portal_url','https://api.substrait.build'))")
HOST=$("$PYTHON" -c "import json;print('https://'+json.load(open(r'$CFG'))['host'])")

echo "Packaging source -> $ZIP"
"$PYTHON" - "$ROOT" "$ZIP" <<'PY'
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
INCLUDE = ["backend", "cicd", "frontend"]           # frontend/ = static prototype (served by nginx, no build)
SKIP_DIRS = {"__pycache__", "node_modules", ".venv", ".git", "dist", "build", ".pytest_cache"}
SKIP_EXT = {".pyc", ".pyo"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for top in INCLUDE:
        for dp, dn, fn in os.walk(os.path.join(root, top)):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in fn:
                if os.path.splitext(f)[1].lower() in SKIP_EXT:
                    continue
                full = os.path.join(dp, f)
                z.write(full, os.path.relpath(full, root).replace(os.sep, "/"))
print("  zip bytes:", os.path.getsize(out))
PY

echo "Uploading to $PORTAL/api/deploy"
RESP=$(curl -s -m 180 -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@${ZIP};type=application/zip;filename=deploy.zip" "$PORTAL/api/deploy")
echo "  $RESP"
RUN_ID=$("$PYTHON" -c "import json,sys;print(json.loads(sys.argv[1]).get('run_id','?'))" "$RESP")
echo "  run_id: $RUN_ID"

echo "Watching rollout via $HOST/api/version ..."
for i in $(seq 1 40); do
  if curl -s -m 15 "$HOST/api/version" | grep -q '"changelog"'; then
    echo "  LIVE at $(date +%H:%M:%S)"; exit 0
  fi
  sleep 15
done
echo "  timed out waiting for rollout (build may still be running)"; exit 1

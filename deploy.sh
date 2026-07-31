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
# git-bash reports /c/Users/… which a Windows python cannot open. Convert once, here,
# so every path handed to $PYTHON below is native. (26 Jul 2026)
if command -v cygpath >/dev/null 2>&1; then
  ROOT="$(cygpath -m "$ROOT")"
fi
# Resolve a Python: explicit $PYTHON wins, else whatever is on PATH, else the anaconda
# path the original handover device used. (Was hardcoded to that device — 26 Jul 2026.)
if [ -z "${PYTHON:-}" ]; then
  if command -v python >/dev/null 2>&1;  then PYTHON="python"
  elif command -v python3 >/dev/null 2>&1; then PYTHON="python3"
  else PYTHON="C:/Users/NXP/anaconda3/python.exe"
  fi
fi
CFG="$ROOT/.substrait/config.json"
ZIP="${ZIP:-$ROOT/.deploy.zip}"

TOKEN=$("$PYTHON" -c "import json;print(json.load(open(r'$CFG'))['token'])")
PORTAL=$("$PYTHON" -c "import json;print(json.load(open(r'$CFG')).get('portal_url','https://api.substrait.build'))")
HOST=$("$PYTHON" -c "import json;print('https://'+json.load(open(r'$CFG'))['host'])")

echo "Packaging source -> $ZIP"
"$PYTHON" - "$ROOT" "$ZIP" <<'PY'
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
# Source only (platform contract): the frontend image builds the bundle itself.
# substrait.yaml is REQUIRED at the repo root — uploads without it are rejected.
INCLUDE = ["backend", "cicd", "frontend"]
ROOT_FILES = ["substrait.yaml"]
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
    for f in ROOT_FILES:
        full = os.path.join(root, f)
        if not os.path.exists(full):
            raise SystemExit(f"FATAL: {f} is required at the repo root — the platform rejects uploads without it.")
        z.write(full, f)
print("  zip bytes:", os.path.getsize(out))
PY

echo "Uploading to $PORTAL/api/deploy"
RESP=$(curl -s -m 180 -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@${ZIP};type=application/zip;filename=deploy.zip" "$PORTAL/api/deploy")
echo "  $RESP"
RUN_ID=$("$PYTHON" -c "import json,sys;print(json.loads(sys.argv[1]).get('run_id','?'))" "$RESP" 2>/dev/null || echo '?')
# Fail fast on a rejected upload. Without this the script polls for the full 15 minutes
# on a response that already said "no" — which is exactly how three deploys burnt 45
# minutes hiding a one-line `substrait.yaml is required` rejection. (26 Jul 2026)
if [ "$RUN_ID" = "?" ]; then
  echo "  UPLOAD REJECTED — the platform did not start a build:"
  echo "  $RESP"
  exit 2
fi
echo "  run_id: $RUN_ID"

# The host now sits behind Substrait's platform SSO gateway, which allowlists only
# /c/* and /api/c/* — every other path (including /api/version) returns 401 from the
# gateway, so the old watcher could never match and always "timed out". Poll an
# allowlisted courier route instead: since 26 Jul the backend answers GET
# /api/c/<token> with a 307 to /c/<token>; the pre-26-Jul build returned 200 HTML.
#
# Budget: successful builds on this app have taken 34–57s (portal history); the one
# outlier was 5m22s on first provision. Validation failures fail in ~1s but are only
# visible in the portal — the deploy token can't read run status — so a watcher that
# waits much beyond the build time just delays asking the human. 6 min is plenty.
# Probe: compare the EXACT bundle filename. Vite hashes it from content, so building
# locally yields the same name the image will produce — an exact "is my code live?" test.
# (Matching only the /c/assets/ prefix was a false positive: the previous build already
# used that path, so the watcher reported LIVE while the old bundle was still served.)
echo "Computing expected bundle hash (local build) ..."
( cd "$ROOT/frontend" && npm run build >/dev/null 2>&1 ) || {
  echo "  local build failed — cannot compute the expected hash"; exit 3; }
EXPECT=$(grep -o '/c/assets/index-[A-Za-z0-9_-]*\.js' "$ROOT/frontend/dist/index.html" | head -1)
echo "  expecting $EXPECT"

echo "Watching rollout via $HOST/c/ (SSO-exempt) ..."
for i in $(seq 1 24); do
  BODY=$(curl -s -m 15 "$HOST/c/probe" || true)
  # Both must flip: the shell serves the new bundle AND the backend answers correctly.
  # The two roll out independently — mid-rollout the API briefly 500s.
  API=$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$HOST/api/c/__probe__/order")
  if printf '%s' "$BODY" | grep -q -- "$EXPECT" && [ "$API" = "404" ]; then
    echo "  LIVE at $(date +%H:%M:%S) — $EXPECT, API healthy"; exit 0
  fi
  sleep 15
done
CODE="expected $EXPECT; API last returned $API"
echo "  NOT LIVE after 6 min (HTTP $CODE — still the previous build)."
echo "  A run that fails validation dies in ~1s and the reason exists ONLY in the portal"
echo "  (the sbd_ token is deploy-scoped — GET /api/runs/<id> returns 401)."
echo "  ACTION: open run $RUN_ID in the portal and read the failure message."
exit 1

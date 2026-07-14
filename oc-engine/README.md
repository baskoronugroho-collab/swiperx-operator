# OC Engine — Local Trial Harness

Standalone Node CLI that validates the SwipeRx **order-creation transform** (TMP batch → Ninja Van
upload) before it is ported into the FastAPI backend. Pure logic, no DB/auth. Rules per
`../OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md`; extracted fixed values + open GAPs in
[`EXTRACTION_NOTES.md`](EXTRACTION_NOTES.md).

## Run

Node v24 is at `C:\Users\NXP\Documents\NXP\node.exe` on this machine. Pass Windows paths with
forward slashes (git-bash `/c/…` paths get mangled).

```sh
NODE="C:/Users/NXP/Documents/NXP/node.exe"
"$NODE" oc-engine.mjs --in "<TMP.xlsx>" --service S1|S2|S3 [--out <dir>] [--base-url <host>]
```

- `--service S1` = Regular · `S2` = Sameday/Instant · `S3` = Return Pickup.
- Writes to `<dir>` (default `./out`): `upload.csv`, `links.csv`, `summary.json`.

## What it does
1. Picks the service up front → fixes branch_id (AE), service_level (E), fixed fields, and the source layout.
2. Reads the TMP, skips header rows, groups by SwipeAWB (forward) / return AWB (S3).
3. Validates rows (per-row error report); MPS-expands **per AWB** (base = SwipeAWB, children `-1…-N`, N = Σ collies).
4. Builds the NV upload columns (B = master `11398423`, AE = branch, W = real weight, Y = PO/collie cross-check).
5. Appends the courier link to col R as `<updated_addr>… <a href="{URL}">{URL}</a></updated_addr>`, capped at 500 chars.
   Forward R = fixed RDO text + link. **Return R = short "MUST open the link" text + link**; the full item
   list + invoice ride in `links.csv` (courier-app payload), never crammed into R.
6. Emits `links.csv` (AWB → token URL, plus `invoice`/`item_detail` for returns) with `crypto.randomUUID()` stub tokens.

Note: **hub is NOT derived here** — it's assigned by NV and re-uploaded in a second flow (EXTRACTION_NOTES §C).

## Verified against the real samples (07 Jul 2026)
- **S1**: 57 AWBs → 144 collie rows; `AWB02S757` correctly expands to 7 pieces; W = real weight (16.1, not the hardcoded-1 bug); R = 419/500.
- **S2**: 79 AWBs → 210 pieces (different Sameday layout: koli in col W, address/zip/city/phone at M/N/O/P; `AWB02U24V`→3 collies).
- **S3**: 23 return AWBs; R = fixed 306-char must-open-link instruction (no truncation); full detail in `links.csv`; pickup instructions in AJ; branch=2.

## Not covered here (backend port only)
DB persistence, auth, real tokens, real `.xlsx` output with array formulas, and the real hub map.

## Layout / files
- `oc-engine.mjs` — CLI + transform.
- `config.json` — fixed fields, per-service branch/level, per-layout source-column maps, char limit.
- `lib/xlsx-read.mjs` — dependency-free XLSX reader.
- `out-S1/`, `out-S2/`, `out-S3/` — sample outputs from the three real TMPs.

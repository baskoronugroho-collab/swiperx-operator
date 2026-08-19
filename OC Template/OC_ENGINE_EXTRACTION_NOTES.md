# OC Engine — Extraction Notes & Open GAPs

> Written **07 Jul 2026**. Records the exact values extracted from the real templates in
> `../OC Template/` (HANDOVER §4.A) and the gaps found while building the local-trial engine
> (HANDOVER §4.B). These feed `config.json`. Diff-source samples: the two `[Template DE FWD]`
> uploads, the `[Template DE PU Return]`, and the three `[Template Swipe …]` TMP batches.

## A. Extracted fixed values (now in config.json)

### A1 — Fixed RDO / instruction text per movement

**Forward (S1 Regular & S2 Sameday) — `parcel_job.delivery_instructions` (col R), IDENTICAL for both, 214 chars:**
```
Dokumen Faktur, Tanda Terima Faktur (TTF), dan Surat Pesanan (SP) wajib ada nama penerima, ditandatangani dan distempel penerima. Jika di label tertera "SP Manual", maka dokumen SP Manual harus diminta ke penerima.
```
*(Note: the guide paraphrased this as "TTTF"; the real label is **TTF** = Tanda Terima Faktur. The real sample R has NO link — the engine appends it.)*

> **UPDATED 09 Jul 2026 (Baskoro):** the extracted text above is the historical source
> value; the **live `rdo_text.forward` in `config.json` / `oc_config.json` has been
> reworded** ("Semua dokumen..." + "Silahkan selesaikan delivery melalui link berikut:")
> and the anchor now attaches directly with no space after the colon. See
> `config.json`'s `_forward_comment`.

**Return (S3) — two instruction fields:**
- `parcel_job.delivery_instructions` (col R): **per-row** = item detail (already carries the invoice) + fixed suffix `Tarik Barang Retur & Wajib bawa BA retur`. Data-driven, not fixed.
- `parcel_job.pickup_instructions` (col AJ): **FIXED**, 154 chars:
```
Pickup Return, wajib bawa form BA Return. Bilang ke Apotek "mau tarik barang". Jika tidak ada barang, tulis keterangan "tidak ada barang retur" di form BA
```
*(The "mau tarik barang" / "tidak ada barang retur" quotes use curly quotes “ ” in the source; preserved verbatim in config.)*

### A2 — WH origin (F/G/H) + return WH destination (J/K/L + N/O/P/Q)

**SwipeRx warehouse (forward `from.*`; return `to.*`):**
| Field | Value |
|---|---|
| name | `PT Teknologi Medika Pratama (SwipeRx) (B2BR)` |
| phone | `087733785699` |
| address1 | `Jl. Tugu Raya, Tugu, Kec. Cimanggis, Kota Depok, Jawa Barat 16451,KUBIK LOGISTICS - Kompleks Pergudangan,Gudang E1` |
| kecamatan / city / province / postcode | `Cimanggis` / `Depok` / `Jawa barat` / `16451` |

*(The Sameday sample appended a batch tag ` KD5` to the address — treated as a per-batch artefact, not stored. The Bible notes origin may differ per WH; only one WH appears in all samples.)*

### A2 — Full S3 (Return Pickup) column map A–AJ

Confirmed from `[Template DE PU Return]`. Reverse job: `from`=pharmacy, `to`=WH. Extends the forward
A–AE with pickup fields AF–AJ:
`AF pickup_date · AG pickup start 09:00 · AH pickup end 22:00 · AI Asia/Jakarta · AJ` = the fixed pickup instruction above.
`D reference.merchant_order_number` = the **PO Number** (not the AWBR). `A` = return AWB + `-01`. `X is_pickup_required` = TRUE. `Y item_description` = `OBAT`.

---

## B. GAPs found while building — Baskoro's rulings (07 Jul)

### GAP-1 — S3 branch_id — ✅ RESOLVED: keep **AE = 2** (RTS `11398434`, per guide)
Every row of the real `[Template DE PU Return]` sample used AE=1, but **Baskoro confirmed 2 is correct**
(the sample's 1 was a fill error). `config.json` stays at 2.

### GAP-2 — Regular vs Sameday TMP layouts DIFFER — ✅ RESOLVED
The guide §1.3 claimed S1 and S2 "share the same template shape." **They do not.** The real Sameday TMP
inserts per-PO **Weight (G)** and **Volume (H)** columns → address/zip/city/phone shift from J/K/L/M to
**M/N/O/P**, and **koli (bundle_information.total_quantity) is in col W**. Otherwise the row structure is the
SAME as Regular: each row = one PO line with a koli **count**; AWB collies = Σ koli; grouped by SwipeAWB
(carry-forward). Config `source_layouts.forward_sameday` = `koli_mode:count`, `cols.koli:W`.

> **Parser bug found & fixed (07 Jul):** the dependency-free XLSX reader was silently dropping any valued
> cell that immediately followed a self-closing empty cell (e.g. `<c r="V5"/><c r="W5"><v>1</v></c>` — V5
> stole W5's value, W5 vanished). That's why W first looked "empty." Root cause: the cell regex's open-tag
> alternative `[^>]*` swallowed the `/` of the self-closing tag. Fixed by trying the self-closing
> alternative first, in both `oc-engine/lib/xlsx-read.mjs` and `tools/xlsx.js`. Baskoro confirmed koli is on
> W; the parser now reads it (W=1 per PO line; `AWB02U24V` → 3 collies, matching its 3 per-PO weights).

### GAP-3 — Return R over 500 chars — ✅ RESOLVED: R must send the courier to the link
Per Baskoro: don't cram the (variable-length) item list into R. R now carries a **short fixed instruction
that the courier MUST open the link** (`return_delivery_short`), and the full item detail + invoice ride in
the courier-app payload (`links.csv` `item_detail`/`invoice` columns). R is now a fixed ~306 chars, no
truncation. Forward keeps its fixed 214-char RDO (→419 with link).

---

## C. Hub assignment — ✅ RESOLVED: NV assigns the hub; a **second upload flow** (not L2→hub in our engine)
Baskoro's ruling: **the engine does NOT derive the hub.** The real flow is a round-trip with NV's system:

1. Implant uploads the **OC template** (our `upload.csv` / the real `.xlsx`) into NV's Operator system.
2. **NV creates the OC and assigns each AWB a destination hub.**
3. Implant **downloads the hub assignment** back from NV.
4. Implant **re-uploads a second file** into a *different* NV upload section: columns =
   **[Ninja Van AWB] + [destination hub code]**.
   - Hub codes are `xxx-xxx` format, e.g. **`MAC-CP5`**, **`SRG-KDL`**.

**Implications for the build:**
- Drop the L2/postcode→hub derivation and the dummy hub map from engine scope.
- The `Mapping Area` (City→`GJ` zone) and `Mapping L2` sheets in the return file are **not** the hub source — ignore for hub assignment.
- Add a **hub-assignment upload** stage to the intake feature: after OC creation, accept the NV hub download and emit the AWB+hub-code file for re-upload.

**Sample received — `../OC Template/AWB-hub assignment.csv`** (9,055 rows). Columns:
`Shipper ID, Tracking ID, Origin Hub Name, Dest Hub Name, Count`.
- **Tracking ID** = NV's per-piece TRID, e.g. `26062603190507YMXN8GUVV-01` (parcel) and `…-DO` (the RDO
  **document** piece NV auto-creates because `documents_required=RDO`). So each PO shows up as a `-01` (+`-02…`)
  **and** a `-DO` row.
- **Dest Hub Name** = the assigned hub, `XXX-YYY` format: region prefix + hub, e.g. `MAC-KD5`, `MAC-SRN`,
  `SUB-TBN`, `MAC-CLG` (MAC≈Makassar area, SUB≈Surabaya). **Origin Hub** likewise.
- **Shipper ID** = the branch shipper (e.g. `11398224` Regular), not the master.
- Notes for the build: (1) the `-DO` pieces are **NV-side**, not in our upload — don't generate them; expect
  them in the download. (2) This download uses NV's tracking IDs; the AWB+hub re-upload is therefore a
  round-trip on NV's data (we can't pre-compute hubs). (3) The sample's Tracking IDs are PO-based `-01/-DO`
  (an older per-PO upload); with our per-AWB MPS they'd be SwipeAWB-based — ~~confirm the re-upload keys
  on the piece TRID vs the AWB~~ **RESOLVED 09 Jul (Baskoro): keys on the AWB naming system** (not the
  piece TRID); build the hub-assignment stage only after the AWB naming scheme is team-confirmed.

---

## D. Still stubbed for the local trial
- **SP-Manual flag** — not in data (rider reads Faktur at door); courier capture stays rider-driven.
- **Courier tokens** — `crypto.randomUUID()` (hex, 32 chars); real unguessable tokens come from the backend.
- **Hub** — now NV-assigned (see §C); no engine stub needed.

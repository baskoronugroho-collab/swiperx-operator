# SwipeRx OC Template & Intake-Engine Guide

> **What this is:** the authoritative, build-ready guide for the SwipeRx Operator **order-creation (OC) engine** — how the app ingests the SwipeRx batch file, expands it, injects the courier link, and produces the Ninja Van upload file, for all **three movements**. It recaps and extends the *SwipeRX Operational Bible (OC Guide v0.3, Jun 2026)* (which only covered Movement 1 / Regular), adding Movement 2 (Instant) and Movement 3 (Return Pickup) from the real templates in this folder.
>
> Read this **before** building the intake engine. Source files analysed: the two forward TMP batches, the two DE FWD upload files, the two return-pickup files, and the Bible docx.
> Written 03 Jul 2026. Owner: Baskoro / DE-Implant.

---

## 0. The core mental model (read this first — it changes the data model)

The single most important correction from the real data:

| Term | What it *actually* is | Not what we assumed |
|---|---|---|
| **SwipeAWB** | SwipeRx's own order number, e.g. `AWB02S5X7`. **One per pharmacy order / delivery visit.** Becomes NV's `merchant_order_number` (shipper reference). **This is what the courier link is scoped to** (one DN per SwipeAWB). | *not* `NVIDMY…` |
| **PO Number** | A long code, e.g. `26060908042940Pt0L9chLQ`. SwipeRx's internal purchase-order id, one per PO line. **No longer the TRID base** — the TRID base is now the SwipeAWB (§2.3). Still used for the col-Y PO/collie cross-check. | *not* a short human `PO-2401` |
| **Koli** | Number of parcels (collies) **per PO line** (TMP col N). | — |
| **TRID / MPS piece** | Per-parcel tracking number. **MPS bundles per AWB**: parent (col A) = SwipeAWB; children are **PO-prefixed**, one per collie, numbered continuously across the AWB and zero-padded — see §2.3. | *not* per-PO bundles |
| **SP type (Manual/Electronic)** | **NOT present anywhere in the batch data.** The rider identifies it by reading the **Faktur at the door** (Bible Open Item #4). | *not* a per-PO column we can pre-count |

**Structure:** `SwipeAWB` → many `PO lines` → each PO line has `Koli` parcels.
So **AWB total koli = sum of its PO-line kolis** (this resolves the earlier open koli question — it's per-PO, summed).

**L2 (kota/kabupaten)** = the source **City** column (`Kabupaten Pandeglang`, `Kota Serang`). That's the finest geography we get — used for report grouping and as the basis for hub assignment.

**Hub code is still NOT in the file** — the finest geo is L2 + postcode. Hub must be derived (L2/postcode → hub mapping) or read back from NV after upload. Still open (§8).

---

## 1. The three movements & the shipper/branch model

### 1.1 Shipper IDs — master + branch (IMPORTANT, corrected 03 Jul)

There is **one master shipper ID** and three sub-accounts ("branches"). **The OC upload ALWAYS puts the master ID `11398423` in `global_shipper_id` (col B).** The actual service is selected by the **branch id in `corporate.branch_id` (col AE)** — *not* by col B.

| Shipper ID | Account | Movement | Branch id (col AE) |
|---|---|---|---|
| **11398423** | PT Teknologi Medika Pratama (B2BR) | **MASTER — always in col B** | — |
| 11398224 | …HW (B2BR) | Regular (S1) | **1** (default child if AE blank) |
| 11398434 | …HW – RTS Account (B2BR) | Return Pickup (S3) | **2** |
| 11549046 | …Sameday CTM (B2BR) | Instant / Sameday (S2) | **3** |

> Using master `11398423` with no branch defaults to child 1 (Regular). So the engine must **always set col B = 11398423** and **set col AE to the branch of the chosen service (1/2/3)**. (This also retracts the earlier "wrong shipper" note — `11398423` in the samples was correct: it's the master.)

### 1.2 The movements

| # | Service | branch (AE) | service_level (E) | Direction | Return AWB | Source / Upload files |
|---|---|---|---|---|---|---|
| **1 — Regular (S1)** | Ninja Express Intercity | **1** | `STANDARD` | Forward (WH → pharmacy) | Created by DE *after* a reject | `[Template Swipe Fwd Reg] …` / `[Template DE FWD] SWIPE UPLOAD …` |
| **2 — Instant / Sameday (S2)** | Sameday CTM | **3** | `SAMEDAY` | Forward (WH → pharmacy) | Created by DE *after* a reject | `[Template Swipe FWD Sameday] …` / `[Template DE FWD] SAMEDAY …` |
| **3 — Return Pickup (S3)** | RTS Account | **2** | `STANDARD` | Reverse (pharmacy → SwipeRx WH) | **Pre-supplied by SwipeRx** (`AWBR-…`) | `[Template Swipe PU Return] …` / `[Template DE PU Return] …` |

### 1.3 S1 vs S2 — where they actually differ (verified from the files)

Movements 1 & 2 share the **same template shape**. Concrete differences found:
1. **`service_level` (col E):** `STANDARD` (S1) vs **`SAMEDAY`** (S2).
2. **`branch_id` (col AE):** `1` (S1) vs `3` (S2).
3. Origin WH (F/G/H) was the **same** (Depok / Cimanggis) in both samples — the Bible notes it *may* differ per WH, but it does not in these files.
4. Timeslot 09:00–22:00 in both (S2 end-time is stored as the fraction `0.9166…` = 22:00 — a formatting artefact, same value).

Movement 3 is a different shape (reverse logistics — from = pharmacy, to = WH).

---

## 2. Movement 1 & 2 — Forward: full column mapping

### 2.1 Source: TMP Batch Order (what SwipeRx sends)

One row **per pharmacy order per PO line**. The file has **3 header rows** the engine must skip:
`Row 2` = NV target field · `Row 3` = explanation · `Row 4` = original SwipeRx label · **`Row 5+` = data**.

| TMP col | SwipeRx label | Meaning | Used as |
|---|---|---|---|
| B | Pharmacy Name | Destination pharmacy | → upload `to.name` |
| C | **SwipeAWB** | SwipeRx order number | → `merchant_order_number` (**AWB grouping key**) |
| D | Total Weight per AWB (kg) | Actual weight | → `weight` (see W bug) |
| F | **PO Number** | SwipeRx PO id (long code) | → `po_line` + col-Y cross-check only. **Never a tracking number** (§2.3) |
| G | Pharmacy's ID | Numeric pharmacy id | prepended to address |
| J | Pharmacy's ID - Address | Full formatted address | → `to.address.address1` |
| K | Zip Code | Postcode | → `postcode` |
| L | **City** | **L2 (kabupaten/kota)** | → `to.address.city` |
| M | Phone | Pharmacy phone | → `to.phone_number` |
| N | **Koli** | Parcels for this PO line | → MPS piece count |
| A, E, H, I | (row idx, volume, note, picking priority) | not used for upload | — |

### 2.2 Target: Ninja Van upload template — column lock status

One row **per TRID** (MPS expands one PO with Koli>1 into multiple rows). Legend: 🔒 **Locked** (fixed, do not edit) · 📄 **From TMP** · 🧮 **Computed/rule** · ⚠️ **GAP/bug**.

| Col | Field | Lock | Value / rule |
|---|---|---|---|
| A | requested_tracking_number | 🧮 | **SwipeAWB** (total=1) or `SwipeAWB-1`,`-2`,… per collie — see §2.3 |
| B | global_shipper_id | 🔒 | **Always master `11398423`** — service is chosen via branch (AE), not here |
| C | service_type | 🔒 | `Corporate B2B Bundle` |
| D | reference.merchant_order_number | 📄 | = SwipeAWB (TMP C). All MPS pieces of the AWB share it |
| E | service_level | 🔒 | `STANDARD` (S1 & S3) · **`SAMEDAY`** (S2) |
| F | from.name | 🔒 | SwipeRx WH — `PT Teknologi Medika Pratama (SwipeRx) (B2BR)` (update per WH) |
| G | from.phone_number | 🔒 | `087733785699` (per WH) |
| H | from.address.address1 | 🔒 | WH address (Depok / Kubik Logistics) (per WH) |
| I | from.address.country | 🔒 | `ID` |
| J | to.name | 📄 | = Pharmacy Name (TMP B) |
| K | to.phone_number | 📄 | = Phone (TMP M) |
| L | to.address.address1 | 📄 | = Pharmacy's ID-Address (TMP J) |
| M | to.address.country | 🔒 | `ID` |
| N | to.address.kecamatan | 🔒 | **blank** — NV auto-fills from postcode+city |
| O | to.address.city | 📄 | = City / L2 (TMP L) |
| P | to.address.province | 🔒 | **blank** — NV auto-fills |
| Q | to.address.postcode | 📄 | = Zip (TMP K) |
| **R** | **parcel_job.delivery_instructions** | 🔒→✏️ | Fixed RDO text (collect Faktur, TTTF, SP Manual if on label) + **the courier link appended as an HTML hyperlink**. **Max 500 chars** (see §2.4) |
| S | delivery_start_date | ✏️ | = today (YYYY-MM-DD); update daily |
| T | delivery_timeslot.start_time | 🔒 | `09:00` |
| U | delivery_timeslot.end_time | 🔒 | `22:00` |
| V | delivery_timeslot.timezone | 🔒 | `Asia/Jakarta` |
| W | dimensions.weight | 📄 | **= TMP col D** (actual weight per AWB). *Some sample files hardcode `1` — the engine must read TMP D, not copy the bug* |
| X | is_pickup_required | 🔒 | `FALSE` (DE stages at WH) |
| Y | items.0.item_description | 🧮 | **PO list + total collies, for the courier to cross-check at the door** — e.g. `PO1 (3), PO2 (2) — 5 koli` |
| Z | items.0.is_dangerous_good | 🔒 | `FALSE` |
| AA | b2b.documents_required | 🔒 | `RDO` (triggers NV's RDO chain) |
| AB | bundle_information.total_quantity | 🧮 | AWB total collies (Σ PO koli) — drives AC |
| AC | requested_piece_tracking_numbers | 🔒🧮 | list of all piece TRIDs in the AWB bundle — computed (see §2.3); in Excel it's an array formula, don't hand-edit |
| AD | insured_value | 🔒 | `0` |
| AE | **corporate.branch_id** | 🔒 | **The service selector** — `1` Regular (→11398224) · `2` Return-Pickup RTS (→11398434) · `3` Instant/Sameday (→11549046) |

### 2.3 MPS expansion — **per AWB** (rev. 10 Aug 2026)

> MPS is bundled **per AWB**, not per PO line. All PO lines under one SwipeAWB roll up into
> **one MPS bundle** = **one upload row** = **one DN** = **one courier link**.

```
for each AWB (group of TMP rows sharing the same SwipeAWB):
    total = sum(Koli of all PO lines in the AWB)     # e.g. PO1(3)+PO2(2) = 5
    A  (requested_tracking_number) = SwipeAWB        # the bundle's own TRID
    D  (merchant_order_number)     = SwipeAWB
    AB (total_quantity)            = total
    AC (piece tracking numbers)    = one child per collie, prefixed with ITS OWN PO Number,
                                     numbered continuously across the AWB, zero-padded to 2
    W  (weight)                    = the AWB total (TMP col C), because 1 row = 1 AWB
    emit exactly ONE upload row per AWB
```

Example: `AWB12340`, PO1=3 + PO2=2 collies → `AB = 5`,
`AC = PO1-01, PO1-02, PO1-03, PO2-04, PO2-05`.

Notes:
- **Children are PO-prefixed**, and this is deliberate. NV permits custom piece ids, and the
  pieces still attach to their parent when the order is created from the **manual template**
  (confirmed by Baskoro, 10 and 18 Aug 2026). It is what lets the per-PO RDO / SP-Manual check
  work at the door.
- **Zero-padded to two digits**, and the counter runs **across the whole AWB** — it does not
  restart per PO. A multi-koli PO therefore shifts every ordinal after it.
- **Col A stays the SwipeAWB** even though the children carry PO prefixes. One bundle per AWB
  ⇒ **one DN and one courier link per AWB**.

> **History — read before "fixing" this.**
> 1. Until 27 Jul the engine emitted **one upload row per collie**, so N orders each claimed to
>    be a bundle of N. That was a genuine bug and is fixed.
> 2. On 10 Aug 2026 the children were switched to **parent-prefixed** (`<A>-01…`), on the basis
>    that 1035/1035 children in three accepted **bulk** uploads used prefix == col A. That
>    inference was wrong — it treated a property of the bulk-upload path as a universal rule,
>    while this account creates orders from the **manual template**, which accepts PO prefixes.
>    Reverted in the engine, and in the converter by **v6**. Converter **v5 is superseded** and
>    should not be used: besides the prefix, it reintroduced a fill-down formula that silently
>    breaks on Google Sheets import.
>
> Pinned by `backend/tests/test_oc_engine.py::test_children_are_po_prefixed_and_numbered_continuously`.

### 2.4 Link injection (clickable hyperlink, 500-char budget)

The courier link goes into column R (delivery_instructions) as a clickable HTML hyperlink. **FINAL template (Baskoro, 26 Aug 2026): the mandated wording leads as plain text OUTSIDE the wrapper; only the anchor is wrapped, and the WHOLE retur sentence plus the visible URL is the anchor text** — the entire call-to-action is one big tap target, not a bare URL the courier must aim for:

```
{mandated RDO wording} <updated_addr><a href="{URL}">Apabila ada retur, catat di Delivery Note dan buka link berikut: {URL}</a></updated_addr>
```

where `{URL}` = `https://{PUBLIC_BASE_URL}/c/{token}` (per AWB).

- **Anchor text = the exact URL** (link text and href are identical).
- **500-character limit** on the field: `{RDO text}` + the URL **twice** (href + visible text) + the wrapper/anchor tags must fit in 500. A ~60-char URL costs ~120 for the pair, so keep the fixed RDO text ≤ ~360 chars.
- The link is **per AWB** — the same hyperlink appears on every child row of the AWB.

The Implant then downloads this file and uploads it into NV's Operator system.

---

## 3. Movement 3 — Return Pickup (S3): full mapping

Structurally different: a **reverse** job. `from` = pharmacy (pickup), `to` = SwipeRx WH. The **return AWB is pre-supplied by SwipeRx** (`AWBR-3320011200`), so **DE does not create it** — DE only formats + uploads. The courier **brings a BA Return form** (delivery instruction says "wajib bawa form BA Return").

### 3.1 Source: TMP Batch Special Case (SwipeRx-sent return list)

3 header rows again (`R1` target · `R2` explanation · `R3` original label · `R4+` data).

| Col | Label | Meaning |
|---|---|---|
| A | pharmacy_id | Pharmacy numeric id |
| C | pharmacy_name | Pharmacy to pick up from |
| **D** | airway bill return | **Return AWB, pre-supplied** (`AWBR-…`) |
| G | Po Number | tracking code |
| **H** | INV Number | **Invoice number** (`TMP-INV-2026/06/12/ 2847208`) |
| I | Detail Barang / Full Return | item detail / full-return text → delivery instruction |
| J | Remarks | e.g. `Tarik Barang Retur` (special-case type) |
| K | Qty | quantity (often `-`) |
| L | Address | pharmacy address |
| **M** | City | **L2 (kabupaten/kota)** |
| N | Email | pharmacy email |
| O | Phone | pharmacy phone |
| P | 3PL Service | `Ninja` |

### 3.2 Target: DE PU Return upload

Key differences from forward (cols A–AJ): `A requested_tracking_number` = the return AWB reformatted (`AWBR-10909-2026-5-16`), `B` = **11398423**, `F from.name` = pharmacy, `J to.name` = `PT Teknologi Medika Pratama (SwipeRx)` (WH), `N/O/P` = WH kecamatan/city/province (Cimanggis/Depok/Jawa barat), `R`/`AJ delivery_instructions` = invoice + item detail + **"Pickup Return, wajib bawa form BA Return…"**, `AC` = piece tracking. Invoice number flows through for cross-checking.

> Movement 3 is **its own intake + delivery flow**, not a continuation of a forward reject. (Forward rejects on S1/S2 spawn a *DE-created* return AWB; S3 pickups arrive as a scheduled batch with the AWB already assigned.)

---

## 4. Locked vs editable — the rule the UI must enforce

- **🔒 Locked / config** — `B` always master `11398423`; `AE` = branch per chosen service (1/2/3); `E` = STANDARD/SAMEDAY per service; plus C, F, G, H, I, M, N, P, T, U, V, X, Z, AA, AD. Set from **config**, not editable row-by-row. `F/G/H` configurable per origin WH.
- **📄 From TMP** (D, J, K, L, O, Q, W): mapped 1:1 from the source file. The only truly data-driven fields.
- **🧮 Computed**: `A/AB/AC` (per-AWB MPS), and `Y` (PO list + total collies for courier cross-check).
- **✏️ Editable per run**: S (delivery date = today), and **R gets the hyperlink appended** (≤500 chars total).
- **Header rows** in the source (rows 2–4 forward; 1–3 return) are structural — **skip on read**.

In the web app there is **no spreadsheet to hand-edit** — the engine applies these rules programmatically. "Locked" becomes "set by config, not exposed for editing"; "from TMP" becomes "parsed and mapped"; the array formula (AC) becomes a computed list, not an Excel formula.

---

## 5. What the intake engine must do

**Input:** the SwipeRx TMP file + the Implant's chosen **service (S1/S2/S3)** (shown with name + type).

1. **Implant selects the service up front** (S1/S2/S3, shown with name + type) → this fixes the movement, the **branch id (AE)**, service_level, and fixed fields *before* parsing. The service is a deliberate choice at the start, not inferred from the file.
2. **Skip header rows**; parse data rows.
3. **Group** by SwipeAWB (forward) / return AWB (S3) → this is the **AWB entity**; each data row is a **PO line** with its Koli.
4. **Validate** per row (missing SwipeAWB / PO Number / address / koli≤0 / bad postcode) → per-row error report; valid rows commit.
5. **Create AWBs + PO lines**; compute AWB koli = Σ PO koli; capture L2 (City), postcode, address, phone.
6. **Generate one unguessable courier link per AWB** (token not derived from the AWB).
7. **Build the NV upload output**: set `B = 11398423` (master) + `AE = branch of the selected service (1/2/3)` + `E = STANDARD/SAMEDAY`; map TMP fields; set `W = TMP D`; build `Y = PO list + total collies`; **MPS-expand per AWB** (base = SwipeAWB, children `SwipeAWB-1…-N`, `AB = Σ collies`); **append the link to col R** as `<updated_addr>…<a href="{URL}">{URL}</a></updated_addr>` within 500 chars; set S = today.
8. **Offer the output for download** (Implant uploads it to NV's Operator system) — plus a copy-of-links view.
9. **Derive hub** from L2/postcode via the hub map — **use a dummy mapping for the local trial** (§7).

Movement 3 variant: use pre-supplied return AWB as the tracking base; swap from/to (pharmacy → WH); carry invoice number; instruction includes "bring BA Return form."

---

## 6. Reconciliation with the current PRD / V2 schema (what must change)

| Area | Current build/PRD assumption | Reality from templates | Action |
|---|---|---|---|
| `po_line.po_number` | short `PO-2401` | long TRID code | Keep column; fix semantics/labels (it's the SwipeRx PO / NV TRID base) |
| `po_line.sp_type` (manual/electronic) | present per PO | **not in data**; rider reads Faktur at door | **Drop from intake.** Courier SP-Manual capture becomes a **rider-driven** step (e.g. "Faktur says SP Manual? capture it"), not a pre-counted set. Update courier flow + §7.1 of PRD |
| `po_line.koli` | maybe AWB-level only | **per PO line**; AWB = Σ | Confirmed — keep per-PO koli, AWB koli = sum |
| `awb.awb_id` | `NVIDMY…` | **SwipeAWB** (`AWB02S5X7`) is the grouping key; NV TRIDs are per-parcel | Model AWB on SwipeAWB; store TRIDs as derived tracking numbers if needed |
| `awb.city` (L2) | unclear source | = source **City** col | Wire it; report groups by station + this L2 |
| `awb.hub_code` | assumed present | **not in file**; only L2+postcode | Derive via L2/postcode→hub map or NV lookup — **still open** (§8) |
| Return AWB (S3) | DE creates in NV | **pre-supplied by SwipeRx** (`AWBR-…`) | S3 is its own intake flow; only forward-reject returns are DE-created |
| Invoice number | not modelled at intake | present in **return** data (col H) | Store for S3; Validator "invoice mismatch" check uses it |
| Delivery instructions (R) | new field | fixed RDO text, ≤500 chars, supports HTML anchors | App **appends the link as `<a href>` hyperlink** within the 500-char budget |
| Weight (W) | — | should be TMP D (samples hardcode 1) | Engine reads TMP D correctly (don't replicate the bug) |
| Shipper / service selection | per-service shipper ID in col B | **col B always master `11398423`; service = branch id in col AE (1/2/3)** | Engine sets B=master + AE=branch, never a per-service value in B |
| Col Y | GAP / unused | **PO list + total collies** | Engine computes it for courier door-cross-check |

---

## 7. Open items & resolutions

### Resolved (03 Jul)
- **Shipper/branch model** — col B always master `11398423`; branch id (AE) = 1 Regular / 2 Return-Pickup (11398434) / 3 Sameday. (Retracts the earlier "wrong shipper" flag.)
- **Col W** = TMP D (weight); engine must not copy the sample's hardcoded `1`.
- **Col Y** = PO list + total collies, for courier door cross-check.
- **Col AE** = branch id (the service selector), not a mystery GAP.
- **S1 vs S2 difference** = `service_level` (STANDARD/SAMEDAY) + `branch_id` (1/3); origin WH same in samples.
- **MPS** = per AWB; **TRID base = SwipeAWB**; children `SwipeAWB-1 … -N` (flat, no zero pad); one DN + one link per AWB.
- **AE** = always set explicitly from the service the Implant selects up front (never left to default).
- **Delivery-instruction** = **500 chars**, link injected as `<updated_addr>…<a href="{URL}">{URL}</a></updated_addr>` with the **anchor text equal to the URL**.

### Still open (stubbed for the local trial)
1. **Hub assignment** — approach agreed: **L2/postcode → hub mapping**, but the table isn't provided yet. **Local trial uses a dummy hub map.** *(Baskoro's standing "which hub" question.)*
2. **SP Manual detection** — not in the data (rider reads Faktur at door). **Baskoro to discuss with SwipeRx.** **Local trial randomly generates the SP-Manual flag** per PO for now; courier capture stays rider-driven.

---

*Supersedes/records the SwipeRX Operational Bible OC Guide v0.3 for engine-build purposes. Updated 03 Jul with the master/branch shipper model, per-AWB MPS, resolved GAP columns, and the 500-char hyperlink rule. Update again when SwipeRx changes the TMP format or resolves the open items.*

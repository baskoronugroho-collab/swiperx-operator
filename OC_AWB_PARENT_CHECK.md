# OC — AWB-level parent: confirmed constraints & the one open blocker (26 Jul 2026)

> **Revised after Baskoro's answers, 26 Jul.** Supersedes the first pass of this document.

## 1. Confirmed constraints

| # | Constraint | Source | Effect |
|---|---|---|---|
| C1 | `requested_tracking_number` is **min 11 / max 29 chars** | **CONFIRMED** | binding |
| C2 | Parent bundles at **SwipeAWB level** — one order per AWB | Baskoro | binding |
| C3 | **No additional prefix** on the tracking number | Baskoro | binding |
| C4 | **NV auto-creates the children when `AC` is blank; `AB` is required** | **CONFIRMED** | 🎉 removes the entire bug class |
| C5 | Namespace collision on `AWB…` — **<1% risk**, dropped | Baskoro | closed |
| C6 | Real per-parcel weights — already correct, no more hardcoded `1` | Baskoro | closed |
| C7 | `item_description` must **not** interact with the OC system | Baskoro | closed — see §4 |
| C8 | Some POs **may become >1 koli** | Baskoro | see §5 |
| C9 | Courier link omitted from this Excel build, **required in the webapp engine** | Baskoro | Lane 1 |
| C10 | **Fix A is not the long-run answer** | Baskoro | see §6 |

## 2. C4 is the headline — the child-numbering problem disappears

Leave `AC` blank, set `AB` = piece count, and NV mints `<A>-01 … <A>-0N` itself.

That means **we never write a child TID again**, so:

- the running-counter bug is structurally impossible, not merely fixed;
- the "must the child prefix match column A" question is moot — NV owns it;
- the converter's 25-nested-`IF` monster in `AC` gets **deleted**, not repaired;
- `backend/oc_engine.py`'s `piece_trids()` gets deleted too.

This also retroactively vindicates **PRD FR-OC3** ("we do NOT generate the collie children"), which I
had flagged as contradicting the working templates. The templates *could* fill `AC`; they never *had* to.

## 3. 🔴 The one blocker: C1 + C2 + C3 cannot all hold

**Every SwipeAWB is exactly 9 characters.** Verified across three independent batches — 215 AWBs,
zero variation:

| Batch | n | lengths |
|---|---|---|
| Regular TMP, 10 Jun | 57 | `{9: 57}` |
| Sameday TMP, 30 Jun | 79 | `{9: 79}` |
| Converter TMP Paste (Jul) | 79 | `{9: 79}` |

Format is invariably `AWB` + 6 alphanumerics (`AWB02U24V`, `AWB02S757`).

```
min length = 11   (C1, confirmed)
SwipeAWB   =  9
no prefix allowed (C3)
⇒ the bare SwipeAWB cannot be the tracking number. 2 characters short.
```

Something has to give. Four ways out, in the order I'd rank them:

### Option 1 — SwipeRx lengthens the AWB at source ⭐ *cleanest long-run*
Ask SwipeRx to emit an 11+ char AWB (e.g. `AWB02U24V` → `AWB2607U24V` with the period baked in, or
simply two more chars of entropy). It stays *their* identifier, no prefix is added by us, C1/C2/C3 all
hold, and every downstream system reads one string.
**Cost:** a change in SwipeRx's TMP generator + lead time. **Ask them tomorrow — this is the only
option that resolves the contradiction rather than working around it.**

### Option 2 — use the AWB's **first PO number** as the tracking number ⭐ *best interim, zero dependencies*
`A` = first PO of the AWB (21–24 chars ✅, globally unique ✅ — verified 210/210), `D` = the SwipeAWB.
The bundle is still **one order per AWB** (C2 satisfied); we simply borrow an identifier that already
exists instead of inventing one — so C3 is satisfied too, on the strict reading that we add nothing.

Why this is low-risk: **the June file that worked already used PO numbers as tracking numbers.** Ops
are used to seeing them. Children become `<firstPO>-01…-0N`, which is byte-identical to what production
has produced all along for single-PO AWBs.

Caveat: the parent TID changes if the first PO of an AWB changes between TMP re-runs. Pin it by
storing the mapping in `awb` at intake — the app already owns this (see §4).

### Option 3 — suffix instead of prefix
`AWB02U24V-S1` (12) or `AWB02U24V0726` (13). Satisfies C1 and the letter of C3, but it is still an
affix we invented, and a `-` suffix reads like a child TID — I'd avoid it. Mentioned only for completeness.

### Option 4 — leave `A` blank and let NV mint the parent too
Untested. Given C4 (NV auto-creates children), it is worth **one question**: does NV also generate the
parent tracking number when `A` is empty? If yes, this is the least work of all. If no, discard.

> **Recommendation:** ask for **Option 1** as the target, ship **Option 2** now — it needs nothing from
> anyone and it reuses a shape with production history. Confirm Option 4 in passing since it costs one question.

## 4. C7 accepted — PO does not belong in the OC file

You're right, and my earlier B3 was wrong to route the PO manifest through `item_description`. That
field describes parcel contents for the courier/handling; it is not a reconciliation ledger, and
loading a 300-char PO list into it would be abuse of the field.

**The PO↔AWB mapping is the webapp's job, and the schema already does it** —
`backend/resources/db/migration/V2__core.sql:79`:

```sql
CREATE TABLE po_line (  awb_id …, po_number …, koli …  )
```

So at intake the app parses the TMP, stores `awb` + its `po_line`s, and serves them behind the courier
link and on the DN. The OC file only needs to create the order. `D = SwipeAWB` remains the join key back
to our records. **No OC column change needed — B3 is closed.**

## 5. C8 — POs may become >1 koli, which settles the ordinal question

In today's data 209 of 210 PO rows are koli = 1, so `child -0k = k-th PO` *looks* workable. With C8 it
is definitively not: any multi-koli PO shifts every ordinal after it in its AWB.

Combined with C4 (NV names the children, not us), the conclusion is clean:

> **Parcel→PO identity cannot live in the TID at all.** It lives in `po_line` and on the DN.

This is consistent rather than a loss — the courier reads the DN and the link, never the child TID.
It does mean partial reject is captured **per AWB with photographic proof** (as PRD §7.2 already
specifies), and the per-PO detail comes from `po_line`, not from which box was scanned.

## 6. C10 — dropping Fix A, and what replaces it today

Agreed, and C4 makes it moot: there is a change that is **both simpler than Fix A and the correct
long-run shape**.

**Delete the `AC` formula.** That's it.

The current converter already sets `A` = PO number and `AB` = that PO's koli. With `AC` blank, NV mints
`<PO>-01…-0N` — exactly the shape that uploaded successfully in June. So:

| | Fix A (rejected) | **Blank `AC`** |
|---|---|---|
| Work | rewrite 25 nested `IF`s in a 2,400-char formula | delete a column |
| Result | we hand-write children | NV mints them |
| Long-run | throwaway | **the target behaviour** |
| Risk | must get padding + restart exactly right | nothing to get wrong |

This unblocks the DE team today *and* moves toward the destination instead of away from it. The
AWB-level consolidation (§3) then becomes a separate, later change to the same file.

## 7. Target shape, once §3 is answered

One row per SwipeAWB, `AC` deleted:

| Col | Value | Source | Status |
|---|---|---|---|
| **A** | AWB-level tracking number, **11–29 chars** | ⛔ **open — §3** | blocker |
| D | `AWB02U24V` (SwipeAWB) | TMP C | ✅ |
| **AB** | **Σ koli across the AWB** | Σ TMP W | ✅ (max 12 today) |
| **AC** | **blank** — NV auto-creates | — | ✅ C4 |
| W | AWB total weight | TMP D (verified == Σ per-PO, 79/79) | ✅ C6 |
| R | RDO text **+ injected courier link**, ≤500 chars | webapp engine | ⛔ C9 — not in Excel |
| Y | leave as-is | — | ✅ C7 |

79 rows instead of 210. Everything except column A is already available and verified.

## 7b. 🔴 Separate OC bug found 26 Jul — wrong service silently commits garbage

Found while writing `backend/tests/test_oc_api.py`. **Not** related to the TID scheme, but
it lives in the same engine, so it is parked here with the rest.

Uploading a **Regular** TMP while **Return Pickup (S3)** is selected produces **58 "AWBs"
with ZERO validation errors**:

| field | value produced |
|---|---|
| `awb_id` | `Total Weight per AWB (kg)`, `2.66`, `16.1` … (weights and header text) |
| `pharmacy_name` | `SwipeAWB`, `AWB02S5X7` … (the AWB column) |
| `po_number` | `Pharmacy's Id`, `4449` … (pharmacy ids) |

Because no row *errors*, **FR-OC5's all-or-nothing gate never fires** — `create` commits
all 58, mints a real courier link for each, and writes them to the upload file. The
operator's only clue is the preview table looking wrong.

**Fix:** validate the header row against the selected layout before parsing. Each layout
already declares `data_start_row` and its column map, so the check is exact, not heuristic.
Deliberately **not applied** — OC is parked until the Monday confirmation.

Pinned as a strict `xfail` in `backend/tests/test_oc_api.py::test_wrong_service_layout_does_not_commit`,
so the suite fails loudly the moment it starts passing.

## 8. Still open

1. **§3 — what goes in column A?** Option 1 (SwipeRx lengthens the AWB) or Option 2 (first PO). Needs a decision.
2. **Option 4 sanity check:** does NV mint the *parent* tracking number if `A` is left blank?
3. **`AB` semantics under C4:** confirm NV creates exactly `AB` children and no extra document piece.
   PRD FR-OC3 mentions a `-DO` document child — if NV appends one, does `AB` count it or not?
4. **C9:** the link injection lives only in the webapp engine. The Excel converter cannot be the
   production path once links are required — plan the cutover.

## 9. Consequent code changes

| Where | Change |
|---|---|
| Converter `OC Upload!AC` | **delete the formula** (do today) |
| Converter, later | one row per SwipeAWB; `AB` = Σ koli; `W` = AWB total |
| `backend/oc_engine.py` | delete `piece_trids()`; stop emitting one row per piece — **one row per AWB**; `AB` = Σ koli; `AC` = `""` |
| `PRD.md` FR-OC3 | correct — the "NV auto-creates children" note stands. Update the AWB-naming clause once §3 lands |
| `OC_LINKING_BUG.md` | Fix A withdrawn; §5 (FR-OC3 contradiction) resolved by C4 |

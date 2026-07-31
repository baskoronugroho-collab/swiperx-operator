# OC child-TID linking bug — diagnosis (26 Jul 2026)

> ## ⚠️ SUPERSEDED IN PART — read [`OC_AWB_PARENT_CHECK.md`](OC_AWB_PARENT_CHECK.md) first
>
> Confirmed by Baskoro on 26 Jul, after this document was written:
>
> - **NV auto-creates the child TIDs when `AC` is left blank** (`AB` is still required). So we should
>   **never write children at all** — delete the `AC` formula. §3 Fix A and Fix B are both **withdrawn**;
>   the diagnosis in §1–§2 stands and explains why the current file fails.
> - **§5 is resolved:** PRD FR-OC3 was right. Filling `AC` is optional, not required.
> - **§4 still stands** — `backend/oc_engine.py` must stop emitting one row per piece.
> - Tracking-number **min 11 / max 29 is confirmed true**, and **no prefix is permitted** — which leaves
>   an open blocker, since every SwipeAWB is 9 chars. See `OC_AWB_PARENT_CHECK.md` §3.

> **Report from ops:** *"tadi kita pake template yang baru tapi hasil resi anakannya gak ngelink ke indukannya."*
>
> **Verdict: reproduced and root-caused.** 131 of 210 parent rows (62.4%) in
> `SwipeRx TMP to Ninja OC Converter (FIXED).xlsx` emit child TIDs that cannot attach to their parent.
> This is a formula bug in the converter, not a Ninja system problem.

---

## 1. The rule Ninja actually enforces

Derived empirically from **three real templates that were uploaded successfully**
(`OC Template/[Template DE FWD] SWIPE UPLOAD 10 JUNI 2026.xlsx`, `[Template DE FWD] SAMEDAY SwipeRx KD5.xlsx`,
`[Template DE PU Return] Copy of Pickup Return SwipeRx.xlsx`). Every single row in all three obeys it:

```
AC[i]  ==  A  +  "-"  +  zeroPad2(i)      for i = 1 … AB
```

| Col | Field | Rule |
|---|---|---|
| **A** | `requested_tracking_number` | the **parent** TID. One upload row = one bundle. |
| **AB** | `bundle_information.total_quantity` | number of children, **N** |
| **AC** | `bundle_information.requested_piece_tracking_numbers` | `A-01, A-02, … A-0N` — **prefix is byte-identical to A**, **zero-padded**, **always restarts at 01** |
| **D** | `reference.merchant_order_number` | the grouping reference (SwipeAWB forward, PO number on returns). **Does not affect linking.** |

Proven examples from the working June file:

```
A = 26061001420090OsBIgygMR   AB = 2   AC = 26061001420090OsBIgygMR-01, 26061001420090OsBIgygMR-02   ✅
A = AWBR-10859-2026-4-17      AB = 1   AC = AWBR-10859-2026-4-17-01                                   ✅
```

There is **no** row anywhere in the working samples where a child's prefix differs from A, where the
numbering starts above 01, or where the pad is dropped.

---

## 2. What the new converter emits

`OC Upload!AC` builds the child list from helper column `AI`:

```
AI = SUMIF($AG$2:$AG2, $AG2, $AH$2:$AH2)     ' running koli count within the SwipeAWB group
AC = <PO> & "-" & TEXT(AI - AH + 1, "00") & …  ' first child index = AWB-level running offset
```

So the **prefix is the PO (row-level)** but the **counter is AWB-level and running**. Those two are
incompatible. Only the *first* PO of each SwipeAWB starts at `-01`; every later PO of the same AWB
starts at `-02`, `-03`, … and therefore has no `-01` under its own parent.

Actual output, AWB `AWB02U24V` (3 POs, 4 koli):

| row | A (parent) | AB | AC (children) | link |
|---|---|---|---|---|
| 2 | `260630054137433DSXWMpd` | 2 | `…DSXWMpd-01, …DSXWMpd-02` | ✅ |
| 3 | `26070102001839ezpAD07IG` | 1 | `…ezpAD07IG-03` | ❌ no `-01` |
| 4 | `26070102001839MzOIv6dbd` | 1 | `…MzOIv6dbd-04` | ❌ no `-01` |

**Scale of the damage in the tested file:** 79 SwipeAWBs, 210 PO rows, **57 AWBs have >1 PO** →
**131 broken parent rows (62.4%)**. Exactly matches the symptom: *some* resi link, most don't.

### Why it happened
The converter **half-migrated**. It kept the old **per-PO parent** shape (Petunjuk B12:
*"Satu baris per Nomor PO"*) but adopted the **per-AWB running numbering** from deck slide 24.
Those two models cannot be combined — the running counter is only meaningful if there is a single
AWB-level parent.

---

## 3. Two ways to fix it — pick one, don't mix

### Fix A — keep per-PO parents (minimal, proven, ships today)
Restart the counter at 1 for every row. In `OC Upload!AC`, replace every occurrence of
`($AI2-$AH2+1)+k` with the literal `1+k`:

```excel
= 'TMP Paste'!$F2 & "-" & TEXT(1,"00")
  & IF($AH2>=2, ", " & 'TMP Paste'!$F2 & "-" & TEXT(2,"00"), "")
  & IF($AH2>=3, ", " & 'TMP Paste'!$F2 & "-" & TEXT(3,"00"), "")
  & …
```

Helper column `AI` becomes unused and can stay (harmless).

- ✅ Byte-identical to the June file that demonstrably works. Zero unknowns.
- ❌ Does **not** deliver the deck's *"Sekarang: per AWB Reference"* consolidation — one apotek with
  4 POs still becomes 4 separate Ninja orders / 4 AWBs / 4 courier links.

### Fix B — go to one bundle per SwipeAWB (the deck's actual intent, **recommended**)
Emit **one row per SwipeAWB**, not per PO:

| Col | Value |
|---|---|
| A | AWB-derived parent TID, e.g. `SWRXAWB02U24V` (`SWRX` + SwipeAWB — satisfies the 11–29 char rule; bare `AWB02U24V` is 9 chars) |
| D | `AWB02U24V` (the SwipeAWB, as the merchant reference) |
| AB | **Σ koli across all POs in the AWB** (= 4 for `AWB02U24V`) |
| AC | `SWRXAWB02U24V-01, -02, -03, -04` — **parent prefix, zero-padded, from 01** |
| Y | PO list + koli, e.g. `260630054137433DSXWMpd (2), 26070102001839ezpAD07IG (1), 26070102001839MzOIv6dbd (1) — 4 koli` — this is where PO granularity survives |

- ✅ Obeys the proven rule.
- ✅ One order = one AWB = **one DN = one courier link**, which is what the whole SwipeRx Operator
  courier app is built around.
- ⚠️ PO-level identity disappears from Ninja's order record (it lives in `D`, `Y`, and our DB).
  Needs Ops/Finance sign-off before switching.

> **Do NOT use deck slide 24 as drawn.** It shows one AWB-level bundle whose children carry
> *different PO prefixes* (`…Xp3cOoIZ-01, …Cd4TW12aas-02, …OsBIgygMR-03`). No working sample has ever
> done that, and the parent-prefix rule says it will not link. **Deck slide 23 (SwipeAWB as the prefix
> for all children) is the correct one** — it is Fix B.

**Recommendation:** ship **Fix A** to the Excel converter today so the DE team is unblocked, and
build **Fix B** into the app's OC engine, trialled on one small batch before cutover.

---

## 4. Third bug: the repo's own OC engine does not match either

`backend/oc_engine.py` (`piece_trids` + `build_upload_xlsx`) currently emits:

```python
return [base] if total == 1 else [f"{base}-{i}" for i in range(1, total + 1)]   # base = SwipeAWB
...
for trid in trids:
    ws.append(_upload_row(..., trid=trid, ...))   # ← one upload ROW per piece
```

Four deviations from the proven contract:

| # | Engine does | Working samples do | Impact |
|---|---|---|---|
| 1 | one upload **row per child piece**, `A` = the child TID | one row per **bundle**, `A` = the parent | creates N orders each claiming to be a bundle of N — hard break |
| 2 | `-1`, `-2` (no pad) | `-01`, `-02` | children won't match |
| 3 | single-koli AWB → `A` = bare `AWB02U24V`, no `-01` child | always `<A>-01` | 1-koli orders lose their piece |
| 4 | `A` = raw SwipeAWB (9 chars) | ≥11 chars required (PRD FR-OC3) | may be rejected outright |

**None of this has been exercised against Ninja's real system** — M1 only ever produced a file for
inspection. Fix items 1–4 together with Fix B above; they are the same change.

---

## 5. Fourth conflict: PRD FR-OC3 contradicts every real template

> FR-OC3: *"**We do NOT generate the collie children** — NV's internal system **auto-creates `-01, -02, … -DO`**"*

But all three working samples ship `AB` and `AC` **populated**. Either the auto-create only fires when
`AC` is blank, or the note is wrong.

**Action:** one 2-row trial upload — one row with `AB`/`AC` blank, one with them filled — settles it in
five minutes. Until then, **fill them** (that is the path with production evidence behind it).

---

## 6. Five competing models currently in play

| Source | Parent (`A`) | Children (`AC`) | Status |
|---|---|---|---|
| Working June/Sameday/Return templates | PO number | `PO-01…-0N`, restart per PO | ✅ **proven in production** |
| New "FIXED" converter | PO number | PO-prefixed, **running** count | ❌ **broken — 62% of rows** |
| Deck slide 23 (Option 1) | SwipeAWB | `AWB-01…-0N` | ✅ consistent → **Fix B** |
| Deck slide 24 (Option 2) | AWB-level | mixed PO prefixes, running | ❌ violates prefix rule |
| `backend/oc_engine.py` | the child TID itself | `AWB-1…-N`, unpadded, per-piece rows | ❌ 4 deviations |
| PRD FR-OC3 | `SWRX`+SwipeAWB | *none — leave blank* | ⚠️ unverified |

Converging on **one** model is the prerequisite for the OC lane in `SCOPE_V3_MVP.md`.

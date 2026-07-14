# SwipeRx Operator — Feedback log (for PRD update)

> Captured from review on 2026-07-10. Grouped by surface. "✅ done" = reflected in the
> prototype this pass; "⚠ needs PRD decision" = flagged for product before it can be final.

---

## Courier app

1. **Header** — show the AWB number (no literal word "AWB") on line 1, customer/pharmacy name on line 2. ✅ done
2. **Order context fields** — must include: service, shipper ID, shipper name, hub, address, total parcels (koli/collies), PO details, and total koli *within each PO*. ✅ done
3. **Photo fallback** — if the live in-app camera can't be used, allow an upload-a-photo option (with the live-capture path still the default/preferred). ✅ done (secondary "Upload instead" action)
4. **Return form capture** — needs a more detailed shot: a close-up of the return-form *box* AND a full-page view. Return form requires an attestation that it is **signed & stamped**. ✅ done (two return-form captures + signed+stamped attestation)
5. **Rejection instruction** — when there is a rejected item, instruct the courier to screenshot the page and inform their Station IC. That page must list the **AWB(s) for return**. ✅ done (reject instruction panel with return AWB listed)
6. **Restart** — make it clearly a button + a confirmation page. Current success screen reads too much like a plain "OK". ✅ done (confirmation interstitial before restart)
7. **Delivery-confirmed note** — explain that delivery confirmation must ALSO be completed on the driver app. ✅ done (notice on success screen)

---

## Order intake  →  rename "Order creation"

1. **Rename** the surface/menu to **"Order creation"**. ✅ done
2. **Drop S1/S2/S3 codes.** Instead capture/show: **service, shipper ID, shipper name, corporate branch.** ✅ done
3. **All-or-nothing commit** — if ANY row fails, reject the entire file (no partial create). ✅ done
4. **Date selection = single day** (not a range). ✅ done
5. **Upload history** — after orders are created, keep a **history table of successful uploads** with the file attached; file format **.csv** (not .xlsx). ✅ done
   - ⚠ needs PRD decision: confirm the courier-link injection column now lives in the .csv, and whether links.csv is still separate or merged into the one history file.

---

## Program Manager (overview)

1. **Naming bug** — detail panel title renders "[object Object]". ✅ fixed
2. **Full table** — show a full AWB list below the KPI cards; the list swaps to the relevant subset when a KPI's "view detail" is clicked (default = all). ✅ done

---

## Arrival scan & handover

1. **Separate tracking view** — keep the scan/handover action page, and add a **tab group to track the list**, separated by **day** and **status**. ✅ done
2. **Handover session system (300–500 docs/day)** — proposed workflow (built as prototype, ⚠ needs PRD sign-off):
   - **Build session:** scan all docs prepared for handover into an open session (running count, grouped by day).
   - **Hand over:** one action submits the whole session to SwipeRx ("Handed over — awaiting SwipeRx receipt").
   - **SwipeRx receives:** SwipeRx confirms receipt; any docs they reject come back to Implant.
   - **Scan rejected docs back:** Implant scans each returned/rejected doc.
   - **Reason per rejected doc:** each rejected doc gets its own coded reason (they differ per doc).
   - **Session sizing:** sessions are capped/paged so 300–500 docs stay manageable — grouped by day, with a progress header (scanned / expected) and bulk-scan entry (scanner-as-keyboard, one line per beep).
3. **Dedicated rejected-docs view** — a view listing rejected docs + the **next action pending** (what type of action each needs). ✅ done
   - ⚠ needs PRD decision: the set of rejected-doc reason codes and the set of "next action" types.

---

## Return worklist (Station IC)

1. **"Download label" was wrong** — there is no label download here. The real flow: ✅ reworked
   - Courier submits a reject → **reject list is populated with the AWB(s)**.
   - Implant **downloads the reject list** and creates an **OC template** for the return.
     - ⚠ needs PRD decision: this needs a **new template engine** for the rejection OC (distinct from the forward OC).
   - The rejection OC is **re-uploaded through Order creation** (as a rejection intake).
   - The system **tracks & logs** the return in the data.
2. Net: this surface becomes a **reject-return worklist** (populate → download reject list → generate rejection OC → re-upload → tracked), not a print-a-PDF-label screen.

---

## SwipeRx report

1. **Downloadable, not read-only** — surface a clear download link (keep the data non-editable, but make export prominent). ✅ done
2. **Filters must actually work** — selecting a filter should filter the table. ✅ done
3. **Date = range (from → to)**, and it refers to the **internal OC date** (when data was input from the TMP file), not delivery date. ✅ done
4. **Full filter set visible** — show every filter control so it can be reviewed before further feedback. ✅ done
5. **Group by ORIGIN, not station** — split by origin TMP (e.g. TMP Depok, TMP Surabaya, …). ✅ done
6. **Three top-level groups:** ✅ done
   - **Forward** (service = Sameday or Regular),
   - **Reject** (based on the forward reported in the Driver app),
   - **Special Case return** (the third service).
7. **"Hub" → "Area".** ✅ done
8. **Handover status column** — add handover status (handed over once docs are received by Ninja). ✅ done
9. **Row identity = SwipeRx AWB** (not Ninja AWB). Clicking a row shows all the **Ninja AWBs** under that SwipeRx AWB + photos + every detail the courier submitted. ✅ done
   - Reject details live in a **separate tab group**; clicking a rejected AWB **auto-switches to the Reject tab**. ✅ done
10. **On-page guide/legend** — define everything, especially the different **status levels**. ✅ done
   - ⚠ needs PRD decision: confirm the canonical status vocabulary and definitions used in the legend.

---

## Cross-cutting open questions for PRD

- Canonical **service list** now that S1/S2/S3 codes are dropped (names only? + shipper/branch metadata source?).
- **Reject-return OC template** engine spec (fields, how AWBs map forward→return).
- **Handover session** rules at 300–500 docs/day scale (caps, paging, who confirms receipt, SLA).
- **Status vocabulary** shared across Driver app, Operator, and Report (single source of truth for the legend).
- Whether **SwipeRx AWB ↔ Ninja AWB** is 1-to-many everywhere (report grouping assumes yes).

---

# Round 2 feedback (2026-07-10)

## SwipeRx report
- Guide/legend collapsed by default, with a distinct colour so it stands out. ✅ done
- Remove Area and Pharmacy filters. ✅ done
- Add an Origin filter (TMP Depok / Bandung / Surabaya, per submitted data). ✅ done
- Merge handover into status (no separate handover column/filter; handover shown within status). ✅ done
- Search by SwipeRx AWB **or** PO number. ✅ done
- Service filter only where applicable: Forward & Reject have services; Special Case return has none — hide the service filter there. ✅ done
- Each AWB's detail opens in a **right-side popup drawer** (not inline expand). ✅ done
- Detail drawer shows: a **status-change timeline**, the **list of POs** (each tagged manual / electronic), and the **photos side by side**. ✅ done

## Courier app
- Total koli = **sum of each PO's koli**. ✅ done
- The screenshot/inform-Station-IC page is the **last** step. ✅ done
- Camera button **opens the device camera** (live capture input). ✅ done
- Normal flow: Pharmacy POD → Receiver POD → **Faktur (whole document)** → SP-manual check → **ask "any partial reject?"** → if yes: return-form photo + parcel photo + forward AWB sticker → finish with a screenshot guide. ✅ done (partial reject is now an inline question, not a separate outcome)
- No-return: **full page only**, no close-up. ✅ done
- Revamped final message: success → "complete the successful delivery in the Ninja driver app"; full reject / failed → the matching action in the driver app. ✅ done
- Under the important section, a small **"Something wrong?"** button → confirm → resubmit/restart. ✅ done
- **Removed** the "Start next delivery" button. ✅ done

## SwipeRx operator
- Picking a service also shows **Shipper ID, Corporate branch, Shipper name** — auto-listed, **read-only** (not editable). ✅ done
- **Remove** link monitoring. ✅ done
- **Remove** the session cap from Arrival & handover. ✅ done
  - ⚠ needs PRD decision: the shipper master that maps service/file → shipper ID / name / corporate branch.

---

# Round 3 feedback (2026-07-10)

## SwipeRx report
- Drawer: no photo per Ninja AWB — just the **list of Ninja AWBs** (with status/receiver). ✅ done
- Remove the "Downloadable — one row per Ninja AWB…" badge. ✅ done
- Remove the sub-header line "Split by Forward, Reject and Special Case return…". ✅ done

## Courier app
- Show the **SwipeRx AWB** on documents, not the Ninja AWB — the tokenized link is per **SwipeRx AWB** level. ✅ done
- Service-aware outcomes: for the **return service**, the first outcome reads **"No return to collect (success)"** instead of "Delivery (normal)", and the reject/failed wording adapts to the return context. ✅ done
- Failed delivery becomes a **2-step** flow: enter reason → upload photo. ✅ done

## Reject returns (Station IC)
- Must be able to see which AWBs are **not yet downloaded**. ✅ done (a "Not downloaded" filter/segment + stage badge)

## Order creation
- **Two OC menus**: (1) Normal OC from SwipeRx input, (2) Reject-item OC (return). ✅ done (split into two left-nav entries)
  - ⚠ needs PRD decision: confirm the reject OC is a distinct template engine + upload path from the normal OC.

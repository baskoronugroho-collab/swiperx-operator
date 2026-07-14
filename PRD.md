# SwipeRx Operator — Product Requirements Document (Production)

> The application (operator dashboard + driver app + SwipeRx page) is named **SwipeRx Operator**.
> This is a **from-scratch production PRD** (**v2.2**, build named **Alpha 0.1**), written after the capability demo. It supersedes and replaces the demo-era PRD v1.8 and the demo-scope/design-brief-demo documents. Those were built for a static, no-login, `localStorage` walkthrough; this document specifies a **real production web-app** on Ninja Van's internal deployment stack. **Where older prose conflicts with the `BUILD_HANDOFF.md` decision ledger (Rounds 1–4), the ledger wins.**

## 1. Document control

| Field | Value |
|---|---|
| Product | **SwipeRx Operator** — Delivery Compliance & Returns (POD / RDO collection + Returns visibility) |
| Version | **2.3 (production)** — PRD document version |
| Build / system name | **Alpha 0.1** (from scratch; no reuse of the demo build; renamed from "v0.0.1") |
| Status | **Draft for review** — building; M0 foundation + M1 OC-intake backend **deployed & verified** on Substrait (09 Jul 2026); design prototype reviewed 10 Jul (3 rounds), folded into this v2.3 |
| Author / Owner | Baskoro Adi Nugroho (Product) |
| Last updated | 14 Jul 2026 |
| Confirmations (14 Jul) | Single DN (two sections, no Faktur); real shipper IDs + **S3 redefined as POD-Return (reject of forward)**, Return-Pickup now on Regular + `AWBR` prefix; §10 status list adopted as canonical; **AWB naming proposed** (`SWRX`+SwipeAWB, NV auto `-01…-DO`); **two OC output files**; three separate reject menus; handover receipt simplified (no SLA). See §19 #15/#21/#22/#25/#27 |
| Supersedes | PRD v1.8, DEMO_SCOPE.md, DESIGN_BRIEF_DEMO.md, context.md, DEPLOYMENT.md, app/ (demo build) |
| Deployment target | **Substrait** — NV's internal Claude Code deployment platform (M0/M1 deployed & verified live; see §17) |
| Source of truth | `BUILD_HANDOFF.md` decision ledger (Rounds 1–4, 03–09 Jul 2026) — **where it conflicts with older PRD prose, the ledger wins**; plus SwipeRx post-demo feedback, the SwipeRX Operational Bible, NV Design Master, and the real OC template samples |
| Changes in 2.2 | Folded in the `BUILD_HANDOFF` decision ledger (Rounds 1–4). **Product/flow changes:** reject = **flag + proof only** (dropped per-PO reject quantities / `RejectLine`); **signed+stamped attestation now required** on the DN (reverses v2.1 §9); **multi-role accounts** (`User.roles[]`); OC intake = **3 explicit steps** with corrected shipper model (col B master `11398423`, service via **branch id in col AE**); **hub is NV-assigned** via a second upload flow (dropped the L2→hub map); return `delivery_instructions` = short "open the link" text; **9-code fail-reason list** + "no-return = success + blank-signed form"; **live-capture photo timestamp** locked; lifecycle `RETURN_LABELLED → RETURN_AWB_PENDING/CREATED`; dropped reprint/print tracking; **Alpha 0.1** rename + in-app changelog; Implant/DE are the **same team**. Appendix C statuses refreshed |
| Changes in 2.3 | Folded in the **10 Jul design-prototype review (Rounds 1–3, `FEEDBACK_NOTES.md`)** — **Round 5** in the decision history. Headline changes: **"Order intake" → "Order creation"**, split into **two menus (normal OC + reject-item/return OC)**; **S1/S2/S3 codes dropped from the UI** → show **service name + shipper ID + shipper name + corporate branch** (read-only); OC commit is **all-or-nothing** (any bad row rejects the whole file); OC date = **single day**; OC output is **`.csv`** (not `.xlsx`) with an **upload-history table**; **camera-fallback upload** now allowed (resolves the webview dead-end — reverses the "no gallery" lock); courier **partial reject is an inline question**, not an up-front outcome; last courier step = **screenshot + inform Station IC** (lists the return AWBs); **"Something wrong?" / resubmit** replaces "Start next delivery"; couriers are reminded **delivery must also be confirmed in the Ninja driver app**; return handling **reworked** — Station IC surface becomes a **reject-return worklist** (reject list → download → generate **rejection OC** → re-upload via Order creation → tracked; **no PDF-label printing**); **handover gains a SwipeRx-receipt loop** (hand over → awaiting receipt → SwipeRx confirms/rejects → scan rejected docs back with a coded reason); report **grouped by ORIGIN/TMP** (not station) into **Forward / Reject / Special-Case-return**, date = **OC-input date range**, "Hub"→"Area", row identity = **SwipeRx AWB** (1→many Ninja AWBs), collapsible **status legend**. **Open ⚠ items → Appendix C / §19 (#21–#27).** Where 2.3 conflicts with 2.2 prose, **2.3 wins** |

### 1.1 What changed from the demo (v1.8 → Alpha 0.1)

| Dimension | Demo (v1.8) | Production (Alpha 0.1) |
|---|---|---|
| Deployment | Static, no-build, `localStorage`, open `index.html` | Real backend + DB + media store, deployed on **Substrait** (NV's internal platform); 300–1000 parcels/day; ~300 concurrent courier links; ~50 hubs. **Alpha 0.1 runs on the public portal with dummy data only** (real bucket + NV self-hosted portal later) |
| Auth | Skipped / seeded email+password | **Google Workspace SSO** for staff and SwipeRx (with a **dev-login stopgap** until the OAuth client exists); couriers stay tokenized (no login) |
| RDO documents | Faktur + TTTF (+ SP for Manual), per AWB | **One Delivery Note (DN) per AWB** listing multiple POs; POD set = pharmacy POD + receiver POD + DN (**signed+stamped attestation required**) + SP Manual (per Manual PO) |
| Reject data | Select medicine items + qty | **Flag + photographic proof only** — courier marks partial/full + captures proof; **no per-PO reject quantities** (`RejectLine` dropped). The DN's box 2 is the built-in return/BA-Retur attestation |
| Return AWB | Auto-generated in-app (`RTS-…`) | **Created via a rejection OC** (Round 5): reject list → download → generate the reject-item OC → re-upload via Order creation → tracked. No in-app PDF-label printing |
| Roles | Merged into one "Operator" view | Full split, **multi-role accounts** (`User.roles[]` — one person can hold several hats): Superadmin, Program Manager, DE, Implant, Station IC, Validator, Courier, SwipeRx. **Implant and DE are the same team** (interchangeable) |
| Compliance control | Courier attestation checkbox + mandatory Validator matrix | **Required-photo completeness gate + required signed+stamped attestation on the DN**; no *mandatory Validator* gate (Validator flags + downloads, non-blocking) — see §9 |
| Image detection | Out of scope | Deferred to a **fast-follow version** (§16); the manual attestation tick is the stopgap until LLM/OCR replaces it |

## 2. Executive summary

Ninja Van Indonesia is SwipeRx's logistics partner for delivering pharmaceutical orders to pharmacies and returning the signed documentation (RDO) and rejected goods each delivery generates. SwipeRx is consolidating its per-PO documents into **one Delivery Note (DN) per AWB**. Ninja can now use **one MPS/TRID per AWB** instead of one per PO.

Four failures cost SLA, tickets and billing disputes:
1. **Invisible rejects** — neither Ninja nor SwipeRx sees returns until a pharmacy disputes an invoice.
2. **Incomplete RDO** — documents delivered unsigned/unstamped or missing entirely.
3. **No SwipeRx visibility into Implant backlog** — SwipeRx cannot see what has arrived at Implant and is awaiting handover.
4. **Forgotten return docs** — drivers forget to bring/ask for the BA Retur or the sign+stamp. The new DN combines these for **forward** movement; **return** movement still needs software help.

SwipeRx Operator addresses these by (a) enforcing **complete photographic capture** of the required POD/RDO documents (with a **required signed+stamped attestation** on the DN) before a delivery can be confirmed, (b) **flagging every reject with photographic proof at the door** (partial/full + proof photos — not per-PO quantities), (c) tracking parcels **from delivery through arrival-at-Implant to handover**, giving SwipeRx a live backlog view, and (d) providing a streamlined **SwipeRx report** to filter and download the data.

v1 is a fully functional production build. Image-based sign/stamp detection is a **fast-follow** (§16).

## 3. Background & problem statement

Every SwipeRx **forward** delivery carries an RDO obligation — documents the pharmacy must sign and stamp ("chop"). On a reject, the pharmacy also fills a return/reject form. Historically these were separate documents (Faktur, TTTF, Surat Pesanan, BA Retur) collected per PO, so Ninja created one MPS/TRID per PO.

**New model (SwipeRx):** one **Delivery Note (DN) per AWB**, listing each PO with its **PO number and quantity (koli)**. *(SP type is **not** carried in the source data — the rider identifies which POs are SP-Manual at the door — so SP-Manual capture is rider-driven, not a pre-counted set.)* The **single DN has two sections** (two sign+stamp areas): the **top** for forward delivery acceptance, the **bottom** for rejected items (the BA Retur is built into the DN's bottom section; **there is no separate Faktur/return document** — confirmed 14 Jul). Ninja moves to **one MPS/TRID per AWB**.

| Failure mode | Root cause | How v2 addresses it |
|---|---|---|
| Invisible rejects | Unstructured, offline return handling | **Reject flagged + proof photos at the door** (partial/full) + report + SwipeRx visibility |
| Incomplete / unsigned RDO | Low door-step compliance across multiple docs | Required-photo completeness gate before "Confirm delivery"; fast-follow sign/stamp detection |
| No visibility into Implant backlog | Arrival + handover tracked offline | Barcode-scan arrival tracking + handover sessions, surfaced to SwipeRx |
| Forgotten BA Retur / sign+stamp | Separate documents, easy to miss | **Forward:** DN combines them (one document, two boxes). **Return (Service 3):** app-guided flow |

## 4. Goals & non-goals

### 4.1 Goals
- Make **complete photographic POD/RDO capture** a hard precondition for delivery completion.
- Capture every reject (partial or full) as **structured data** with photographic proof.
- Track each parcel **delivery → arrival-at-Implant → handover**, and expose backlog to SwipeRx.
- Split and report cleanly by the three **SwipeRx services** (regular / instant / return pickup).
- Give non-drivers (DE, Implant, Station IC, Program Manager) tools that **simplify** their steps.
- Provide **role-aware in-app guidance** so any user understands their part without external training.
- Ship a production-deployable build within ~2 weeks.

### 4.2 Non-goals (v1)
- **Automated sign/stamp/OCR detection** — deferred to a fast-follow (§16).
- **Mandatory Validator review as a completion gate** — Validator monitors + flags + downloads, but does not block completion in v1 (§9).
- Real-time integration into Operator/OPV2 beyond what DE does manually (DE creates return AWBs in NV's real system and uploads the PDF).
- Automated driver-link opening at the door (a real risk — tracked as a dependency, §18/§19).
- Offline capture & sync.

## 5. Personas & roles

The interface differs by role; each user sees only their menus/actions. Superadmin sees everything.

| Persona / Role | Surface | Primary responsibility |
|---|---|---|
| **Courier / Driver** | Courier app (tokenized link, no login) | Capture required POD/RDO documents; record any reject; cannot finish incomplete |
| **Implant** | Operator dashboard | Upload SwipeRx data → OC template; create per-AWB driver links; scan arrivals; run handover sessions. **Implant and DE are the same team** (interchangeable). |
| **DE** | Operator dashboard | Everything Implant does; **downloads the reject list and creates the rejection OC** (re-uploaded via Order creation, §7.3) for returns; supports the internal-NV send flow. Same team as Implant |
| **Station IC** | Operator dashboard | Works the **reject-return worklist**: sees reject AWBs (incl. a "not downloaded" segment), **downloads the reject list**, and creates the **rejection OC** re-uploaded via Order creation (§7.3/§11.4). *(No PDF-label printing — reworked Round 5.)* |
| **Validator** | Operator dashboard | Monitor RDO validity (forward + return), flag valid/invalid + reason, **download data** for internal performance (non-blocking in v1) |
| **Program Manager** | Operator dashboard | Full oversight + deep-dive; decide next steps; **owns the internal-NV document-send flow** |
| **Superadmin** | All | Everything + **register users and assign roles** |
| **SwipeRx Ops (client)** | SwipeRx page | **Non-editable but downloadable** report: filter (by origin/TMP, OC-date range, status, …) + export reject + validity data; grouped Forward / Reject / Special-Case return (Implant-backlog tab **deferred**, §11.8) |

> **Role relationships:** **Implant and DE are the same team** (interchangeable; multi-role accounts make this natural). Program Manager ≈ Superadmin minus user registration.

## 6. Services & separation

SwipeRx has three movement services. The **service ID** is the separator; the app tags every order with its service and can **filter/report by service**. Rejects/returns on regular & instant remain **billed under their originating service**.

The Implant/DE **picks the service up front**. **The internal codes are never shown in the UI (Round 5)** — the operator picks by name (Regular / Instant (Sameday) / Return pickup), and picking a service auto-displays its **shipper ID, shipper name, and corporate branch** as **read-only** metadata from the **shipper-master table** below. In the generated NV upload file the internal model is unchanged: col B `global_shipper_id` is **always the master `11398423`**; the service is set by the **branch id in col AE**; `service_level` = STANDARD / SAMEDAY.

**Shipper master (corrected 14 Jul — real shipper IDs; replace the mockup's `SWRX-ID-014` placeholders):**

| UI service name | Shipper ID | AE | service_level | Report group | Notes |
|---|---|---|---|---|---|
| **Regular** | `11398224` | 1 | STANDARD | Forward | Forward DN flow (§7.1) |
| **Instant (Sameday)** | `11549046` | 3 | SAMEDAY | Forward | Forward DN flow (§7.1) |
| **POD Return** *(the reject of a forward)* | `11398434` (RTS) | 2 | STANDARD | **Reject** | Created via the **Reject OC** (§7.3); this is what "S3" now means — the return of a rejected forward (from Regular **or** Instant) |
| **Return Pickup** *(special case)* | `11398224` (**Regular**) | 1 | STANDARD | **Special-Case return** | Now runs on the **Regular** shipper, **differentiated by an `AWBR` prefix** on the AWB (SwipeRx pre-supplies `AWBR-…` + invoice, §7.4) |
| *(master — col B always)* | `11398423` | — | — | — | The global master shipper in col B |

> **Shipper name / corporate branch** display values come from this master (the shipper is SwipeRx's NV account). If a specific per-service name/branch string is required for display, it is the one remaining shipper-master detail to confirm (§19 #21).

**Reporting/grouping vocabulary (Round 5, aligned to the redefinition above):** the **three top-level report groups** are **Forward** (Regular or Instant), **Reject** (= POD Return — a forward the driver reported as rejected), and **Special-Case return** (the `AWBR`-prefixed return pickup on the Regular shipper). The Special-Case return group has **no service sub-filter**.

## 7. Document model & flows

### 7.1 Forward delivery — required capture set

For **regular** and **instant** services, a normal (no-reject) forward delivery walks the courier through this **phased order (Round 5)**:

1. **Pharmacy POD** — photo of the pharmacy storefront / premises.
2. **Receiver POD** — photo of the person receiving.
3. **Delivery Note (DN) — whole document** — **one single DN per AWB with two sections: the top for the forward delivery, the bottom for the return (used only if there's a reject).** There is **no separate "Faktur"** (confirmed 14 Jul). For a normal delivery the courier captures the DN and must **confirm the (forward/top section) is signed + stamped** (required attestation — see §9; a fast-follow LLM/OCR check will replace the manual tick).
4. **SP-Manual check** — SP type is **not** in the source data; the **rider identifies which POs are "SP Manual" at the door** and captures **one SP photo per flagged PO** (rider-driven, not a pre-counted set).
5. **"Any partial reject?" inline question** — after the SP check, the app asks whether any item is rejected. **Partial reject is an inline branch, not an up-front outcome (Round 5).** If yes → the reject capture set (§7.2). If no → confirm.

**Capture input:** the **live in-app camera is the default/preferred** path (app-stamps the time). **A secondary "Upload instead" fallback is allowed (Round 5)** for when the camera can't open (e.g. an NV-app webview without `getUserMedia`) — this resolves the former dead-end. The courier **cannot confirm delivery** until every required photo is captured **and** the signed+stamped attestation is ticked (completeness gate, §9).

**Total koli shown = the sum of each PO's koli.** The courier header shows the **AWB number on line 1** (without the literal word "AWB") and the **pharmacy name on line 2**; documents reference the **SwipeRx AWB** (the tokenized link is per SwipeRx AWB), not the Ninja AWB. A final step reminds the courier that **delivery must ALSO be confirmed in the Ninja driver app** (§7.2.2).

### 7.2 Forward delivery — partial reject

Reject in Alpha 0.1 is **flag + photographic proof only** — the courier indicates the delivery is a partial (or full) reject and captures proof; there is **no per-PO/quantity entry** (`RejectLine` dropped). **Partial reject is reached via the inline "any partial reject?" question (§7.1 step 5); full reject is chosen up front.** The reject capture set (Round 5):
- **DN return section (bottom) — two shots:** a **close-up of the DN's return section** AND a **full-page view of the DN**, with a required **signed + stamped attestation** on the return section. *(This is the bottom section of the same single DN, not a separate document — confirmed 14 Jul.)*
- **One overall photo of the rejected goods / parcel** (not a photo per item).
- The **forward AWB sticker** photo (traceability).
- **Last step — screenshot & inform Station IC:** the app instructs the courier to **screenshot the page and inform their Station IC**; the page **lists the AWB(s) to be returned**. This is the final step of a reject flow.

> There is **no driver-facing return-AWB step**; the return is created later by the operator via a **rejection OC** (§7.3). Every return is **flagged with photographic proof at the door**, not captured as per-PO quantities.

### 7.2.1 Failed delivery — courier cannot complete

Distinct from a reject: here **nothing is handed over** and no POD/RDO set can be captured (the delivery attempt itself failed). Failed delivery is a **two-step flow (Round 5): (1) enter reason → (2) capture/upload the proof photo.** Instead of the §7.1 set, the courier records:

- **Fail reason** (single-select, **coded list LOCKED 09 Jul**, bilingual ID/EN in the courier app):

  | code | ID | EN |
  |---|---|---|
  | `cancelled` | Penerima membatalkan pesanan | Recipient cancels the order |
  | `not_ordered` | Penerima tidak memesan paket | Recipient did not order the package |
  | `address_wrong` | Alamat tidak lengkap atau salah | Address incomplete or wrong |
  | `moved` | Penerima sudah pindah dari lokasi | Recipient has moved from the location |
  | `no_receiver` | Penerima tidak ada di lokasi | Recipient not at the location |
  | `reschedule` | Penerima meminta untuk penjadwalan ulang | Recipient asks for a reschedule |
  | `office_closed` | Kantor tutup | Office closed |
  | `force_majeure` | Bencana alam, huru-hara, atau musibah/kecelakaan | Natural disaster, riot, or accident |
  | `refused_sign` | Penerima tidak mau menandatangani dokumen | Recipient refuses to sign the documents |

- **Proof photo with a trustworthy timestamp — live in-app capture is the default/preferred path.** The app opens the in-app camera and **stamps the capture moment** (`timestamp_source=camera`). **A secondary "Upload instead" fallback is now allowed (Round 5, reverses the 09 Jul "no gallery" lock)** for when the camera can't open — an uploaded file uses its **EXIF** timestamp (`timestamp_source=exif`). Not forensic proof (no hardware attestation) — it's deterrence. Drivers still see a friendly "photos are taken live and the time is logged for review" note (with the upload path as the escape hatch). *(The "you can't upload from your gallery" microcopy of §3 is now softened accordingly.)*
- Optional free-text note; GPS if permitted.

**Completeness gate** still applies: the courier cannot confirm a failed delivery until a reason **and** a live-captured, timestamped proof photo are present. Result: AWB → **DELIVERY_FAILED**. There is **no return-AWB track** (nothing was delivered → nothing to reject). Re-attempt = the **same link re-opens** (no new AWB); prior attempts kept in history, within the 30-day window (LOCKED, §10).

> **"No return to collect" is NOT a failure.** When the consignee simply has no goods to return, the courier chooses **complete/success** (not a fail reason) **but must still collect the return form signed by the consignee even though it is left blank** — the success flow requires that blank-but-signed return-form photo (**full-page view only, no close-up**, Round 5). *(Distinct from `refused_sign`, which is a real failure.)*
>
> **Service-aware outcomes (Round 5):** for the **Special-Case return service (S3)** the first outcome reads **"No return to collect (success)"** instead of "Delivery (normal)", and the reject/failed wording adapts to the return context (a "return pickup", not a "delivery").

### 7.2.2 Confirm, resubmit & the driver-app reminder

- **Delivery must ALSO be confirmed in the Ninja driver app (Round 5).** SwipeRx Operator captures the RDO/POD, but it does **not** close the delivery in NV's system — the success screen (and the full-reject / failed screens) explicitly tell the courier to complete the **matching action in the Ninja driver app**.
- **"Something wrong?" → confirm → resubmit/restart.** A small, guarded **"Something wrong?"** control replaces the old "Start next delivery" button (which was **removed**, Round 5). It routes through a **confirmation interstitial** before resubmitting/restarting, so a misclick can't wipe a good submission. The restart guard still locks once a Validator flags or DE acts on the return (§10, §19 #20).
- **Terminal / resume:** a returning link within 30 days resumes in place; a terminal state renders read-only.

### 7.3 Reject-return handling (post-delivery, back office) — REWORKED (Round 5)

The 10 Jul review **replaced** the old "DE creates the return AWB in NV's system + uploads a PDF label → Station IC prints it" model. There is **no PDF-label printing**. The new flow, surfaced as a **reject-return worklist**:

1. A courier's reject (§7.2) **populates the reject list** with the AWB(s) to be returned.
2. The operator (Implant/DE — same team) **downloads the reject list** and **creates a rejection OC template** for the return. *(⚠ this needs a **separate template engine** from the forward OC — the "reject-item OC" — §19 #23. It is distinct enough to get its **own Order-creation menu**, §11.2.)*
3. The **rejection OC is re-uploaded through Order creation** (as a rejection intake), the same way a forward OC is created.
4. The system **tracks & logs** the return end-to-end (it appears in the report's **Reject** group, §11.8).
5. The worklist shows a **stage badge** per AWB and a **"Not downloaded" filter/segment** so the operator can see which reject AWBs have **not yet been picked up** for OC creation (Round 5).

**Working assumption on the return AWB (format still TBD — §19 #15, keep open):** the return AWB is **minted when the rejection OC is created + re-uploaded** (step 2–3), not at reject time. Until then the worklist shows the AWB in a **"pending download / pending OC"** stage with no final return-AWB number. The `RET-NVID…` string in the current mockup is a **placeholder format** — the real scheme is confirmed with the AWB-naming decision (§19 #15). *(Build to this assumption; revisit if Baskoro confirms a pre-assigned return number instead.)*

*(This supersedes the per-hub email→print→acknowledge path. The hub→email distribution list (§19 #12) and notify-only recipients remain open, but they are no longer on the critical path to producing a return — the rejection OC is.)*

### 7.4 Return pickup — Special-Case return (corrected 14 Jul)

**Terminology (14 Jul):** "Service 3 / POD Return" now means **the reject of a forward delivery** (§7.3, the **Reject** group). The **Return Pickup** described here is a **distinct "special case"**: SwipeRx pre-supplies a return AWB and asks NV to collect goods from a pharmacy back to the SwipeRx WH.

- It now runs on the **Regular shipper (`11398224`, AE=1)** — **not** a separate return shipper — **differentiated by an `AWBR` prefix** on the AWB (`AWBR-…`), plus the SwipeRx-supplied invoice number. from = pharmacy, to = SwipeRx WH; master `11398423` in col B.
- It enters the app as a **different, simpler process** (no DN, no forward POD set). The `delivery_instructions` (col R) is the **short "you MUST open the link" instruction**; the item list + invoice ride **behind the link**.
- The courier **prepares the BA themselves** and captures it + the returned goods; on the return service the first outcome is **"No return to collect (success)"** (§7.2.1). *(Detailed capture set to be finalized — §19 #6.)*

### 7.5 Internal-NV document-send flow

A special flow where the trigger is **internal to Ninja Van** (not SwipeRx): sending documents that must come back **signed + stamped** (the same RDO obligation), then returned to SwipeRx. A variant is "just send docs" with no return.
- **Owned by Program Manager**; likely **created by DE** (confirm).
- Behaves like a forward flow for the sign+stamp-and-return portion.
- **Open:** how this is *differentiated* from a normal forward AWB in data/reporting is not yet decided (§19 #3).

### 7.6 End-to-end operational flow (regular / instant)

```
SwipeRx sends data
  → Implant/DE uploads it via Order creation (picks service by name; single-day; all-or-nothing) → app generates the OC .csv with the per-AWB courier link injected
  → Implant/DE uploads the OC .csv into NV's internal logistics system (upload kept in history)
  → Courier opens the link at the door → captures the required POD/RDO set (SP-manual check + inline "any partial reject?") → confirms → (also confirms in the Ninja driver app)
  → [if reject] the AWB lands on the reject list → Implant/DE downloads it → creates a rejection OC → re-uploads via Order creation (reject-item menu) → tracked in the report's Reject group
  → Documents/rejected goods arrive at Implant → Implant scans the barcode → status: Arrived at Implant (awaiting handover)
  → Implant builds a handover session (by day) → submits it to SwipeRx → awaiting SwipeRx receipt → SwipeRx confirms received (or rejects docs → scanned back with a coded reason)
  → Program Manager oversees; SwipeRx views/downloads the report (grouped by origin: Forward / Reject / Special-Case return)
```

## 8. Scope

| In scope (v1) | Out of scope (v1) |
|---|---|
| Google Workspace SSO (staff + SwipeRx); Superadmin user registration + role assignment | Automated sign/stamp/OCR detection (fast-follow, §16) |
| Order creation (SwipeRx data → OC `.csv`, 2 menus: normal + reject-item) + per-AWB unguessable courier link | Mandatory Validator gate on completion |
| Downloadable links/OC output for pasting into NV's logistics system | Real-time Operator/OPV2 integration (DE bridges manually) |
| Courier app: forward DN capture set (POD ×2, DN, SP-per-Manual-PO), completeness gate, partial/full reject, Service-3 return-pickup flow | Automatic driver-link opening at the door |
| Reject-return worklist: reject list → download → rejection OC → re-upload via Order creation → tracked (no PDF-label printing) | Offline capture & sync |
| Arrival-scan + handover sessions (incl. handover-rejection note) | |
| Validator monitoring + validity flagging + data download (non-blocking) | |
| Program Manager oversight/deep-dive; internal-NV send flow | |
| SwipeRx report: filter + download, incl. Implant backlog visibility | |
| Service split (regular / instant / return pickup) by service ID | |
| 30-day retention of POD photos + courier links; courier resubmit within window | |
| Role-aware in-app guidance | |
| Bilingual (ID/EN) courier app | |

## 9. Compliance control model (v1)

The core control is a **required-photo completeness gate + a required signed+stamped attestation** on the DN, not human/ML verification:

- **Gate:** "Confirm delivery" is disabled until **every required document photo** (per §7.1/§7.2) is captured **and** the courier has ticked the **DN signed+stamped attestation**. The button states the reason while blocked.
- **Signed+stamped attestation is REQUIRED** (reverses the v2.1 no-checkbox stance): the courier confirms the DN carries the receiver's name, signature and stamp. A **fast-follow LLM/OCR check** (§16) will replace this manual tick.
- **No mandatory Validator step** — Validator may not be staffed at launch. Validator can still **flag** validity + reason for monitoring and **download** data, but completion does **not** block on a Valid verdict.
- **Fast-follow:** sign/stamp *quality* detection (§16) will pre-screen and, if desired, re-introduce a Validator/auto gate in place of the manual attestation.

## 10. AWB status lifecycle

```
CREATED → DELIVERED → ARRIVED_AT_IMPLANT → HANDED_OVER → AWAITING_SWIPERX_RECEIPT → SWIPERX_RECEIVED
   │            │                                                     └─(SwipeRx rejects a doc)→ SWIPERX_REJECTED → (scan back at Implant, coded reason) → re-handover
   │            └─(if reject)→ RETURN_REJECTED → RETURN_OC_CREATED ─┘ (reject-return track: reject list → rejection OC → tracked, §7.3)
   └─(attempt failed)→ DELIVERY_FAILED ─(re-attempt: same link re-opens, within 30d)→ CREATED/DELIVERED
```

- **CREATED** — link generated, injected into the OC `.csv`, uploaded to NV logistics.
- **DELIVERED** — courier passed the completeness gate + signed+stamped attestation and confirmed (POD/RDO captured; reject flagged with proof if any). *(Also requires the separate confirmation in the Ninja driver app, §7.2.2.)*
- **DELIVERY_FAILED** — courier could not complete; two-step: coded fail reason + timestamped proof photo (§7.2.1). Re-attempt = **same link re-opens** (no new AWB); prior attempts kept in history, within the 30-day window.
- **RETURN_REJECTED** — a reject was recorded; the AWB is on the **reject list**, awaiting rejection-OC creation.
- **RETURN_OC_CREATED** — the operator downloaded the reject list and created + re-uploaded the **rejection OC** (§7.3). *(Replaces the old RETURN_AWB_PENDING/CREATED + PDF-label states.)*
- **ARRIVED_AT_IMPLANT** — Implant scanned the barcode; awaiting handover.
- **HANDED_OVER → AWAITING_SWIPERX_RECEIPT** — Implant submitted the handover session to SwipeRx; awaiting SwipeRx's receipt confirmation (Round 5).
- **SWIPERX_RECEIVED** — SwipeRx confirmed receipt of the session's docs.
- **SWIPERX_REJECTED** — SwipeRx rejected one or more docs; each returns to Implant, is **scanned back**, and gets its **own coded reason** (⚠ reason set + next-action types — §19 #24), then re-enters handover.
- **Validity** (Valid/Invalid + reason) is an **independent, non-blocking overlay** set by the Validator.
- **Report note (Round 5):** handover state is **shown within the single status column** of the SwipeRx report — there is no separate handover column/filter.
- **⚠ Canonical status vocabulary** (this list) must be the **single source of truth** shared across the driver app, Operator, and the report legend — §19 #25.
- **Retention:** POD photos + links accessible **30 days**; courier may **resubmit** within the window.

## 11. Functional requirements

Priority: **P0** required, **P1** strongly desired, **P2** nice-to-have.

### 11.1 Auth & user management
| ID | Requirement | Pri |
|---|---|---|
| FR-AUTH1 | Staff and SwipeRx sign in via **Google Workspace SSO** (OAuth2/OIDC). SSO authenticates; the app authorizes by role | P0 |
| FR-AUTH2 | A signed-in Google account with **no assigned role** sees "contact admin for access" | P0 |
| FR-AUTH3 | **Superadmin** registers users (by Google email) and assigns **one or more roles** (checkboxes); deactivates users; changes take effect on next sign-in | P0 |
| FR-AUTH4 | **Multi-role accounts** (`User.roles[]`) — one person can hold several hats (e.g. Implant + Validator) without superadmin. Role set: Superadmin, Program Manager, DE, Implant, Station IC, Validator, SwipeRx (+ Courier via token, no login). **Implant and DE are the same team** (interchangeable). The role landing/launcher offers a starting point per hat | P0 |
| FR-AUTH7 | **Dev-login stopgap** (`POST /api/auth/dev-login`, gated by `DEV_LOGIN_ENABLED`) lets a registered email sign in with no Google flow, for building before the OAuth client exists; **must be off in production** | P0 |
| FR-AUTH5 | Restrict SSO to the approved **Workspace domain(s)** where feasible; else allow-list by registered email | P1 |
| FR-AUTH6 | Couriers use **unguessable tokenized links** only (no login) | P0 |

### 11.2 Order creation & link creation  *(renamed from "Order intake", Round 5)*
| ID | Requirement | Pri |
|---|---|---|
| FR-OC0 | **Three separate left-nav menus (confirmed 14 Jul):** (1) **Order creation** — normal OC from SwipeRx TMP input; (2) **Reject OC** — the reject-item/return OC upload (a **distinct template engine + upload path** from the normal OC, §19 #23); (3) **Reject returns** — the worklist that populates from courier rejects, where the operator downloads the reject list before generating the Reject OC (§11.4). These stay distinct — not merged | P0 |
| FR-OC1 | **OC = 3 explicit steps.** (1) Implant/DE uploads the SwipeRx TMP + **picks the service up front — by name, NOT S1/S2/S3 codes** (which are internal only); picking a service **auto-shows read-only shipper ID, shipper name, corporate branch** (from the shipper master, §19 #21); date selection is a **single day, not a range** (Round 5); (2) the app generates the NV upload file with the **driver link auto-injected into the delivery-instruction column**; (3) download → upload into NV's internal system. Preview (no writes) + Create (commit) | P0 |
| FR-OC2 | Upload/commit **creates orders**; each AWB gets a **unique, unguessable courier link** (`secrets.token_urlsafe`, **not** derived from the AWB); `/api/c/<token>` resolves it. The link is **per SwipeRx AWB** | P0 |
| FR-OC3 | The AWB carries its **service** and the **PO lines** (PO number, quantity/koli). **SP type is not stored** (the rider identifies SP-Manual POs at the door). Shipper model: col B master `11398423`, service via **branch id AE** (1/3/2). **AWB naming (proposed 14 Jul, §19 #15):** we generate **only the base Ninja AWB from the SwipeAWB** (min 11 / max 29 chars) — proposed **`SWRX` + SwipeAWB** (e.g. `AWB02S757` → `SWRXAWB02S757`), Return-Pickup prefixed **`AWBR`**. **We do NOT generate the collie children** — NV's internal system **auto-creates `-01, -02, … -DO`** (the `-DO` = document piece) | P0 |
| FR-OC4 | **Two output files (confirmed 14 Jul):** (1) the **OC template `.csv`** with the courier link **injected into the driver-instruction column** (upload this into NV's system); (2) a **link-map `.csv`** — one row per **SwipeAWB = Ninja AWB = link** (for records / re-paste). Both retained in the upload history | P0 |
| FR-OC5 | **All-or-nothing commit (Round 5):** if **any** row fails validation, **the entire file is rejected** (no partial create). Per-row errors are still reported so the operator can fix and re-upload. *(Supersedes the v2.2 "valid rows commit" behaviour and makes the empty-upload guard moot.)* | P0 |
| FR-OC6 | **Upload history:** after a successful create, keep a **history table of successful uploads** with the created **`.csv` file attached** for re-download/audit | P0 |
| FR-OC7 | **Hub-assignment re-upload stage:** after NV creates the OC and assigns a destination hub per piece, Implant re-uploads AWB↔hub into NV — **the engine does NOT derive the hub**; the re-upload keys on the **AWB naming system** (pending team confirmation of that scheme) | P1 |
| FR-OC8 | Single manual order entry available | P1 |

### 11.3 Courier app — capture
| ID | Requirement | Pri |
|---|---|---|
| FR-D1 | Link resolves to one **SwipeRx AWB**, no login; **phased wizard, no scrolling** (step N of M). **Header:** AWB number on line 1 (no literal word "AWB"), pharmacy name on line 2. **Order context shows:** service, shipper ID, shipper name, hub, address, **total parcels (koli = sum of each PO's koli)**, and **per-PO details incl. that PO's koli**. Documents reference the **SwipeRx AWB**, not the Ninja AWB (Round 5) | P0 |
| FR-D2 | Required forward set (phased, Round 5): **Pharmacy POD → Receiver POD → single DN whole document, forward/top section signed+stamped → SP-Manual check** (rider flags SP-Manual POs, one photo each) → **inline "any partial reject?" question** → confirm. A **required signed+stamped attestation** accompanies the DN (§9). The DN has two sections (top forward / bottom return); no separate Faktur | P0 |
| FR-D3 | One capture slot per required photo; the **live in-app camera is the default/preferred** input (app-stamped `timestamp_source=camera`); a **secondary "Upload instead" fallback is allowed** (Round 5) for when the camera can't open (EXIF time, `timestamp_source=exif`); client-side downscale. Friendly "photos are logged for review" note | P0 |
| FR-D4 | **Completeness gate:** "Confirm delivery" disabled with a stated reason until all required photos are captured **and** the signed+stamped attestation is ticked (§9) | P0 |
| FR-D5 | **Partial reject — inline branch (Round 5), flag + proof only:** reached via the "any partial reject?" question; captures the **DN return section (bottom) as two shots (close-up of the return section + full-page DN) with a signed+stamped attestation**, **one overall rejected-goods/parcel photo**, and the **forward AWB sticker** photo. **No per-PO/quantity entry** (`RejectLine` dropped) | P0 |
| FR-D6 | **Full reject (Retur Semua):** chosen up front; same reject capture set (DN return section ×2 + attestation, rejected-goods photo, AWB sticker) | P0 |
| FR-D7 | **Last step on any reject — screenshot & inform Station IC:** the app instructs the courier to screenshot the page (which **lists the AWB(s) to return**) and notify their Station IC | P0 |
| FR-D8 | **No** driver-facing return-AWB step → confirmation preview → double-check → submit → success. **Success/full-reject/failed screens remind the courier to complete the matching action in the Ninja driver app** (§7.2.2). A guarded **"Something wrong?" → confirm → resubmit/restart** replaces the removed "Start next delivery" button | P0 |
| FR-D9 | **Resume in place** within the 30-day window; **resubmit** allowed | P0 |
| FR-D10 | Bilingual ID/EN toggle, ID default; ≥48px touch targets; document "See example" guides | P1 |
| FR-D11 | Capture timestamp + GPS (if permitted) on confirm | P1 |
| FR-D12 | **Failed delivery — two-step (Round 5):** (1) select a **coded fail reason** (9-code list, §7.2.1) → (2) capture/upload a **proof photo** (app-stamped time, upload fallback allowed). Gate blocks confirm until reason + timestamped proof present → status `DELIVERY_FAILED`. Re-attempt = same link re-opens | P0 |
| FR-D13 | **"No return to collect" is a SUCCESS path, not a failure:** courier chooses complete/success but must still capture the **return form signed by the consignee even though it is left blank** (full-page only, no close-up). For the **return service**, this is the **first outcome** ("No return to collect (success)"), §7.2.1 | P0 |

### 11.4 Reject-return worklist  *(reworked Round 5 — no PDF-label printing)*
| ID | Requirement | Pri |
|---|---|---|
| FR-R1 | A courier reject **populates the reject list** with the AWB(s) to return; the worklist shows them with a **stage badge** and a **"Not downloaded"** filter/segment so the operator sees which are not yet picked up | P0 |
| FR-R2 | The operator (Implant/DE) **downloads the reject list** and **creates a rejection OC template** for the return → status `RETURN_REJECTED` | P0 |
| FR-R3 | The **rejection OC is re-uploaded through Order creation** (the reject-item OC menu, FR-OC0) → status `RETURN_OC_CREATED`; the system **tracks & logs** the return (appears in the report's **Reject** group) | P0 |
| FR-R4 | *(⚠)* The **rejection OC uses a distinct template engine** from the forward OC (maps forward AWB → return) — §19 #23 | P0 |
| FR-R5 | *(De-scoped from the critical path)* Hub→email notification of returns (per-hub distribution list, §19 #12) may still be layered on later; it is **no longer required to produce a return** (the rejection OC is). No print/label/acknowledge tracking | P2 |

### 11.5 Arrival scan & handover  *(session-receipt loop, Round 5)*
| ID | Requirement | Pri |
|---|---|---|
| FR-H1 | Implant **scans the barcode / enters the AWB** on arrival (scanner-as-keyboard, one line per beep) → status **Arrived at Implant (awaiting handover)**. Keep the **scan/handover action page** and add a **tracking tab group** listing docs **separated by day and status** (Round 5) | P0 |
| FR-H2 | **Build handover session:** scan all docs prepared for handover into an **open session** with a **running count, grouped by day**. **No session cap** (Round 5 removed the earlier cap; sessions run at 300–500 docs/day) | P0 |
| FR-H3 | **Hand over:** one action submits the whole session to SwipeRx → **`AWAITING_SWIPERX_RECEIPT`** | P0 |
| FR-H4 | **SwipeRx receipt:** SwipeRx confirms receipt (`SWIPERX_RECEIVED`); any docs SwipeRx **rejects** come back to Implant | P0 |
| FR-H5 | **Scan rejected docs back:** Implant scans each returned/rejected doc; **each gets its own coded reason** (they differ per doc) and a **"next action pending"** type. A **dedicated rejected-docs view** lists them with the pending action. *(⚠ the coded reason set + the "next action" type set — §19 #24)* | P0 |
| FR-H6 | Handover state + timestamps + per-doc rejection reasons are stored and visible to PM and SwipeRx | P0 |

### 11.6 Validator (non-blocking)
| ID | Requirement | Pri |
|---|---|---|
| FR-V1 | **Dedicated Validator page.** Validator reviews RDO (forward + return) and flags **Valid / Invalid**; on Invalid picks **coded reasons, multi-select**: (a) DN missing / not signed+stamped; (b) Return Form missing / not signed+stamped (**whenever a return form is expected — including the "no-return = success + blank-but-signed form" case (§7.2.1), not only when a reject was submitted**); (c) SP Manual missing vs DN; (d) invoice number mismatch. **Non-blocking** in v1; invalid verdict is **recorded-only** (no notification loop; appears in the download + PM view) | P0 |
| FR-V2 | Validator **downloads** validity data for internal performance measurement | P0 |
| FR-V3 | Data model + UI are designed so a **blocking gate and ML pre-screen can be switched on** in a fast-follow | P1 |

### 11.7 Program Manager
| ID | Requirement | Pri |
|---|---|---|
| FR-M1 | Overview with **rate KPIs** (% completed, % RDO validated, % return recorded; suggested adds: % failed, % invalid RDO, avg time-to-handover, backlog aging) + clickable drill-downs; editable date range; filters incl. **service** | P0 |
| FR-M1a | **Full AWB list below the KPI cards (Round 5):** shows all AWBs by default; clicking a KPI card's **"view detail"** swaps the list to that KPI's subset. (Fixes the prototype's "[object Object]" detail-title bug in passing.) | P0 |
| FR-M2 | Deep-dive over all AWBs with full filters + export | P0 |
| FR-M3 | **Owns the internal-NV send flow** (§7.5): trigger/track document-send items | P1 |

### 11.8 SwipeRx report  *(reworked Round 5)*
| ID | Requirement | Pri |
|---|---|---|
| FR-X1 | Data is **non-editable but prominently downloadable** (a clear export link, not a "read-only" dead end). **Filters must actually filter the table** | P0 |
| FR-X2 | **Grouped by ORIGIN / TMP** (e.g. TMP Depok, Bandung, Surabaya…), **not by station**. **Three top-level groups:** **Forward** (Regular or Sameday/Instant), **Reject** (from the driver-app forward report), **Special-Case return** (the third service) | P0 |
| FR-X3 | **Filters:** an **Origin** filter (per submitted TMP); **date = a range (from → to)** referring to the **internal OC-input date** (when data was loaded from the TMP), **not** delivery date; **service filter only where applicable** (Forward & Reject have services; Special-Case return has none — hide it there); **search by SwipeRx AWB or PO number**. **Removed:** the Area and Pharmacy filters. **"Hub" is relabelled "Area"** | P0 |
| FR-X4 | **Row identity = SwipeRx AWB** (not Ninja AWB — 1→many). Clicking a row opens a **right-side popup drawer** showing a **status-change timeline**, the **list of Ninja AWBs** under that SwipeRx AWB (with status/receiver), and the **list of POs tagged manual/electronic**. *(Round 3: no photo per Ninja AWB in the drawer — just the AWB list.)* **Reject details live in a separate tab group**; clicking a rejected AWB **auto-switches to the Reject tab** | P0 |
| FR-X5 | **Handover status is shown within the single status column** (no separate handover column/filter). An **on-page status legend/guide** defines every status level — **collapsed by default, in a distinct colour**. *(⚠ canonical status vocabulary — §19 #25)* | P0 |
| FR-X6 | **Download** the filtered set (CSV) — **one row per SwipeRx AWB** | P0 |
| FR-X7 | ~~Implant backlog tab~~ **Deferred** — arrival/handover data accrues for a later tab | P2 |

### 11.9 In-app guidance
| ID | Requirement | Pri |
|---|---|---|
| FR-G1 | A **role-aware "How this works" guide** in-app: on first sign-in and always reachable, explaining that role's steps in plain language (ID/EN on the courier app) | P0 |
| FR-G2 | Contextual helper text on each key screen (what to do, what "done" looks like) | P1 |

### 11.10 Non-functional
| ID | Area | Requirement |
|---|---|---|
| NFR-1 | Scale | ~300–1000 parcels/day; ~300 concurrent courier sessions; ~50 hubs. Staff headcount (informs concurrency): DE 1–2, Implant 2–5, Validator 1–3, PM 2–4, Station IC ~50 hubs × (~4–5 notified / ~1–2 acting) |
| NFR-2 | Performance | Key screens interactive < 1.5s under expected load |
| NFR-3 | Retention | POD photos + courier links retained + downloadable **30 days**; resubmit within window |
| NFR-4 | Security | SSO for staff/client; roles enforced server-side; courier tokens cryptographically random; least-privilege; audit log |
| NFR-5 | Data residency | Confirm whether pharmacy documents must stay in-country / in-house (drives storage + future ML choices) — §19 #7 |
| NFR-6 | Deployability | Deploys on **Substrait** upload-mode (FastAPI :8000 `/health` `/api` + React/Vite :80; OceanBase + Flyway); source + Dockerfiles only, platform owns k8s (§17) |
| NFR-7 | Brand | Conforms to the NV Design Master (red `#EE1B2C`, Montserrat, status palette) |
| NFR-8 | Media | Photos downscaled client-side; stored in an **external S3-compatible object store** (not part of the Substrait contract — §15, §19 #14) with signed, time-limited download URLs |

## 12. Data model (entities & key fields)

| Entity | Key fields |
|---|---|
| User | id, name, google_email, active — **+ `user_roles` (many-to-many)**; a user holds **one or more** of superadmin / program_manager / de / implant / station_ic / validator / swiperx |
| OrderCreation *(was OrderIntake)* | id, **oc_kind (normal / reject_return)**, source_file_ref, **oc_output_ref (`.csv`, link injected)**, service_code (internal), shipper_id, shipper_name, corporate_branch, **origin_tmp** (e.g. TMP Depok), **oc_date (single day)**, uploaded_by, uploaded_at, row_count, awb_count, piece_count, status, error_summary. **All-or-nothing:** a create is committed only if every row validates. Retained in the **upload-history** table with its `.csv` attached |
| Awb | swiperx_awb (row identity), **ninja_awbs[] (1→many, MPS children)**, service_id, shipper_id/shipper_name/corporate_branch, origin_tmp, pharmacy_name, address, city (**"Area"**), postcode, phone, weight, koli (**= Σ Po.koli**), link_token, status, return_type (none / sebagian / semua), is_return, invoice, item_detail, delivery_instructions, created_by, intake_id, created_at. **hub_code is NV-assigned via a second upload (not derived here)** |
| ShipperMaster | service_code, shipper_id, shipper_name, corporate_branch — the read-only lookup shown at Order creation (⚠ source to be supplied, §19 #21) |
| PoLine | id, awb_id, po_number, koli, **sp_manual_flag (rider-set at the door)**. *(No `sp_type` in the source; the rider flags SP-Manual POs. The report tags each PO manual/electronic from this flag.)* |
| DocumentCapture | id, awb_id, doc_type (pharmacy_pod / receiver_pod / **dn** (single, forward/top section) / sp_manual / rejected_goods / awb_sticker / **dn_return_closeup** / **dn_return_fullpage** / **dn_return_blank_signed**), attestation_signed_stamped (bool), po_number (for sp_manual), photo_ref, **capture_source (camera / upload)**, captured_at, gps |
| ~~RejectLine~~ | **Dropped** — reject is flag + proof only (return_type on the Awb + proof photos in DocumentCapture); no per-PO reject quantities |
| FailedDelivery | id, awb_id, fail_reason (cancelled / not_ordered / address_wrong / moved / no_receiver / reschedule / office_closed / force_majeure / refused_sign), reason_note, proof_photo_ref, proof_timestamp, timestamp_source (camera / exif), gps, created_at |
| RejectReturn *(was ReturnParcel)* | id, original_awb_id, **on_reject_list (bool)**, **downloaded (bool) + downloaded_at**, **reject_oc_id (the rejection OC that was re-uploaded, FK → OrderCreation)**, status (RETURN_REJECTED / RETURN_OC_CREATED), created_by, area, service_id, created_at. *(No PDF-sticker / print-label fields — reworked §7.3/§11.4.)* |
| ArrivalScan | id, awb_id, scanned_by, scanned_at, day |
| HandoverSession | id, created_by, created_at, day, submitted (bool), submitted_at, **swiperx_received (bool)**, **received_at**, status (OPEN / AWAITING_SWIPERX_RECEIPT / SWIPERX_RECEIVED) |
| HandoverItem | id, handover_session_id, awb_id, **swiperx_rejected (bool)**, **reject_reason_code**, **next_action_type**, **scanned_back_at** *(per-doc; ⚠ reason + next-action sets §19 #24)* |
| ValidationFlag | id, awb_id, validated_by, result (valid / invalid), validated_at — **+ `validation_reason` (coded, multi-select):** dn_missing_unsigned / return_form_missing_unsigned / sp_manual_missing / invoice_mismatch |
| MediaBlob | id (uuid), content_type, byte_size, data (LONGBLOB) — **Alpha 0.1 stopgap** store behind the storage adapter; every `*_ref` column holds an opaque key so an S3 bucket drops in later with no schema change |
| InternalSend | id, awb_id (or internal ref), created_by, owner (program_manager), send_type (docs_only / docs_with_return), status, created_at |
| AppVersion | id, version, notes, released_at — feeds the in-app "What's new" changelog |
| Notification | id, recipient_role/hub, type (return_to_print / …), awb_id, channel (in_app / email), sent_at, read_at |
| HubContact | id, hub_code, email, name, notify_role (action / notify_only), active — the per-hub email distribution list (Baskoro-supplied, §19 #12) |
| AuditLog | id, actor, action, entity, timestamp |

> **Media fields** (`photo_ref`, `awb_pdf_ref`, `proof_photo_ref`, and the report photo columns) are **object-store keys**, not DB blobs — see the storage decision in §15 / §19 #14. The relational entities above map to **OceanBase (MySQL)** tables via **Flyway** migrations, not application-side DDL (§15).

## 13. Reporting & export

**SwipeRx CSV** — **one row per SwipeRx AWB** (no per-reject-line rows; `RejectLine` dropped), grouped by **ORIGIN / TMP** (e.g. TMP Depok) into the **three groups (Forward / Reject / Special-Case return)**, columns:
`group, origin_tmp, service, oc_date, area, swiperx_awb, ninja_awbs, return_type, pharmacy_name, pharmacy_pod, receiver_pod, faktur_dn_photo, signed_stamped, sp_manual_photos, return_form_photos, rejected_goods_photo, status (incl. handover state), fail_reason, fail_proof_photo, fail_timestamp, arrived_at_implant, swiperx_received, validation_result, validation_reason`.

**Date filter = a range over the internal OC-input date** (`oc_date`), not delivery date. Handover state is folded **into `status`** (no separate column). Failed-delivery rows carry `status = DELIVERY_FAILED` with `fail_reason` + `fail_timestamp` and empty POD/return columns. **No Implant-backlog tab in Alpha 0.1** (deferred, §11.8).

Photo columns are signed, time-limited download URLs (valid within the 30-day window). In **Alpha 0.1** media is served from the in-DB stopgap store behind the storage adapter; the S3 presigned-URL path drops in later with no call-site change (§15, §19 #14). Every list/report includes **date** and **status** filters and a **service** filter.

## 14. In-app guidance (user explanation)

Per FR-G1/G2, the app ships a **role-aware guide** so a new user understands the whole app *from within it*:
- A short **first-sign-in walkthrough** per role (what you do, where, and what "done" looks like).
- An always-available **"How this works"** panel summarizing the end-to-end flow (§7.6) and this role's part.
- **Courier app:** bilingual (ID/EN), step hints, and per-document "See example" images (DN, SP Manual, POD examples) — pending the new DN mockup from SwipeRx.

## 15. Architecture (Substrait deployment stack)

The app deploys on **Substrait** (§17), whose contract fixes several choices; the rest we design to fit it.

**Platform-provided (the Substrait contract):**
- **Backend** — any stack that listens on **:8000**, serves **`GET /health`** (readiness probe), and exposes its API under **`/api`**. First build uses the scaffold's **FastAPI**. Role-gated routes; courier routes gated by **token only**.
- **Frontend** — served on **:80**, calling the backend **same-origin via relative `/api`** paths. First build uses the scaffold's **React + Vite + Tailwind** (nginx). One ingress: `/api` → backend, everything else → frontend.
- **Database: OceanBase (MySQL wire protocol)** — injected as `DATABASE_URL`; use a **MySQL driver** (`asyncmy`, `%s` placeholders), **not** Postgres/`asyncpg`. **All DDL lives in Flyway migrations** (`backend/resources/db/migration/V*.sql`, MySQL dialect) — never `CREATE TABLE` in code. The §12 entities map to MySQL tables.
- **Redis** (`REDIS_URL`) — sessions, caching, and the email-notification queue.
- **`JWT_SECRET`** — signs session/courier tokens.
- **Config & secrets** — declared in `backend/.env.example` (portal pre-creates them, filled in the portal); **public** build-time frontend vars in `frontend/.env.production` (baked into the bundle — never secrets).
- Platform owns the Kubernetes manifests + slug; **no `k8s/`** in the repo; ship source + Dockerfiles, ≤16 MB.

**We must bring (not provided by the contract):**
- **Object storage for photos + PDFs.** Substrait injects only DB + Redis + JWT — **no blob store**. Decision (§19 #14):
  - **(recommended) External S3-compatible bucket** (NV MinIO/S3 or cloud) — endpoint/key/secret/bucket as `backend/.env.example` **secrets**; backend issues **presigned, time-limited URLs**; 30-day retention via bucket lifecycle or an app cleanup job. Photos downscaled client-side before upload.
  - **(stopgap only) OceanBase BLOB** — no extra infra, but heavy at our volume (~1000/day × several photos × 30-day retention) and inefficient to serve; avoid for production.
- **Google OIDC** — client **ID** (public) in `frontend/.env.production`; client **secret** in `backend/.env.example`; backend handles the OAuth callback under `/api/auth/*`, mints a session (JWT / Redis), maps `google_email` → role; domain-restricted (FR-AUTH5). Couriers never authenticate — token links only.
- **Email** for Station-IC notifications — an SMTP/API provider (creds via `.env.example`); send via a Redis-backed job; the in-app worklist mirrors it (FR-R3).

**Seams:** return-AWB creation is **manual via DE** (PDF upload) in v1 — isolate as a seam for a future NV-system adapter. The **object-store, email, and OIDC** providers sit behind thin adapters so NV's self-hosted equivalents drop in without touching business logic.

## 16. Image detection — fast-follow (deferred from v1)

**Decision:** deferred to a fast-follow version. Rationale: no labeled training data exists yet, the new DN layout has no mockup, and the v1 completeness gate already delivers the compliance win; the ML only *accelerates* review.

When taken up:
- **Scope:** presence detection ("is there a signature AND a chop in the expected DN region"), not identity verification; a **Validator assist / pre-screen**, never a doorstep gate.
- **Options** (to choose with real data):
  - **Managed cloud API** — AWS Textract (`SIGNATURES`) / Azure AI Document Intelligence / Google Document AI for signatures. Fast to integrate, no training; but data leaves NV's network and stamp detection is weak.
  - **Self-hosted model** — a YOLO-class object detector with `{signature, stamp}` classes. Best for stamps and data residency; needs labeling + training + serving.
- **Serving note:** a self-hosted model runs as a separate service or backend dependency; Substrait's build scratch is capped (~10Gi) and the cluster is **CPU-only** — pin CPU-only builds.
- **Prereqs:** final DN layout; a labeled sample of real DN photos (collected during v1); a data-residency decision (§19 #7).

## 17. Deployment — Substrait

**Substrait is NV's internal deployment platform for Claude Code builds** (the "DIY stack"). It builds the app from its own Dockerfiles, provisions an OceanBase DB, runs Flyway, and deploys behind one ingress — the app ships **source + Dockerfiles** (`cicd/Dockerfile.backend` → :8000 `/health` `/api`; `cicd/Dockerfile.frontend` → :80); the platform owns k8s + the slug.

**Status:** the **M0 foundation + M1 OC-intake backend are deployed & verified** (09 Jul 2026) on the **public** portal (`api.substrait.build`) → live at `swiperx-operator.apps.substrait.build`. Verified end-to-end: Flyway V2–V4 applied, `/api/version` returns the Alpha 0.1 changelog, dev-login mints a session, OC preview/create match expected engine counts (S1 57/144, S2 79/210, S3 23/23), and generated courier links open. The React frontend is the next unbuilt piece.

**Production must move to NV's self-hosted Substrait** (§19 #4): the public portal is fine for pipeline tests but **cannot hold real pharmacy data** (ties to data residency, §19 #7). Migration = re-link with `--portal-url <NV portal>` and redeploy — **same contract, no code change**.

**Deploy mechanics (ops detail, not a product requirement):** the Substrait plugin isn't installed on the build device and the folder isn't a git repo, so the stock `/substrait:deploy` / `git archive` paths don't apply. The repo ships **`deploy.sh`**, which builds a forward-slash `.zip` (Python `zipfile`) and **`POST`s it to the portal upload API** (`POST https://api.substrait.build/api/deploy`, Bearer token from `.substrait/config.json`, multipart field `file`), then watches rollout via the app's own `/api/version`. Use that to redeploy.

**Still open:** NV self-hosted portal URL/access (§19 #4); object-storage bucket + creds (§19 #14); production domain + Google-OIDC client registration; email provider creds.

## 18. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Driver doesn't open the link** at the door | No capture → defeats the gate | **Top open item** (§19 #1): investigate auto-open / enforcement with ops (e.g., embed in NV app flow; block completion in NV system until submitted). Design for resubmit within 30 days |
| 2-week timeline | Scope slip | Ship P0 first: SSO, intake+links, courier gate, reject capture, return-AWB upload + Station IC, arrival/handover, SwipeRx report |
| Data residency of pharmacy docs | Compliance | Confirm early (§19 #7); pick storage + future ML accordingly |
| DN layout not finalized | Capture UI churn | Build the capture set data-driven; slot in the mockup/example images when they arrive |
| Concurrency at scale (~300 concurrent) | Contention | Stateless app tier; DB transactions on state transitions; object storage for media |
| **Real pharmacy data on the public Substrait portal** | Compliance / residency | Move production to **NV self-hosted Substrait** before real data (§17, §19 #4/#7); public portal is for pipeline tests only |
| **No object storage in the Substrait contract** | Photos/PDFs have nowhere durable to live | Integrate an **external S3-compatible bucket** (§15, §19 #14); don't rely on DB BLOBs at scale |

## 19. Open dependencies

| # | Item | Owner | Needed for |
|---|---|---|---|
| 1 | **Ensure the driver opens the link** at delivery (auto-open / enforcement) | Baskoro + ops experts | Whole capture premise |
| 2 | **Return-AWB digit format** (how NV generates the return AWB number) | Baskoro + team | §7.3, ReturnParcel |
| 3 | **Internal-NV send flow** — a flow **triggered by Ninja Van itself** (not SwipeRx) to send documents that must come back **signed+stamped** and then be returned to SwipeRx (a variant just sends docs, no return). Open sub-questions: (a) **who creates it** — PM-owned, DE-created? (b) **how is it tagged** so it's distinguishable from a normal forward AWB in the data + report (a flag? its own group?)? (c) does it reuse the forward DN capture set? *(Explained further in §7.5 — Baskoro to confirm a/b/c)* | Baskoro + PM | §7.5 |
| 4 | ~~NV self-hosted Substrait portal~~ **Substrait deploy access is available in this environment** (plugin/skill installed; `.substrait/config.json` linked to `swiperx-operator`). Alpha 0.1 stays on the **public** portal with **dummy data only**; a separate NV self-hosted portal is only needed before **real** pharmacy data | Baskoro | Production deploy off the public portal (§17) |
| 5 | **New DN mockup** (layout, two sign+stamp boxes, PO/SP columns, BA Retur box) | SwipeRx | Courier capture UI, example images |
| 6 | **Service-3 return-pickup** exact capture set (BA + goods + …) | Baskoro | §7.4 |
| 7 | **Data residency** requirement for pharmacy documents | NV / legal | Storage + fast-follow ML |
| 8 | Confirm §7.2 reject assumptions (single DN photo covers both boxes; AWB-sticker photo needed) | Baskoro | Courier reject flow |
| 9 | Confirm the §9 control model (no attestation checkbox, no mandatory Validator gate in v1) | Baskoro | Core compliance model |
| 10 | ~~OC template fields~~ ✅ **Resolved** — templates received & analysed; sp_type not in source; corrected shipper model (col B master, AE branch); hub NV-assigned | Baskoro | §11.2, §6 |
| 11 | ~~Failed-delivery re-attempt semantics~~ ✅ **LOCKED** — same link re-opens; proof retained 30 days | Baskoro | §7.2.1, §10 |
| 12 | **Hub → email distribution list** — per-hub recipients, who acts vs notify-only, and who maintains it | Baskoro | §7.3, FR-R3, HubContact |
| 13 | ~~Failed-delivery fail-reason list~~ ✅ **LOCKED 09 Jul** — 9 codes + "no-return = success + blank-signed form" | Baskoro + ops | §7.2.1, FR-D11/D12 |
| 14 | **Object storage** — S3-compatible bucket + creds (Substrait injects DB + Redis + JWT only, **no blob store**). Alpha 0.1 uses the in-DB BLOB stopgap | Baskoro / NV infra | §15, §13 |
| 15 | **AWB naming system** — 🟡 **PROPOSED 14 Jul (confirm):** base Ninja AWB = **`SWRX` + SwipeAWB** (min 11 / max 29 chars), Return-Pickup prefixed **`AWBR`**; **NV auto-creates the collie children `-01…-DO`** (we generate only the base). Confirm this base format with the team | Baskoro → team | §11.2, FR-OC3 |
| 16 | **Google OAuth client + SMTP** — 🟡 **Baskoro reports Google SSO sign-in already appears on his Substrait account** but is unsure how it's wired. **To confirm:** does Substrait provide Google SSO natively (so we consume its identity instead of registering our own OAuth client)? If yes, we may not need a separate client ID/secret. Dev-login + log-only email cover Alpha until this is clarified | Baskoro / NV infra + investigate | FR-AUTH1/AUTH7, §15 |
| 17 | **Partial-reject return-creation flow** — confirm how NV generates the AWB, then whether the operator (Implant/DE) uploads to NV to create the OC/return template (may change §7.3) | Baskoro + ops | §7.3, C15 |
| 18 | **Driver's opening context + camera fallback** — does the link open in the **NV-app webview** (which may block `getUserMedia`) or a browser? The locked live-capture policy dead-ends the courier if the camera can't open — define the fallback (file upload w/ EXIF? "open in Chrome" hint?) | Baskoro + ops | §7.2.1, FR-D3 (unhappy-flow A7) |
| 19 | **Correction / amend flow** — SwipeRx resends corrected data (wrong address/koli) after create; no void/amend path is decided. Decide: void+recreate in-app, edit, or explicitly manual/out-of-scope | Baskoro + ops | §11.2 (unhappy-flow B11) |
| 20 | **Restart-guard unlock ownership** — once the courier Restart guard engages (Validator flagged / DE acted), no unlock/correct action is defined. Proposed: an Implant/superadmin unlock in M3 | Baskoro | FR-D8 (unhappy-flow A9) |
| 21 | ~~Shipper master + link file~~ 🟢 **RESOLVED 14 Jul** — real shipper IDs set (§6: Regular `11398224` / Instant `11549046` / POD-Return `11398434` / Return-Pickup Regular+`AWBR` / master `11398423`); **two separate output files** (OC `.csv` with link injected + a SwipeAWB=NinjaAWB=link map, FR-OC4). *Only the display **shipper name/branch strings** remain to confirm if a specific label is wanted* | Baskoro | §6, FR-OC4 |
| 22 | ~~**Faktur vs Delivery-Note model**~~ ✅ **RESOLVED 14 Jul** — **no separate Faktur; a single DN with two sections (top = forward, bottom = return-if-needed).** The "return form" is the DN's bottom section, not a separate document. Design should say "DN", not "Faktur" | Baskoro | §7.1, FR-D2/D5 |
| 23 | **Reject-item OC template engine** — a **distinct engine** from the forward OC that maps a forward AWB → its return OC (fed by the reject list, re-uploaded via Order creation). Fields + forward→return mapping | Baskoro + team | §7.3, FR-OC0/R4 *(Round 5)* |
| 24 | **Handover rejected-doc vocabulary** — the set of **coded reasons** for a SwipeRx-rejected doc and the set of **"next action" types** each needs | Baskoro + SwipeRx | §11.5 FR-H5, HandoverItem *(Round 5)* |
| 25 | ~~Canonical status vocabulary~~ 🟢 **ADOPTED 14 Jul** — the **§10 status list is now canonical** (CREATED · DELIVERED · DELIVERY_FAILED · RETURN_REJECTED · RETURN_OC_CREATED · ARRIVED_AT_IMPLANT · HANDED_OVER · AWAITING_SWIPERX_RECEIPT · SWIPERX_RECEIVED · SWIPERX_REJECTED). Driver app, Operator, and the report legend all use it | Baskoro | §10, FR-X5 |
| 26 | **SwipeRx AWB ↔ Ninja AWB is 1-to-many everywhere** — the report grouping + row identity assume this; confirm it holds across all surfaces | Baskoro | §11.8, §12 Awb *(Round 5)* |
| 27 | ~~Handover receipt actor/SLA~~ 🟢 **SIMPLIFIED 14 Jul** — the "receipt" is just SwipeRx confirming in-app that they physically received the handed-over docs (any SwipeRx-role user; **no SLA in v1**). Sessions run unpaged; revisit paging only if volume proves a problem | Baskoro + SwipeRx | §11.5 |

## 20. Roadmap beyond v1
- **Fast-follow:** sign/stamp detection assist (§16); optional Validator/auto gate re-introduced.
- Real NV-system adapter for return-AWB creation (replace DE's manual PDF upload).
- Deeper SwipeRx self-service + SLA/KPI dashboards.
- Driver-link auto-open / NV-app embedding.

## 21. Glossary

| Term | Meaning |
|---|---|
| AWB (SwipeAWB) | SwipeRx shipment number; one DN and one MPS/TRID per AWB; the courier link's scope |
| DN (Delivery Note) | New single document per AWB; lists PO lines (PO number, qty, SP type); two sign+stamp boxes (forward / rejected) |
| PO line | One purchase-order row on the DN: PO number + quantity + SP type |
| POD | Proof of Delivery — here, pharmacy POD (storefront photo) and receiver POD (person photo) |
| RDO | Return Delivery Order — signed/stamped documents returned to SwipeRx |
| SP Manual | Surat Pesanan for a Manual PO; captured once **per Manual PO** |
| BA Retur | Return/reject form — now built into the DN (box 2) on forward movement; still self-prepared on Service-3 returns |
| Return AWB | Number for a returned parcel, created in NV's real system; label PDF uploaded by DE |
| MPS / TRID | Multi-parcel shipment / trip ID — now one per AWB |
| OC (Order Creation) | Ninja Van's order-creation step; the **OC template** is the standardized sheet SwipeRx-provided data is auto-converted into before per-AWB links are generated (exact fields TBD — Baskoro to provide, §19 #10) |
| DE | Same team as Implant (interchangeable); additionally downloads the reject list + creates the rejection OC for returns (§7.3) |
| Service ID | 11398224 (regular) / 11549046 (instant) / 11398423 (return pickup) — used to split + report |
| Handover session | A batch of arrived parcels Implant marks handed over to SwipeRx in one action |

## 22. Appendix A — Role capability matrix (initial)

> **Multi-role:** a user may hold several roles (`User.roles[]`); they get the union of these capabilities. **Implant and DE are the same team** — the Implant/DE columns are interchangeable in practice.

| Capability | Superadmin | PM | DE | Implant | Station IC | Validator | SwipeRx | Courier |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Register users / assign roles | ✅ | | | | | | | |
| Full oversight / deep-dive (rate KPIs) | ✅ | ✅ | | | | | | |
| Order creation → links (3-step, normal + reject-item menus) | ✅ | | ✅ | ✅ | | | | |
| Hub-assignment re-upload | ✅ | | ✅ | ✅ | | | | |
| Reject-return worklist: download reject list → create rejection OC | ✅ | | ✅ | ✅ | ✅ | | | |
| Arrival scan / handover session | ✅ | | ✅ | ✅ | | | | |
| Flag validity (coded multi-select) / download | ✅ | ✅ | | | | ✅ | | |
| Internal-NV send flow | ✅ | ✅ | (create) | | | | | |
| SwipeRx report (read/download) | ✅ | ✅ | | | | | ✅ | |
| Capture at the door | | | | | | | | ✅ (token) |

## Appendix B — Sample dataset (to be built with the new model)
To be defined once the DN mockup and service/PO examples arrive (§19 #5). Should seed at least one AWB per service, mixed SP-Manual/Electronic PO lines, one partial reject, one full return, one **failed delivery** (with timestamped proof), one arrived-awaiting-handover, and one handed-over — so every role has data on first run.

## Appendix C — Open questions for follow-up (running log)

> Living log of questions raised in review/discussion, with status. Items that become blocking dependencies graduate to §19. Add new rows as they surface; strike through when closed.

| # | Date raised | Question | Status | Links |
|---|---|---|---|---|
| C1 | 02 Jul 2026 | **OC template** — source/target columns; does the source carry **sp_type per PO**? | ✅ **Resolved** — templates received & analysed; **sp_type is NOT in the source** (rider reads Faktur at door) | §11.2, §7.1 |
| C2 | 02 Jul 2026 | **Failed-delivery fail reasons** — confirm the coded list | ✅ **LOCKED 09 Jul** — 9 codes (cancelled / not_ordered / address_wrong / moved / no_receiver / reschedule / office_closed / force_majeure / refused_sign) | §7.2.1, FR-D11 |
| C3 | 02 Jul 2026 | **Failed delivery re-attempt** — same link vs new AWB? proof retention? | ✅ **LOCKED** — same link re-opens (no new AWB), prior attempts kept; proof retained 30 days | §10, FR-D11 |
| C4 | 02 Jul 2026 | **EXIF fallback** — behaviour when no EXIF timestamp and not a live capture | ✅ **LOCKED 09 Jul** — **force live in-app capture, app-stamps time**; EXIF only a fallback; re-capture if neither. Not forensic (deterrence) | §7.2.1, FR-D3 |
| C5 | 02 Jul 2026 | **Hub → email list** — format, ownership, action-vs-notify flag | 🔲 Open — Baskoro to provide | §19 #12, FR-R3 |
| C6 | 02 Jul 2026 | **Notify-only hub recipients** — app login/role, or email-only? | 🔲 Open | §11.4 |
| C7 | 02 Jul 2026 | **SwipeRx handover rejection** — free text | ✅ Decided (free text) — revisit later | FR-H3 |
| C8 | 02 Jul 2026 | **SP Manual sample image** — still valid for v2 or superseded by the DN mockup? | 🔲 Blocked on DN mockup | §19 #5, §14 |
| C9 | 02 Jul 2026 | **Build versioning** — first build name/scope | ✅ Resolved — **Alpha 0.1**; M0+M1 backend deployed & verified 09 Jul | §1, §17 |
| C10 | 02 Jul 2026 | **Timezone/locale** for timestamps | ✅ **LOCKED** — WIB (Asia/Jakarta) everywhere | §7.2.1, §13 |
| C11 | 02 Jul 2026 | **Object storage** provider — S3-compatible bucket + creds | 🔲 Open — **Alpha 0.1 stopgap: in-DB BLOB behind the storage adapter** (S3 drops in later) | §19 #14, §15 |
| C12 | 02 Jul 2026 | **Portal migration** — NV self-hosted Substrait before real data | 🔲 Open — Alpha 0.1 runs on the public portal with **dummy data only** | §17, §19 #4/#7 |
| C13 | 09 Jul 2026 | **AWB naming system** — specific scheme (pending Baskoro's confirmation to the team). **Do not change the current SwipeAWB/MPS naming until confirmed.** | 🔲 Open — pending team | §11.2, FR-OC3 |
| C14 | 09 Jul 2026 | **Hub-assignment re-upload key** — piece TRID vs AWB? | ✅ **Resolved 09 Jul** — keys on the **AWB naming system** (build after C13) | FR-OC6, §7.4 |
| C15 | 09 Jul 2026 | **Partial-reject → return-creation flow** — Baskoro considering: on partial reject, operator (Implant/DE, same team) uploads into NV to create the OC/return template; needs to see **how NV generates the AWB** first | 🔲 Open — keep current DE-creates-return-AWB flow until confirmed | §7.3, FR-R1/R2 |
| C16 | 09 Jul 2026 | **Google OAuth client + SMTP** — who registers the Google OAuth client (client ID/secret + allowed Workspace domains) and provides SMTP creds? Dev-login + log-only email cover Alpha until then | 🔲 Open — Baskoro / NV infra | FR-AUTH7, §15 |
| C17 | 03 Jul 2026 | **Signed+stamped attestation** — required on the DN (reverses v2.1 no-checkbox stance); LLM/OCR to replace the manual tick later | ✅ Decided | §9, FR-D2 |
| C18 | 10 Jul 2026 | **Shipper master + `.csv` link injection** — service→shipper id/name/branch source; is `links.csv` merged into the OC `.csv` or separate? | 🔲 Open (Round 5) | §19 #21 |
| C19 | 10 Jul 2026 | **Faktur vs single-DN model** — does "Faktur (whole document)" + separate return form supersede the DN box1/box2 model, or is it just courier naming? | ✅ **Resolved 14 Jul** — single DN, two sections (top forward / bottom return); no separate Faktur | §19 #22 |
| C20 | 10 Jul 2026 | **Reject-item OC engine** — distinct template engine mapping forward AWB → return OC | 🔲 Open (Round 5) | §19 #23 |
| C21 | 10 Jul 2026 | **Handover rejected-doc codes** — coded reasons + "next action" types for SwipeRx-rejected docs | 🔲 Open (Round 5) | §19 #24 |
| C22 | 10 Jul 2026 | **Canonical status vocabulary** — one shared status list/definitions for driver app + operator + report legend | 🔲 Open (Round 5) | §19 #25 |
| C23 | 10 Jul 2026 | **SwipeRx AWB ↔ Ninja AWB 1-to-many** — confirm it holds across all surfaces (report grouping assumes yes) | 🔲 Open (Round 5) | §19 #26 |
| C24 | 10 Jul 2026 | **Handover at 300–500 docs/day** — cap removed; confirm paging/perf, who at SwipeRx confirms receipt, SLA | 🔲 Open (Round 5) | §19 #27 |
| C25 | 10 Jul 2026 | **Camera fallback** — upload-a-photo fallback now allowed (reverses "no gallery" lock); confirms the webview dead-end fix | ✅ Decided (Round 5) — softens §3 microcopy | §7.1, FR-D3, §19 #18 |

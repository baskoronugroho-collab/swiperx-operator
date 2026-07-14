# SwipeRx Operator — Design Brief (Alpha 0.1)

> Companion to [PRD.md](PRD.md) **v2.2** and the `BUILD_HANDOFF.md` decision ledger (Rounds 1–4).
> Use this with a design/mockup tool (Claude "design" / artifact mode). **Everything here derives from
> PRD v2.2 — where the PRD/ledger conflicts with older prose, the ledger wins.** Where the PRD has an
> open dependency, this brief says **build data-driven / placeholder** rather than inventing final content.
>
> **This supersedes the v0.0.1 brief.** If you have an earlier artifact, it is stale on six points:
> reject is now flag+proof (no qty stepper); the DN signed+stamped attestation is **required**; the
> courier flow is a **phased wizard** (one doc per screen), not a scrolling checklist; the fail-reason
> list is the **9 coded reasons** below; photo capture is **forced live in-app camera**; and the link is
> **auto-injected into the upload file** (no manual copy-per-row).

---

## 1. What we're designing

**SwipeRx Operator** — a delivery-compliance & returns app for Ninja Van Indonesia's pharma partnership
with SwipeRx. Its job: make **complete photographic POD/RDO capture + a signed+stamped DN attestation a
hard gate** before a delivery can be confirmed, flag every reject with **photographic proof at the door**
(not per-PO quantities), and track parcels delivery → arrival-at-Implant → handover, with a read-only
client report.

**Three surfaces, one product:**

| Surface | Device | Users | Auth |
|---|---|---|---|
| **Courier app** | Mobile web (phone), portrait | Drivers | Tokenized link, no login |
| **Operator dashboard** | Desktop web | Superadmin, Program Manager, DE, Implant, Station IC, Validator | Google SSO, role-gated |
| **SwipeRx report** | Desktop web | SwipeRx Ops (client) | Google SSO, read-only |

The **courier app is the hero** — highest volume (~300 concurrent), used one-handed at a pharmacy door,
and where the core control (completeness gate + attestation) lives. Design it first and best.

> **Multi-role & team note:** one person can hold several roles (`User.roles[]`) — the landing page
> offers a starting point per hat. **Implant and DE are the same team** (interchangeable operators).

---

## 2. Brand & visual system (NV Design Master)

- **Primary:** Ninja Van red `#EE1B2C`. Primary actions, active nav, brand accents — not large fills.
- **Typography:** **Montserrat** (400/500/600/700). Generous sizes on the courier app.
- **Neutrals:** near-black text `#1A1A1A`, mid grey `#6B7280`, borders `#E5E7EB`, surfaces `#FFFFFF` / `#F7F7F8`.
- **Status palette** (working defaults; derive final tokens from NV Design Master):
  | State | Meaning | Suggested color |
  |---|---|---|
  | Neutral | Created / pending / not-opened | grey `#6B7280` |
  | In progress | Delivered / arrived / opened | blue `#2563EB` |
  | Success | Handed over / valid / return-AWB created | green `#16A34A` |
  | Warning | Return pending / awaiting action | amber `#D97706` |
  | Danger | Delivery failed / invalid | red `#DC2626` |
- **Tone:** clean, high-contrast, operational (not playful). Rounded-8px cards, clear hierarchy, whitespace.
- **Accessibility:** touch targets **≥48px**; WCAG AA contrast; **never color alone** (icon + label always).

---

## 3. Courier app (mobile) — design in detail

**Context:** phone, one hand, at a pharmacy door, possibly poor light/signal, driver in a hurry.
Bilingual **ID/EN toggle, Indonesian default.**

**Global patterns**
- **Phased wizard — NO scrolling.** One decision or one document per screen, with a **"Langkah N dari M /
  Step N of M"** indicator. Big sticky bottom primary button. Back arrow to the previous step.
- ID/EN toggle top-right; plain language everywhere.
- Each document capture = one full screen with a **camera-first live capture** (empty → captured
  thumbnail), a **"Lihat contoh / See example"** link, and client-side downscale (invisible to the user).
- **Live capture only — no gallery upload.** Show this friendly note on capture screens (locked microcopy):
  - **ID:** *"Semua foto diambil langsung dari kamera aplikasi dan waktunya tercatat otomatis untuk
    pengecekan. Foto tidak bisa diambil dari galeri — cukup ambil di lokasi seperti biasa 🙂"*
  - **EN:** *"All photos are taken live in the app and the time is logged automatically for review.
    You can't upload from your gallery — just snap it at the location 🙂"*

**Flow order** (locked, `BUILD_HANDOFF` §3.5): **order context → outcome → capture (one doc/screen) →
reject/fail proof (if any) → confirm preview → success + Restart.**

**Screens**
1. **Order context** — resolves from the link: pharmacy name, AWB, PO lines (PO number + **koli**; **no SP
   type — it isn't in the data**), service, hub, address, total Koli. One primary CTA: **Mulai / Start**.
2. **Outcome switch (up front):** **Normal delivery / Partial reject (Retur Sebagian) / Full reject
   (Retur Semua) / Failed delivery (Gagal Kirim).** This branches the wizard before capture.
3. **Capture — Normal delivery** (one doc per screen, "step N of M"):
   - **Pharmacy POD** (storefront) → **Receiver POD** (person) → **Delivery Note (box 1)** → **SP Manual**
     (see below).
   - **On the Delivery Note screen:** a **required "Saya konfirmasi DN sudah ditandatangani & distempel
     penerima / I confirm the DN is signed + stamped by the receiver" attestation tick.** This is part of
     the gate (§9). *(A fast-follow LLM/OCR check will later replace this manual tick — design it as a
     clean required checkbox, not a permanent fixture.)*
   - **SP Manual is rider-driven, not pre-counted.** SP type is not in the data — the rider reads the
     Faktur at the door. Design: after the DN, present the PO lines and let the rider **flag which POs are
     "SP Manual"**; each flagged PO opens **one SP Manual capture slot**. Data-driven from the PO lines,
     rider-flagged (do **not** show a fixed "SP Manual × N" pre-count).
4. **Partial reject (Retur Sebagian)** — **flag + proof only, no per-PO quantity entry.** Adds, after the
   normal set: **DN box 2** signed+stamped (attestation for the rejected items), **one overall
   rejected-goods photo** (not per item), and the **forward AWB sticker** photo. *(No qty stepper — the
   `RejectLine` per-PO capture was dropped.)*
5. **Full reject (Retur Semua)** — chosen up front: **DN box 2** signed+stamped + **one overall
   rejected-goods photo**. No per-line selection.
6. **Failed delivery (Gagal Kirim)** — nothing handed over, no POD set. Distinct **danger/amber** styling.
   - **Coded fail reason (single-select, 9 codes, bilingual):**
     | code | ID (courier UI) | EN |
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
   - **+ one live-camera proof photo whose app-stamped time is shown to the driver.** Optional free-text note.
7. **"No return to collect" is a SUCCESS, not a failure.** When the consignee has no goods to return, the
   courier chooses **complete/success** (not a fail reason) **but must still capture the return form signed
   by the consignee even though it is left blank** — a mandatory blank-but-signed return-form photo slot in
   this branch. *(Distinct from `refused_sign`, which is an outright failure.)*
8. **Confirm preview → Success** — review captured items, **double-check**, then **Kirim & Selesai /
   Submit & Finish**. Then a success screen with a **Restart** button (for misclicks; guarded — locks once
   a Validator flags or DE acts on the return). **No return-AWB step for the driver.**
9. **Resume / resubmit** — a returning link within **30 days** resumes in place; terminal states render
   **read-only** (not a fresh capture); a bad/expired token shows a friendly "link not valid" screen.

**Completeness gate (the product):** the final **"Confirm / Kirim & Selesai"** is **disabled with a
visible reason** ("Ambil foto Delivery Note dulu / Capture the Delivery Note to continue", or "Centang
konfirmasi tanda tangan & stempel / Tick the sign+stamp confirmation") until **every required photo for
the chosen outcome is captured AND the DN signed+stamped attestation is ticked.** Make the
disabled→enabled transition satisfying and obvious.

> **Pending the new DN mockup (§19 #5):** build the capture set **data-driven** — slots render from the
> AWB's PO lines, and SP-Manual slots appear as the rider flags POs. Use placeholder "See example" images
> until the real DN/SP examples arrive.

---

## 4. Operator dashboard (desktop) — shell + per-role home

Left-nav app shell; **each role sees only its menus** (Superadmin sees all). Top bar: product mark,
role/name, SSO account, ID/EN. **Role landing/launcher** on first open: action-phrased starting points per
hat ("Saya ingin buat OC / I want to create an OC", "I want to report an arrival", …), multi-hat aware.

**Role homes to mock:**

- **Implant / DE — Order intake & link creation (the 3-step OC flow).** *This replaces the old
  "manual copy-link-per-row" screen — the courier link is now **auto-injected into the delivery-instruction
  column of the generated file**, so Implant uploads **one file** to NV, not one link at a time.*
  - **Step 1 — Upload & pick service.** Drag-and-drop (or browse) the **SwipeRx TMP** source file **and
    pick the service up front: S1 Regular / S2 Instant (Sameday) / S3 Return pickup** (show name + type).
  - **Step 2 — Preview (no writes).** Show valid **AWB / piece counts** and a per-row **error list**
    (row number + reason) for invalid rows. **Wrong-service guard:** if (nearly) all rows fail, show a
    prominent hint — *"Most rows failed — did you pick the right service for this file?"* — instead of only
    raw per-row errors.
  - **Step 3 — Create & download.** Commit valid rows → download **`upload.xlsx`** (link already embedded
    in col R) **+ `links.csv`**. **Empty-commit guard:** if nothing was committed (e.g. all AWBs are
    duplicates of a prior upload), **refuse to produce a file** and say "nothing new to create" — never
    hand back an empty `upload.xlsx`.
  - **Monitoring table (secondary, not a paste workflow):** a table of generated per-AWB links for
    at-a-glance status — AWB ID, pharmacy, service chip (Regular / Instant / Return pickup), Koli, **link
    status** (Not opened / Opened / Delivered / Failed), created at. A **"Copy link"** affordance is a
    convenience only (the link is already in the downloaded file). Filter by service / date / status; row
    click → shared AWB detail drawer.
  - *(Hub-assignment re-upload stage is **out of scope for this design pass** — blocked on the AWB naming
    scheme, §19 #15.)*
- **DE — Return queue:** rejects awaiting a return-AWB PDF. **Mark "AWB created" + upload the AWB PDF
  sticker** against the original AWB. (The return AWB itself is created in NV's system.)
- **Station IC — Return-to-print worklist:** return AWBs to print, filterable by **hub / date / service**.
  Each row: AWB, pharmacy, hub, service, return-AWB number. Action: **Download label (PDF) → print.**
  **No "acknowledge labelled" / reprint tracking — that was dropped.** Station IC just filters by hub and
  prints (or acts from the notification email).
- **Implant — Arrival scan & handover:** an **always-focused scan-input** screen (USB barcode scanner acts
  as a keyboard) → scan/enter AWB → **Arrived at Implant (awaiting handover)**. Build a **handover session**
  (group parcels) → one action marks the whole session handed over; **free-text note** if SwipeRx rejects
  the handover. Surface **discrepancy lists**: delivered-but-never-scanned (lost docs) and
  scanned-but-never-delivered (courier skipped the app).
- **Validator — RDO review (non-blocking):** view captured docs; flag **Valid / Invalid + coded reasons
  (multi-select):** (a) DN missing / not signed+stamped; (b) **Return form missing / not signed+stamped**;
  (c) SP Manual missing vs DN; (d) invoice number mismatch. Download validity data. *(Note: reason (b) now
  applies whenever a return form is expected — **including the "no-return = success + blank-signed form"
  case** — not only when a reject was submitted.)*
- **Program Manager — Overview:** **rate KPIs** (% completed, % RDO validated, % return recorded; adds:
  % failed, % invalid RDO, avg time-to-handover, backlog aging) with **clickable numbers → detail tables**,
  date-range + service filters, deep-dive export.
- **Superadmin — User management:** register by Google email, **assign one or more roles (checkboxes)**,
  deactivate.

**Shared components:** **AWB detail drawer** (status timeline CREATED → DELIVERED → ARRIVED_AT_IMPLANT →
HANDED_OVER, with reject/return and **DELIVERY_FAILED** branches; captured-photo gallery via signed URLs;
return-AWB status; validation flag), filter bar (date + status + service always), data table with export.

---

## 5. SwipeRx report (desktop, read-only)

- No operational controls. Flexible filters: service, status, return type, pharmacy, hub, **date (always)**,
  validity, PO.
- **Grouped by station + L2 (city/kabupaten).** Rows expand to reject/return detail + photo thumbnails
  (signed, time-limited URLs).
- **Download CSV** of the filtered set — **one row per AWB** (return_type + signed photo URLs), not per
  reject line.
- **No Implant-backlog tab in Alpha 0.1 — it is deferred** (no automated arrival/handover source at launch).
  Design the report without it; the arrival/handover data still accrues for the deferred tab later.

---

## 6. Design principles (apply everywhere)

1. **The gate is the product.** Completeness + the signed+stamped attestation must be unmistakable —
   always show what's missing and why the button is blocked.
2. **Phased, no-scroll courier flow.** One decision/document per screen; the driver is never hunting.
3. **Role-aware & self-explaining.** First-sign-in walkthrough per role + an always-available "How this
   works" panel (courier app bilingual).
4. **Plain language, minimal chrome.** Operational users under time pressure; reduce cognitive load.
5. **Data-driven where content is pending** (DN layout, SP-Manual flags, hub-assignment): design the
   container, not fixed content.
6. **Mobile courier app is first-class**, not a shrunken desktop.

---

## 7. Deliverables to request from the design tool

- **Priority 1:** Courier app full **phased-wizard** flow (screens 1–9, §3), mobile frames, ID + one EN
  example, empty / captured / **disabled-gate** / error states, plus the danger-styled failed-delivery and
  the "no-return = success + blank-signed form" branches.
- **Priority 2:** Operator dashboard shell + role homes (the **3-step OC intake**, Station IC print
  worklist, PM overview, arrival-scan/handover) + the AWB detail drawer.
- **Priority 3:** SwipeRx report page (grouped station + L2, no backlog tab).
- A **component sheet** (buttons incl. disabled-with-reason, status chips, live-capture slot card,
  required attestation tick, filter bar). **No quantity stepper** — reject is flag + proof only.

---

## 8. Out of scope for this design pass

Final DN capture layout (awaiting the mockup, §19 #5), ML/sign-stamp detection UI (fast-follow §16), the
hub-assignment re-upload UI (blocked on the AWB naming scheme, §19 #15), the internal-NV send flow detail
(§7.5), and anything dependent on the NV self-hosted deployment stack (§17).

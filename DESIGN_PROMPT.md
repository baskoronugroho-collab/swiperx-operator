# Claude Design — ready-to-paste prompts (Alpha 0.1, aligned to PRD v2.2)

Two ways to use these: paste the **full self-contained prompt** (works on its own), or attach
`DESIGN_BRIEF.md` + `PRD.md` and use the **short prompt**. All prompts assume PRD **v2.2** — reject is
flag+proof (no qty stepper), the DN signed+stamped attestation is **required**, the courier flow is a
**phased wizard**, the fail list is the **9 coded reasons**, capture is **forced live in-app camera**, and
OC intake is the **3-step flow** (link auto-injected into the file).

---

## A. Short prompt — Courier app (attach DESIGN_BRIEF.md)

> Using the attached SwipeRx Operator design brief (Alpha 0.1), design **high-fidelity, interactive
> mockups of the Courier app** (mobile, portrait) as a **phased wizard, one document/decision per screen,
> no scrolling** ("Step N of M"). Cover §3 screens 1–9: order context → outcome switch (Normal / Partial
> reject / Full reject / Failed delivery) → capture (Pharmacy POD, Receiver POD, Delivery Note with a
> **required signed+stamped attestation tick**, SP Manual rider-flagged per PO) → reject/fail proof →
> confirm preview → success + Restart. Include the **disabled-completeness-gate** state (with a visible
> reason), the danger-styled **failed-delivery** branch (9 coded reasons), and the **"no return to collect
> = success + mandatory blank-but-signed return form"** branch. Indonesian default with an EN toggle;
> **live in-app camera only (no gallery)** with the friendly "photos are taken live and the time is logged"
> note; ≥48px touch targets. Follow the NV brand tokens in §2 (red `#EE1B2C`, Montserrat, status palette).
> Output a single clickable React artifact, plus a short component sheet (buttons incl. disabled-with-
> reason, status chips, live-capture slot, required attestation tick, filter bar). **No quantity stepper —
> reject is flag + proof only.** Render the capture set data-driven from placeholder PO-line data.

---

## B. Full self-contained prompt — Courier app (paste as-is, no attachments)

> You are designing **SwipeRx Operator**, a delivery-compliance app for Ninja Van Indonesia's
> pharmaceutical-delivery partnership with SwipeRx. Produce **high-fidelity, clickable mockups as a single
> interactive React artifact.**
>
> **Focus: the Courier mobile app** (phone, portrait, used one-handed at a pharmacy door). It is the hero
> surface. Build it as a **phased wizard — one document or one decision per screen, no scrolling**, with a
> "Langkah N dari M / Step N of M" indicator and a sticky bottom primary button.
>
> **Core concept — the completeness gate + attestation:** a courier opens a tokenized link (no login) and
> must capture a required set of document photos **and tick a required "DN is signed + stamped by the
> receiver" attestation** before the "Confirm delivery" button enables. The button stays **disabled with a
> visible reason** ("Capture the Delivery Note to continue" / "Tick the sign+stamp confirmation") until the
> chosen outcome's required photos are all present and the attestation is ticked.
>
> **Capture is forced live in-app camera — no gallery upload.** Each capture screen shows a camera-first
> slot, a "See example" link, and this friendly bilingual note: ID — *"Semua foto diambil langsung dari
> kamera aplikasi dan waktunya tercatat otomatis untuk pengecekan. Foto tidak bisa diambil dari galeri —
> cukup ambil di lokasi seperti biasa 🙂"*; EN — *"All photos are taken live in the app and the time is
> logged automatically for review. You can't upload from your gallery — just snap it at the location 🙂"*.
>
> **Flow order:** order context → outcome → capture → reject/fail proof → confirm preview → success.
>
> **Screens (portrait mobile frames):**
> 1. **Order context** — pharmacy name, AWB, PO lines (PO number + koli; **no SP type — not in the data**),
>    service, hub, address, total Koli; primary CTA "Mulai / Start".
> 2. **Outcome switch (up front):** Normal delivery / Partial reject (Retur Sebagian) / Full reject
>    (Retur Semua) / Failed delivery (Gagal Kirim).
> 3. **Capture — Normal** (one doc per screen): Pharmacy POD (storefront) → Receiver POD (person) →
>    **Delivery Note (box 1)** with a **required signed+stamped attestation tick** → **SP Manual**: since
>    SP type isn't in the data, let the rider **flag which POs are "SP Manual"** and open one SP capture
>    slot per flagged PO (rider-driven, not a pre-count).
> 4. **Partial reject** — flag + proof only (NO quantity stepper): adds DN **box 2** signed+stamped, **one**
>    overall rejected-goods photo, and a forward AWB-sticker photo.
> 5. **Full reject** — DN box 2 signed+stamped + one overall rejected-goods photo; no per-line selection.
> 6. **Failed delivery** — a coded fail reason (single-select, 9 codes: Recipient cancels the order /
>    Recipient did not order the package / Address incomplete or wrong / Recipient has moved / Recipient not
>    at the location / Recipient asks for a reschedule / Office closed / Natural disaster, riot or accident /
>    Recipient refuses to sign the documents) **plus one live-camera proof photo whose app-stamped time is
>    shown to the driver**; distinct danger/amber styling; no POD set; optional note.
> 7. **No return to collect (a SUCCESS, not a failure):** courier chooses complete/success but must still
>    capture the **return form signed by the consignee even though it is left blank** — a mandatory
>    blank-but-signed return-form photo.
> 8. **Confirm preview → Success** — review captured items, double-check, "Kirim & Selesai / Submit &
>    Finish", then a success screen with a **Restart** button. **No return-AWB step for the driver.**
> 9. **Resume / terminal** — a returning link within 30 days resumes in place; a terminal state renders
>    read-only; an invalid/expired token shows a friendly "link not valid" screen.
>
> **Brand & style:** Ninja Van red `#EE1B2C` for primary/active (not large fills); **Montserrat**; neutrals
> near-black `#1A1A1A`, grey `#6B7280`, borders `#E5E7EB`, surfaces white / `#F7F7F8`. Status colors:
> neutral grey, in-progress blue `#2563EB`, success green `#16A34A`, warning amber `#D97706`, danger red
> `#DC2626` — always paired with an icon + label, never color alone. Rounded 8px cards, high contrast,
> generous whitespace, clean/operational (not playful).
>
> **Requirements:** Indonesian default with an ID/EN toggle (show at least one screen in EN); every touch
> target ≥48px; render the capture set **data-driven** from placeholder PO-line data (e.g. 3 POs, the rider
> flags 2 as SP Manual → 2 SP slots); include empty / captured / disabled-gate / error states. Make it
> clickable end-to-end: order context → outcome → capture → reject/failed → success.
>
> **Also output:** a compact component sheet — primary/secondary/**disabled-with-reason** buttons, status
> chips, live-capture slot card, required attestation tick, and a filter bar. **No quantity stepper.**

---

## C. Order intake & link creation — 3-step OC flow (attach DESIGN_BRIEF.md)

> Using the attached SwipeRx Operator design brief (Alpha 0.1), design a **high-fidelity, interactive
> mockup of the Order Intake & Link Creation screen** for the Operator dashboard (desktop), used by Implant
> and DE (same team). Follow the NV brand in §2. Output a single clickable React artifact.
>
> This is a **3-step OC flow on one page.** Note: the courier link is **auto-injected into the
> delivery-instruction column of the generated file**, so the operator uploads **one file** to NV — this is
> NOT a manual copy-link-per-row workflow.
>
> **Step 1 — Upload & pick service.** A drag-and-drop zone (+ "Browse file") for the SwipeRx **TMP** source
> file, **and a service picker up front: S1 Regular / S2 Instant (Sameday) / S3 Return pickup** (show name +
> type). CTA: **"Preview"**.
>
> **Step 2 — Preview (no writes).** A result panel showing valid **AWB / piece counts** and, if any rows
> failed, a collapsible **error table** (row number, AWB, reason). **Wrong-service guard:** if (nearly) all
> rows fail, show a prominent hint banner — *"Most rows failed — did you pick the right service for this
> file?"* — above the raw errors. CTA: **"Create orders"**.
>
> **Step 3 — Create & download.** On commit, a success panel: "N orders created" + download buttons
> **"Download upload.xlsx"** (link already embedded) and **"Download links.csv"**. **Empty-commit guard:**
> if nothing was committed (e.g. all AWBs duplicate a prior upload), show a warning state — *"Nothing new to
> create"* — and **do not** offer an empty file.
>
> **Monitoring table (below, secondary):** generated per-AWB links for at-a-glance status — columns AWB ID,
> pharmacy, service chip (Regular / Instant / Return pickup), Koli, **link status** badge (Not opened /
> Opened / Delivered / Failed), created at. A "Copy link" button is a convenience only. Filter bar: service,
> date, link status. Row click → shared AWB detail drawer (slide-in: status timeline + captured-photo
> placeholder). Make it interactive: Preview → Create transitions, filters update rows, copy shows "Copied!".

---

## D. Operator dashboard — shell + role homes (attach DESIGN_BRIEF.md)

> Using the attached SwipeRx Operator design brief (Alpha 0.1), design **high-fidelity, interactive mockups
> of the Operator dashboard** (desktop): a left-nav shell (each role sees only its menus), a top bar with a
> multi-hat **role landing/launcher** (action-phrased starting points), and these role homes. Follow the NV
> brand tokens in §2. Output a single clickable React artifact.
>
> **1. Order intake — 3-step OC flow (Implant/DE):** upload TMP + pick service → preview (counts + per-row
> errors + wrong-service hint) → create → download upload.xlsx + links.csv (link auto-injected; empty-commit
> guard). Secondary monitoring table with link-status badges. *(Full detail in prompt C.)*
>
> **2. Station IC — Return-to-print worklist:** return AWBs to print, filterable by hub / date / service.
> Each row: AWB, pharmacy, hub, service, return-AWB number. Action: **"Download label (PDF)" → print.**
> **No "acknowledge labelled" / reprint tracking** (dropped) — filter by hub and print only.
>
> **3. Implant — Arrival scan & handover:** an **always-focused scan-input** field (USB barcode scanner as
> keyboard) → scan AWB → "Arrived at Implant (awaiting handover)"; build a **handover session** grouping
> parcels → one action marks the whole session handed over, with a **free-text note** if SwipeRx rejects the
> handover. Show **discrepancy lists** (delivered-never-scanned / scanned-never-delivered).
>
> **4. Program Manager — Overview:** **rate KPI cards** (% completed, % RDO validated, % return recorded,
> % failed, % invalid RDO, avg time-to-handover, backlog aging) where each number is **clickable → detail
> table**; date-range picker + service filter.
>
> **5. Superadmin — User management:** register by Google email, **assign one or more roles (checkboxes)**,
> deactivate. Multi-role.
>
> **6. Shared — AWB detail drawer:** slides in from the right on any row click. Status timeline
> (CREATED → DELIVERED → ARRIVED_AT_IMPLANT → HANDED_OVER, with reject/return and **DELIVERY_FAILED**
> branches), captured document-photo thumbnails (signed URLs), return-AWB status, and the validation flag.
> Usable from any screen.

---

## E. SwipeRx report (attach DESIGN_BRIEF.md)

> Using the attached SwipeRx Operator design brief (Alpha 0.1), design **high-fidelity, interactive mockups
> of the SwipeRx report page** (desktop, read-only). Follow the NV brand tokens in §2. Output a single
> clickable React artifact.
>
> Cover: a filter bar (service, status, return type, pharmacy, hub, date — always visible — validity, PO);
> a data table **grouped by station + L2 (city/kabupaten)** where rows expand to show reject/return detail +
> document-photo thumbnails (signed, time-limited URLs); and a **"Download CSV"** button for the filtered
> set (**one row per AWB**, with signed photo URLs). **No operational controls, and no Implant-backlog tab —
> the backlog view is deferred in Alpha 0.1.**

# SwipeRx Operator — Written Feedback on the Deployed Tools

| Field | Value |
|---|---|
| Author | Baskoro Adi Nugroho (Product) |
| Date | 03 Jul 2026 |
| Subject | Feedback on the deployed prototype (courier + operator + report) and the Substrait deploy |
| System name | **Alpha 0.1** (was "v0.0.1") |
| Related | PRD.md v2.1 — to be updated after these decisions |

## 1. Overall assessment

What is live on Substrait today is a **clickable design prototype** (three front-end surfaces) plus the **stock scaffold backend**. It successfully proves the **deploy pipeline** (build both images → Flyway migrate → serve `/health` + `/api` on OceanBase). It is **not** a working product yet:

- The prototypes do **not** call the backend, do **not** persist, and do **not** authenticate — they render fixed demo data.
- `backend/main.py` is still the sample `hello`/`items` endpoints; `V1__init.sql` is still the sample `items` table.
- Therefore the **generated driver link cannot open**: the operator surface prints a fabricated `op.ninjavan.co/c/…` string, and the courier surface is a standalone demo that ignores any token. There is no backend route yet turning a token into a real capture session. *(This is the reported "can't open the link" issue — expected for a prototype, and the #1 thing the production build must wire.)*

**Bottom line:** the visual design and the deployment pipeline are validated; the production application (real schema, auth, storage, intake, capture) is still to be built, and the changes below reshape what that build should be.

## 2. What the prototypes got right (keep)

- NV brand system (red `#EE1B2C`, Montserrat, status palette) and clean status chips.
- Bilingual ID/EN toggle on the courier and operator surfaces.
- Courier phase skeleton (order → outcome → capture → summary → success) and the completeness-gate pattern.
- Operator role-switcher, per-role menus, deliveries drawer with a status timeline + photo gallery.
- Report read-only framing with filters + CSV download.

## 3. SSO on Substrait — confirmed feasible

Substrait provides DB + Redis + `JWT_SECRET` but **no identity provider**. Since we own the FastAPI backend, we wire **Google Workspace OIDC** ourselves (`/api/auth/*` auth-code flow → session JWT → `google_email` → role). An unregistered account gets the **"contact the Ninja Van team"** screen. Couriers stay tokenized (no login). Only prerequisite: registering a Google OAuth client for the production domain + choosing the approved Workspace domain(s). **No platform limitation.**

## 4. Decisions locked this round (03 Jul 2026)

1. **Reject = flag + proof, not structured lines.** The courier only indicates whether there is a reject (partial / full) and supplies proof; it does **not** list which PO or how many. Drop per-PO/qty reject capture (and the `RejectLine` entity) from the courier flow. Problem #1 ("invisible rejects") is reframed: every return is flagged at the door with photographic proof, not captured as per-PO quantities.
2. **Signed + stamped is a required attestation.** Re-introduce a mandatory "DN signed & stamped" checklist/attestation on the DN capture (reverses PRD §9's no-attestation stance). A future LLM/OCR check is intended to replace the manual tick.
3. **Implant backlog: kept but deferred.** No automated arrival/handover data source exists yet (handover list is manual today). Keep FR-X2 / problem #3 in the PRD as a fast-follow; remove the Backlog **tab** from the built report for now.
4. **Reprint / print tracking is out of scope.** Drop FR-R4 (acknowledge / labelled / printed timestamps). Station IC filters by hub and prints (or receives the email); the app does not track whether it was printed. Solve tracking later.

## 5. Change requests by surface

### 5.1 Auth & first-run
- **Google SSO required**; unregistered → "contact the Ninja Van team."
- **First open = role landing / launcher**: tell the user who they are, their role, and where to start, with each option explained (e.g. Implant: *"I want to create an OC"*, *"I want to report a handover list"*). Sharper than a passive help panel.
- **Multi-user per role** supported (superadmin retains full access).
- Name the system **Alpha 0.1**; add an in-app **version-notes / changelog** panel.

### 5.2 Order creation (OC) — 3 explicit steps
1. Implant uploads the SwipeRx template and **selects the shipper / service ID** (UI shows its **name + service type** so they can tell which one it is).
2. The webapp processes and produces the output per template, **auto-injecting the unique driver link into the delivery-instruction column**.
3. Implant **downloads** the output and **uploads it into NV's internal system**.

### 5.3 Courier app
- Rebuild as a **phased wizard — no scrolling**; each phase is a step.
- **Terminology:** PO quantity is in **koli (collies), max ~10 per PO — never "units."**
- **Forward POD:** capture the document photo, with a **required signed + stamped attestation** to remind/force the driver.
- **Partial reject:** capture **item photo + forward AWB sticker photo + Return Form** (on forward, the Return Form is the DN's box 2 — same document). The courier does **not** list rejected items/quantities.
- **Submit:** show a **confirmation of exactly what is being submitted**; the courier double-checks; the final confirmation screen is **re-previewable** before submitting. After submit, provide a **Restart** button in case of a misclick.

### 5.4 DE — returns handling
- A **rejected-items list** DE can view and **download**.
- After download, DE **creates the actual AWB in NV's system** by re-uploading, then **marks whether it was created** and **uploads the PDF sticker**.

### 5.5 Station IC
- Either (a) open the webapp, **filter by hub, print** the created AWB, or (b) receive an **email notification** for their AWB.
- **No print/ack tracking** in the app (per decision #4).
- **OPEN QUESTION:** how does the app know which hub an AWB is assigned to?

### 5.6 Validator — dedicated page
- A page **just to validate**, entering an **invalid reason** from a coded list, **multi-select**:
  - DN note missing / not signed & stamped
  - Return Form missing / not signed & stamped — **only when a return was submitted**
  - No additional SP Manual as stated in the DN, **or** the invoice number didn't match

### 5.7 One delivery-data list
Columns: **order-creation datetime, driver-submitted, complete/fail delivery, has return (full/partial), RDO validation status (– / valid / invalid), handover-by-Implant.** Each row opens the detail + photos.

### 5.8 Program Manager metrics
Show **rates**, not just counts: **% completed orders (of how many), % RDO validated, % return recorded.** Suggested additions: **% failed delivery, % invalid RDO, average time-to-handover, backlog aging.**

### 5.9 SwipeRx report
- **Remove the Implant-backlog tab** (deferred, no source yet).
- Keep the report similar but **grouped by station and L2 (city / kabupaten name)**.
- Drop per-PO reject columns (reject is now flag + proof).

## 6. Scope note
Narrow the scope to **the original SwipeRx request across all three movements** (regular, instant, return-pickup). Reprint tracking and automated backlog are out for now.

## 7. Still open
- Which hub an AWB is assigned to (Station IC routing).
- Object-storage bucket + credentials (still the key infra gap).
- Google OAuth client registration for the production domain + approved Workspace domain(s).
- NV self-hosted Substrait portal (public portal cannot hold real pharmacy data).
- OC template exact fields; hub → email distribution list; Service-3 capture set.

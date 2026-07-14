# SwipeRx Operator — Unhappy-flow register

> Audit dated **09 Jul 2026**, run against the live deploy (`swiperx-operator.apps.substrait.build`)
> and the decision ledger (`BUILD_HANDOFF.md` §3). Goal: every failure path — real-world ops and
> in-app — is either **solved**, **designed & scheduled**, or **explicitly open with an owner**.
> Update this file when a row changes; it feeds PRD v2.2.

**Legend:** ✅ solved & live-verified · 🔒 decided/locked, builds in the stated milestone ·
🟡 decided but has a gap/ripple to fix · 🔴 open — needs a decision (owner in brackets)

---

## A. Driver app / at the door (courier)

| # | Unhappy flow | Status | Detail |
|---|---|---|---|
| A1 | Courier can't complete the delivery | 🔒 M2 | 9 coded fail reasons LOCKED 09 Jul (incl. `refused_sign`); live in-app photo + app-stamped time LOCKED; completeness gate (reason + proof) before confirming a fail |
| A2 | Re-attempt after a failed delivery | 🔒 M2 | LOCKED: same link re-opens (no new AWB), prior attempts kept, 30-day window |
| A3 | Partial / full reject at the door | 🟡 M2 | Design LOCKED (flag + proofs, DN box-2 attestation, no per-PO qty). Open confirmations (§19 #8): does one DN photo cover both boxes; is the forward-AWB-sticker photo required |
| A4 | Receiver refuses to sign | 🔒 M2 | `refused_sign` fail code (outright failure) |
| A5 | Nothing to return at a return-collection stop | 🟡 M2 | LOCKED 09 Jul: success path + mandatory **blank-but-signed** return form photo. **Ripple not yet applied:** Validator coded reason (b) says return form is checked "only when a return was submitted" — now stale, the form exists on no-return successes too. Fix the coded list in PRD v2.2 |
| A6 | **Driver never opens the link** | 🔴 [Baskoro + ops] | Top real-life risk (§19 #1) — defeats the whole capture premise. In-app mitigations exist: reworded col-R "MUST open the link" text (live), M3 scanned-never-delivered alarm catches it after the fact. Real enforcement (NV-app embedding / blocking completion in NV system) is an ops decision |
| A7 | Camera blocked (webview without getUserMedia, permission denied) | 🔴 [Baskoro + ops, input #8] | Locked policy forces live capture — if the NV-app webview can't open the camera the courier is dead-ended. Need the answer to "webview or browser?" plus a defined fallback (file upload w/ EXIF? "open in Chrome" hint?) |
| A8 | Connectivity loss / photo upload fails mid-wizard | 🟡 M2 design | Offline sync is out of scope (locked). M2 must still define: per-photo retry, what survives a dropped session, resume via the same link (resume-within-30d is in scope) |
| A9 | Misclick submit | 🟡 M2/M3 | Restart button + guard LOCKED (guard: allowed until Validator flags or DE acts, then "contact Implant"). **Gap:** no defined unlock/correct action for the Implant side once the guard engages — propose a superadmin/Implant unlock in M3 |
| A10 | Link guessing / opening after terminal state | 🟡 M1→M2 | Unguessable `token_urlsafe(24)`; bad token → **404 (live-verified)**. Gaps for M2: `/api/c/<token>` has **no 30-day expiry check** yet, and terminal states must render read-only instead of capture |
| A11 | S3 return-pickup fails (pharmacy closed, goods not ready, refuses handover) | 🔴 [Baskoro, §19 #6] | S3 capture set still open AND the 9 fail codes are delivery-worded — confirm which apply to pickups or add pickup-specific codes |

## B. Operator webapp (intake) — negative paths live-tested 09 Jul

| # | Unhappy flow | Status | Detail |
|---|---|---|---|
| B1 | No session on staff endpoints | ✅ | 401 (live-verified) |
| B2 | Wrong role | ✅ | `require_roles("implant","de")` gates all `/api/oc/*` |
| B3 | Unknown service code | ✅ | 400 `unknown_service` (live-verified) |
| B4 | Corrupt / non-xlsx file | ✅ | 422 "could not read .xlsx: File is not a zip file" (live-verified) |
| B5 | Wrong service picked for the file | 🟡 | Fails **safe** — 0 AWBs, all rows error (live-verified: Regular TMP as S2 → 181 errors, nothing commits). UX gap: errors read "koli must be > 0", no hint the *service* is wrong — frontend should detect all-rows-failed and suggest re-checking the service |
| B6 | Same TMP uploaded twice | 🟡 | Existing AWBs are skipped with per-AWB errors (good). **Gap:** an all-duplicate `create` still returns 201 and generates an **empty upload.xlsx** an Implant could push into NV — refuse the commit when nothing was committed |
| B7 | Empty file upload | ✅ | 400 `empty_file` |
| B8 | Bad courier token | ✅ | 404 `invalid_link` (live-verified) |
| B9 | Stored file missing at download | ✅ | 404 `file_missing` |
| B10 | Dev-login exposed on the public portal | 🟡 | Anyone knowing a seeded email can mint a session. Acceptable while dummy-data-only; **disable `DEV_LOGIN_ENABLED` once React login + real OAuth land**, and rotate the `sbd_` deploy token (HANDOVER §7) |
| B11 | SwipeRx resends corrected data after create (wrong address, wrong koli) | 🔴 [Baskoro + ops] | No amend/void flow decided anywhere. Today the correction presumably happens NV-side. Decide: void+recreate in-app, edit, or explicitly out of scope (manual) |

## C. Back office / real-world ops (M3 designs)

| # | Unhappy flow | Status | Detail |
|---|---|---|---|
| C1 | Docs delivered but never arrive at Implant (lost docs) | 🔒 M3 | Delivered-never-scanned discrepancy alarm |
| C2 | Docs arrive but courier skipped the app | 🔒 M3 | Scanned-never-delivered discrepancy alarm (also the after-the-fact catch for A6) |
| C3 | SwipeRx rejects the handover | 🔒 M3 | Free-text rejection note on the handover session (locked) |
| C4 | Invalid RDO found by Validator | 🔒 M3 | Coded multi-select reasons, recorded-only overlay (locked; apply the A5 ripple to reason (b)) |
| C5 | Return AWB never created (DE backlog) | 🟡 M3 | DE queue + mark-created + PDF upload designed. Flow mechanism may still change — C15 open (Baskoro watching how NV generates the AWB); keep current flow until he confirms |
| C6 | Station IC never notified / never acts | 🔴 [Baskoro] | Hub→email list (C5), notify-only recipients (C6), SMTP creds (C16) all open — log-only email until then. Print/ack tracking was deliberately dropped (accepted residual risk) |
| C7 | AWB has no hub assigned (re-upload forgotten) | 🔴 blocked on C13 | Hub-assignment stage itself is blocked on the AWB naming scheme; when built, add "missing hub" visibility to the delivery list |
| C8 | Email send fails | 🟡 M3 | Log-only fallback until SMTP; surface failed sends via the notification table when wired |

---

## Decision batch for Baskoro (everything 🔴 above, deduplicated)

1. **Driver-link enforcement** (A6, §19 #1) — ops mechanism to guarantee the link opens.
2. **Webview or browser + camera fallback** (A7, input #8).
3. **S3 capture set + S3 fail reasons** (A11, §19 #6).
4. **Reject confirmations** (A3, §19 #8) — one DN photo for both boxes? AWB-sticker photo?
5. **AWB naming scheme** (C13) — unlocks hub-assignment stage (C7) and return-AWB format.
6. **Partial-reject → return-creation mechanism** (C15) — after he sees NV's AWB generation.
7. **Hub→email list + notify-only recipients + SMTP** (C6 register row; C5/C6/C16).
8. **Correction/amend flow** (B11) — or declare it manual/out-of-scope explicitly.
9. **Restart-guard unlock ownership** (A9) — propose: Implant/superadmin unlock in M3.
10. **Google OAuth client** (C16) — needed to kill dev-login (B10).

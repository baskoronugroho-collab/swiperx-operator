# SwipeRx Operator — demo build

Static, no-build, no-install. The whole app is this folder.

## Run it
**Double-click `index.html`** (opens in your default browser). No server, no Node, no internet.
Portability = zip this folder, move it, unzip, open `index.html`.

> Live data lives in the browser's `localStorage` (not in the files). The zip carries the
> **app + seed**, which reproduces the full showable demo state on any machine. Click
> **Reset demo** (bottom-right) any time to restore the clean seed and re-run the walkthrough.

## Three surfaces (top nav)
- **Operator** — Order creation (CSV + manual), RDO Validation, Document Upload, Orders list.
- **Aplikasi Driver** — the headline phone flow (opens the walkthrough AWB `#/d/X7DEMO`).
- **Laporan SwipeRx** — read-only report, filters + Download CSV.

ID/EN toggle on all three (ID default). Photo capture is **simulated** (a placeholder drops in
instantly — narrate "on a real phone this is the live camera").

## Scripted live walkthrough
1. **Operator › Pembuatan Order** → "Gunakan CSV contoh": valid rows commit, bad rows hit the error
   log, links table + Download links appear.
2. **Aplikasi Driver** (AWB02S5X7): **Mulai** → capture + attest Faktur / TTTF / Surat Pesanan
   (gate blocks until all done) → **Retur Sebagian** → set return qty with the +/− steppers →
   per-item photos → AWB sticker → BA Retur → **Ringkasan** → **Kirim & Selesai**.
   *(Orders list rows are clickable — open any order to see full details + the RDO document
   pictures.)*
3. **Operator › Validasi RDO**: select the AWB → **Valid**, or **Invalid** with the per-document
   matrix (each doc: OK / Dokumen Hilang / Cap & Tanda Tangan tidak lengkap; lock enables once
   ≥1 doc is flagged). Seed **AWB02S5W8** is pre-loaded Invalid with two differing per-doc reasons.
4. **Operator › Unggah Dokumen**: find an AWB → upload RDO documents → status flips to **RDO
   Completed** (only when validation is Valid; an Invalid AWB shows the lock with its per-doc reason).
5. **Laporan SwipeRx**: the AWB + its return items (with chosen quantities) appear — each row has
   a photo thumbnail; **click any row to see full return details + evidence pictures** (modal);
   filter and Download CSV.

## Deep links
`index.html#/d/{token}` opens a driver link directly · `#/operator` · `#/report`.

## Notes / production seams
- Persistence is `localStorage` (~5 MB) — a scripted-demo store, not a real DB.
- No login: surfaces are open ("role-gated behind login in production").
- Reprint / Station-IC print-acknowledge and the Program-Manager overview are out of demo scope.
- Document images in `uploads/` are referenced by exact filename.

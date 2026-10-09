import { useState } from "react";

import { ApiError, api } from "../lib/api";
import type { DocType, VasilPhoto, VasilReturn } from "../lib/api";

/** Photo fixes for one AWB, on the Vasil page only. Removing a courier photo just hides it
 *  from this page; an upload is kept apart from the courier's photos. Reject returns never
 *  sees any of this. */
const KINDS: { doc: DocType; label: string }[] = [
  { doc: "delivery_note", label: "DN photos" },
  { doc: "rejected_goods", label: "Item photos" },
  { doc: "sp_manual", label: "SP manual photos" },
];

export default function VasilPhotos({ row, onChanged }: { row: VasilReturn; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [po, setPo] = useState(row.po_options[0]?.po_number ?? "");

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn’t save (${err.detail}).` : "Couldn’t save.");
    } finally {
      setBusy(false);
    }
  }

  function remove(p: VasilPhoto) {
    const note =
      p.source === "original"
        ? "Remove this photo from the Vasil page? The courier's original stays on Reject returns."
        : "Remove the photo you uploaded?";
    if (window.confirm(note)) void act(() => api.vasil.removePhoto(row.id, p.source, p.ref_id));
  }

  const sticker = row.proof_photos.filter((p) => p.doc_type === "awb_sticker");

  return (
    <div className="mt-4 space-y-3">
      <p className="text-xs font-semibold uppercase text-ink-muted">Fix photos (Vasil page only)</p>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="grid gap-4 md:grid-cols-3">
        {KINDS.map((k) => {
          const photos = row.proof_photos.filter((p) => p.doc_type === k.doc);
          return (
            <div key={k.doc} className="rounded-xl border border-line bg-surface p-3">
              <p className="mb-2 text-xs font-semibold">{k.label}</p>
              <div className="flex flex-wrap gap-2">
                {photos.length === 0 && <span className="text-xs text-ink-muted">None</span>}
                {photos.map((p) => (
                  <div key={`${p.source}-${p.ref_id}`} className="w-24">
                    <a href={p.photo_url} target="_blank" rel="noreferrer">
                      <img
                        src={p.photo_url}
                        alt={k.label}
                        className="h-24 w-24 rounded-lg border border-line object-cover"
                      />
                    </a>
                    <p className="mt-0.5 truncate text-[10px] text-ink-muted">
                      {p.source === "vasil" ? "Uploaded here" : "Courier"}
                      {p.po_number ? ` · ${p.po_number}` : ""}
                    </p>
                    <button
                      disabled={busy}
                      onClick={() => remove(p)}
                      className="text-[11px] font-semibold text-danger hover:underline disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {k.doc === "sp_manual" && (
                  <select
                    className="rounded-lg border border-line bg-canvas px-2 py-1 text-xs"
                    value={po}
                    onChange={(e) => setPo(e.target.value)}
                  >
                    {row.po_options.map((o) => (
                      <option key={o.po_number} value={o.po_number}>
                        {o.po_number}
                      </option>
                    ))}
                  </select>
                )}
                <label
                  className={`inline-flex cursor-pointer items-center rounded-[10px] border border-line px-3 py-1.5 text-xs font-semibold hover:bg-canvas-soft ${
                    busy || (k.doc === "sp_manual" && !po) ? "pointer-events-none opacity-50" : ""
                  }`}
                >
                  Upload
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (f) void act(() => api.vasil.uploadPhoto(row.id, k.doc, f, k.doc === "sp_manual" ? po : undefined));
                    }}
                  />
                </label>
              </div>
            </div>
          );
        })}
      </div>
      {sticker.length > 0 && (
        <div className="text-xs text-ink-muted">
          AWB sticker (view only):{" "}
          {sticker.map((p) => (
            <a key={p.ref_id} href={p.photo_url} target="_blank" rel="noreferrer" className="mr-2 underline">
              open
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

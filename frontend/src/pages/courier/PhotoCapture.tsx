import { useRef, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../../lib/api";
import type { CourierCapture, DocType } from "../../lib/api";

/** One photo slot.
 *
 * Live capture uses `<input capture="environment">` rather than getUserMedia: the
 * courier app is opened inside the Ninja driver-app webview, where getUserMedia is
 * frequently blocked or silently fails — which is exactly the dead end Round 5 called
 * out. The capture attribute hands off to the OS camera and works everywhere.
 *
 * The gallery fallback is a second input WITHOUT `capture`, tagged `exif` so a
 * Validator can tell the two apart.
 */
export default function PhotoCapture({
  token,
  docType,
  poNumber,
  existing,
  all,
  multiple = false,
  guide,
  onChange,
  label,
  hint,
}: {
  token: string;
  docType: DocType;
  poNumber?: string;
  existing?: CourierCapture;
  /** Every photo taken for this slot. Only read when `multiple` is set. */
  all?: CourierCapture[];
  /** Keep the capture buttons visible after the first shot and list them all.
   *  Used where one photo genuinely can't cover the evidence — a partial return may send
   *  back parcels from several POs, each with its own AWB label. */
  multiple?: boolean;
  /** Illustration of what a good photo looks like, shown before the courier shoots. */
  guide?: ReactNode;
  onChange: () => void;
  label: string;
  hint?: string;
}) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const shots = multiple ? (all ?? []) : existing ? [existing] : [];

  async function upload(file: File | undefined, source: "camera" | "exif") {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.courier.upload(token, docType, file, { poNumber, timestampSource: source });
      onChange();
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setError(
        detail === "photo_too_large"
          ? "Foto terlalu besar (maks 12 MB)."
          : detail === "unsupported_image_type"
            ? "Format foto tidak didukung."
            : "Gagal mengunggah. Coba lagi.",
      );
    } finally {
      setBusy(false);
      if (cameraRef.current) cameraRef.current.value = "";
      if (galleryRef.current) galleryRef.current.value = "";
    }
  }

  async function remove(id: number) {
    setBusy(true);
    try {
      await api.courier.deleteCapture(token, id);
      onChange();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">{label}</p>
          {hint && <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>}
        </div>
        {shots.length > 0 && (
          <span className="shrink-0 rounded-full bg-ok-soft px-2.5 py-0.5 text-xs font-semibold text-ok">
            ✓ {multiple ? `${shots.length} foto` : "Ada"}
          </span>
        )}
      </div>

      {guide && (
        <div className="mt-2">
          <button
            onClick={() => setShowGuide((v) => !v)}
            aria-expanded={showGuide}
            className="text-xs font-semibold text-nv-red hover:underline"
          >
            {showGuide ? "Sembunyikan contoh" : "Lihat contoh foto"}
          </button>
          {showGuide && <div className="mt-2">{guide}</div>}
        </div>
      )}

      {shots.length > 0 && (
        <div className={`mt-3 ${multiple ? "grid grid-cols-2 gap-2" : ""}`}>
          {shots.map((c) => (
            <div key={c.id}>
              <img
                src={c.photo_url}
                alt={label}
                className={`w-full rounded-xl border border-line object-cover ${multiple ? "h-28" : "h-44"}`}
              />
              <button
                onClick={() => remove(c.id)}
                disabled={busy}
                className="mt-1.5 text-xs font-semibold text-nv-red hover:underline disabled:opacity-50"
              >
                {multiple ? "Hapus" : "Ambil ulang"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* A single-shot slot hides the buttons once filled (retake replaces it); a multi
          slot keeps them, because "add another" is the whole point. */}
      {(shots.length === 0 || multiple) && (
        <div className="mt-3 space-y-2">
          <button
            onClick={() => cameraRef.current?.click()}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-nv-red px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Mengunggah…" : shots.length > 0 ? "📷 Tambah foto lagi" : "📷 Ambil foto"}
          </button>
          <button
            onClick={() => galleryRef.current?.click()}
            disabled={busy}
            className="w-full rounded-xl border border-line px-4 py-2 text-xs font-semibold text-ink-muted disabled:opacity-50"
          >
            Unggah dari galeri
          </button>
        </div>
      )}

      {error && <p className="mt-2 text-xs font-semibold text-danger">{error}</p>}

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => upload(e.target.files?.[0], "camera")}
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => upload(e.target.files?.[0], "exif")}
      />
    </div>
  );
}

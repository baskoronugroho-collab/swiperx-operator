import { useRef, useState } from "react";

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
  onChange,
  label,
  hint,
}: {
  token: string;
  docType: DocType;
  poNumber?: string;
  existing?: CourierCapture;
  onChange: () => void;
  label: string;
  hint?: string;
}) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  async function remove() {
    if (!existing) return;
    setBusy(true);
    try {
      await api.courier.deleteCapture(token, existing.id);
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
        {existing && (
          <span className="shrink-0 rounded-full bg-ok-soft px-2.5 py-0.5 text-xs font-semibold text-ok">
            ✓ Ada
          </span>
        )}
      </div>

      {existing ? (
        <div className="mt-3">
          <img
            src={existing.photo_url}
            alt={label}
            className="h-44 w-full rounded-xl border border-line object-cover"
          />
          <button
            onClick={remove}
            disabled={busy}
            className="mt-2 text-xs font-semibold text-nv-red hover:underline disabled:opacity-50"
          >
            Ambil ulang
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <button
            onClick={() => cameraRef.current?.click()}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-nv-red px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Mengunggah…" : "📷 Ambil foto"}
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

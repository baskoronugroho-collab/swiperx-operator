/** "What a good photo looks like" references for the capture steps.
 *
 * These are the REAL documents, not drawings: the actual TMP Delivery Note (AWB002STL), a
 * true crop of its Berita Acara Return table,. SP Manual capture was removed from the wizard on
 * 19 Aug 2026, so its references went with it. A courier recognises the real thing instantly; a schematic makes them translate.
 *
 * Loaded through Vite so each file is hashed and emitted as its own asset rather than
 * inlined into the JS bundle, and every <img> is `loading="lazy"` — the guides sit behind a
 * "Lihat contoh foto" toggle, so nothing is fetched until a courier actually asks for help.
 * That matters inside the Ninja driver-app webview on a bad signal.
 *
 * To swap in a better reference later, replace the file in ../../assets/guides/ — the
 * captions and checklists here are what carry the instruction.
 */
import type { ReactNode } from "react";

import dnFull from "../../assets/guides/dn-full.jpg";
import dnReturnCloseUp from "../../assets/guides/dn-return-closeup.jpg";

function Shot({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  return (
    <figure className="m-0 overflow-hidden rounded-xl border border-line bg-canvas-soft">
      <img src={src} alt={alt} loading="lazy" decoding="async" className="block w-full" />
      <figcaption className="border-t border-line px-3 py-2 text-[11px] text-ink-muted">
        {caption}
      </figcaption>
    </figure>
  );
}

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 space-y-1">
      {items.map((t) => (
        <li key={t} className="flex gap-1.5 text-xs text-ink-muted">
          <span className="text-ok">✓</span>
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

function Guide({ children, items }: { children: ReactNode; items: string[] }) {
  return (
    <div>
      <div className="space-y-2">{children}</div>
      <Checklist items={items} />
    </div>
  );
}

/** Delivery Note — the whole page, exactly as it must be shot. */
export function DeliveryNoteGuide() {
  return (
    <Guide
      items={[
        "Ambil dari atas, tegak lurus — seluruh halaman sampai QR code ikut masuk",
        "Kolom Nama, TTD Penerima dan Stempel di kanan harus terisi dan terbaca",
        "Ceklis Kondisi Penerimaan (Lengkap / Tidak Lengkap) terlihat jelas",
        "Tidak ada jari, bayangan, atau pantulan cahaya di atas tulisan",
      ]}
    >
      <Shot
        src={dnFull}
        alt="Contoh Delivery Note TMP satu halaman penuh"
        caption="Contoh Delivery Note asli. Seluruh halaman masuk — dari judul sampai QR code di bawah."
      />
    </Guide>
  );
}

/** Close-up of the DN's Berita Acara Return table — a real crop of the same document. */
export function DnReturnCloseUpGuide() {
  return (
    <Guide
      items={[
        "Fokus ke tabel Berita Acara Return, bukan seluruh halaman",
        "Nama Produk, No SKU, Batch, Expiry Date, Qty dan Kode Return harus terbaca",
        "Kalau barisnya banyak, ambil dua foto — jangan sampai ada baris terpotong",
      ]}
    >
      <Shot
        src={dnReturnCloseUp}
        alt="Contoh close-up tabel Berita Acara Return pada Delivery Note"
        caption="Bagian retur pada Delivery Note. Dekatkan sampai isi tiap kolom terbaca."
      />
    </Guide>
  );
}

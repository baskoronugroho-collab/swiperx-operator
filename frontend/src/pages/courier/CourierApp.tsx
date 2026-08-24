import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, api } from "../../lib/api";
import type { CourierOrder, DocType, Outcome } from "../../lib/api";
import PhotoCapture from "./PhotoCapture";
import { DeliveryNoteGuide, DnReturnCloseUpGuide } from "./PhotoGuides";

type Phase =
  | "identity"
  | "start"
  | "delivery_note"
  | "reject_capture"
  | "confirm"
  | "done_delivered"
  | "done_reject"
  | "done_failed"; // legacy rows only — the fail flow was removed 19 Aug 2026

/** The courier app. Opened from the tokenized link with no login — the token is the
 *  credential. Phased, one decision per screen, and it never scrolls the whole page
 *  (PRD FR-D1): the header and footer are fixed, only the middle scrolls.
 *
 *  Reworked 19 Aug 2026: the instruction to couriers is to open this link ONLY when some
 *  form of return happens at the point of delivery. Forward-delivery proof (pharmacy /
 *  receiver POD) and the fail flow are the Ninja driver app's job and were removed — the
 *  three choices are: tidak ada retur, retur sebagian, retur semua. */
export default function CourierApp() {
  const { token = "" } = useParams();
  const [order, setOrder] = useState<CourierOrder | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("start");
  const [outcome, setOutcome] = useState<Outcome>("delivered");
  /** True when "Retur semua paket" was chosen up front (QC feedback, 27 Jul): it skips
   *  the reject question — the answer is already known — and submits return_type "semua"
   *  rather than "sebagian", which is what routes it to RTS instead of a new return AWB. */
  const [fullReject, setFullReject] = useState(false);
  /** How many pieces came back. A count only: there is no way to collect item names at the
   *  door, and asking for them would cost the driver time the process cannot spare. It
   *  becomes the return OC's item_description and is what the pre-handover check reconciles
   *  against, alongside the goods photo and the notes on the BA Retur. */
  const [rejectPcs, setRejectPcs] = useState("");
  const [driverId, setDriverId] = useState("");
  const [hubName, setHubName] = useState("");
  /** Fallback: the fixed hub list is maintained by ops and can lag reality. Ticking this
   *  switches the picker to free text so a driver at a brand-new hub is never stuck. */
  const [hubNotListed, setHubNotListed] = useState(false);
  const [gateMissing, setGateMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const o = await api.courier.order(token);
      setOrder(o);
      if (o.terminal) setPhase(o.status === "delivery_failed" ? "done_failed" : "done_delivered");
      // Nobody captures anything before saying who they are. Once driver_id is set this
      // stops firing, so a resumed link does not ask twice.
      else if (!o.driver_id) setPhase("identity");
    } catch (err) {
      setLoadError(
        err instanceof ApiError && err.status === 404
          ? "Link tidak valid atau sudah tidak berlaku."
          : "Tidak bisa memuat pesanan. Periksa koneksi lalu muat ulang.",
      );
    }
  }, [token]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const capturesBy = useMemo(() => {
    const m = new Map<DocType, CourierOrder["captures"]>();
    order?.captures.forEach((c) => {
      const list = m.get(c.doc_type) ?? [];
      list.push(c);
      m.set(c.doc_type, list);
    });
    return m;
  }, [order]);

  const first = (d: DocType) => capturesBy.get(d)?.[0];
  const totalKoli = order?.po_lines.reduce((s, p) => s + p.koli, 0) ?? 0;

  async function checkGate(target: Outcome): Promise<boolean> {
    const g = await api.courier.gate(token, target);
    setGateMissing(g.missing);
    return g.complete;
  }

  async function doSubmit(target: Outcome, returnType?: "sebagian" | "semua") {
    setBusy(true);
    setError(null);
    try {
      if (!(await checkGate(target))) {
        setBusy(false);
        return;
      }
      await api.courier.submit(token, {
        outcome: target,
        return_type: returnType,
        reject_pcs: target === "reject" && rejectPcs ? Number(rejectPcs) : undefined,
      });
      setPhase(target === "reject" ? "done_reject" : "done_delivered");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Gagal mengirim. Coba lagi.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <Fullscreen title="Tidak bisa dibuka" body={loadError} tone="danger" />;
  if (!order) return <Fullscreen title="Memuat…" body="Sebentar ya." />;
  if (order.expired)
    return (
      <Fullscreen
        title="Link sudah kedaluwarsa"
        body="Link ini berlaku 30 hari. Hubungi Station IC untuk link baru."
        tone="danger"
      />
    );

  const isReturn = order.is_return;

  /* ------------------------------------------------------------- screens -- */
  let body: React.ReactNode = null;
  let footer: React.ReactNode = null;

  if (phase === "identity") {
    const idOk = /^\d+$/.test(driverId.trim());
    const hubOk = hubNotListed
      ? hubName.trim().length >= 2
      : order.hubs.includes(hubName.trim());
    body = (
      <div className="space-y-4">
        <div>
          <p className="text-lg font-bold">Sebelum mulai</p>
          <p className="mt-1 text-sm text-ink-muted">
            Isi identitas dulu. Ini dipakai untuk insentif dan supaya Station IC bisa
            menemukan pengantaran ini.
          </p>
        </div>

        <label className="block">
          <span className="mb-1.5 block text-sm font-bold">Driver ID</span>
          <input
            className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-base outline-none focus:border-nv-red"
            value={driverId}
            onChange={(e) => setDriverId(e.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            autoComplete="off"
            placeholder="contoh: 123456"
          />
          <span className="mt-1 block text-xs text-ink-muted">Angka saja.</span>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-bold">Hub</span>
          <input
            className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-base outline-none focus:border-nv-red"
            value={hubName}
            onChange={(e) => setHubName(e.target.value.toUpperCase())}
            list={hubNotListed ? undefined : "hub-options"}
            autoComplete="off"
            placeholder="ketik untuk mencari — contoh: MAC-KD5"
          />
          {!hubNotListed && (
            <datalist id="hub-options">
              {order.hubs.map((h) => (
                <option key={h} value={h} />
              ))}
            </datalist>
          )}
          <span className="mt-1 block text-xs text-ink-muted">
            {hubNotListed
              ? "Tulis nama hub kamu apa adanya."
              : hubName && !hubOk
                ? "Hub tidak ada di daftar. Pilih dari daftar, atau centang di bawah."
                : `Pilih dari ${order.hubs.length} hub yang terdaftar.`}
          </span>
          <label className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
            <input
              type="checkbox"
              className="h-4 w-4 accent-nv-red"
              checked={hubNotListed}
              onChange={(e) => setHubNotListed(e.target.checked)}
            />
            Hub saya tidak ada di daftar
          </label>
        </label>

        {error && <p className="text-sm font-semibold text-danger">{error}</p>}
      </div>
    );
    footer = (
      <Next
        disabled={busy || !idOk || !hubOk}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await api.courier.identity(token, driverId.trim(), hubName.trim(), hubNotListed);
            await reload();
            setPhase("start");
          } catch (err) {
            setError(err instanceof ApiError ? err.detail : "Gagal menyimpan. Coba lagi.");
          } finally {
            setBusy(false);
          }
        }}
      />
    );
  }

  if (phase === "start") {
    body = (
      <div className="space-y-4">
        <OrderContext order={order} totalKoli={totalKoli} />
        <div>
          <p className="text-sm font-bold">Ada barang yang diretur di titik pengantaran?</p>
          <p className="mt-1 text-xs text-ink-muted">
            Link ini khusus untuk lapor retur. Foto serah terima dan gagal kirim tetap lewat
            aplikasi driver Ninja seperti biasa.
          </p>
        </div>
        <div className="space-y-2">
          <BigChoice
            label={isReturn ? "Tidak ada barang retur (sukses)" : "Tidak ada retur"}
            sub={isReturn ? "Tetap minta form retur ditandatangani meski kosong" : "Konfirmasi saja — tidak perlu foto"}
            onClick={() => {
              setOutcome("delivered");
              setFullReject(false);
              setPhase(isReturn ? "delivery_note" : "confirm");
            }}
          />
          <BigChoice
            label={isReturn ? "Ada barang retur ditarik" : "Retur sebagian"}
            sub={isReturn ? "Bawa kembali barang + BA retur" : "Sebagian paket dikembalikan apotek"}
            tone={isReturn ? undefined : "danger"}
            onClick={() => {
              setOutcome("reject");
              setFullReject(false);
              setPhase("delivery_note");
            }}
          />
          {!isReturn && (
            <BigChoice
              label="Retur semua paket"
              sub="Apotek menolak seluruh kiriman"
              tone="danger"
              onClick={() => {
                setOutcome("reject");
                setFullReject(true);
                setPhase("delivery_note");
              }}
            />
          )}
        </div>
      </div>
    );
  }

  if (phase === "delivery_note") {
    const dn = first(isReturn ? "return_form" : "delivery_note");
    const docType: DocType = isReturn ? "return_form" : "delivery_note";
    body = (
      <div className="space-y-4">
        <PhotoCapture
          token={token}
          docType={docType}
          existing={dn}
          onChange={reload}
          guide={<DeliveryNoteGuide />}
          label={isReturn ? "Foto BA Retur" : "Foto Delivery Note (halaman penuh)"}
          hint={
            isReturn
              ? "Meski tidak ada barang retur, form tetap harus ditandatangani apotek."
              : "Foto harus jelas, tidak blur, tidak terpotong."
          }
        />
        {dn && (
          <Attest
            checked={!!dn.signed_stamped}
            label="Sudah ditandatangani DAN distempel penerima"
            onChange={async (v) => {
              await api.courier.attest(token, dn.id, v);
              await reload();
            }}
          />
        )}
      </div>
    );
    footer = (
      <Next
        disabled={!dn || !dn.signed_stamped}
        onClick={() => setPhase(isReturn ? "confirm" : "reject_capture")}
        onBack={() => setPhase("start")}
      />
    );
  }

  if (phase === "reject_capture") {
    const dnShots = capturesBy.get("delivery_note") ?? [];
    body = (
      <div className="space-y-4">
        {/* Both reject paths land here, so the copy must follow the branch the courier
            actually chose — showing partial-return wording inside "Retur semua paket"
            was the QC finding on 10 Aug (deck slide 6). */}
        <div className="rounded-2xl bg-danger-soft p-4 text-sm text-danger">
          <p className="font-bold">
            {fullReject
              ? "Apotek menolak seluruh kiriman — minta DN diisi & ditandatangani"
              : "Minta apotek isi bagian retur di Delivery Note"}
          </p>
          <p className="mt-1">
            {fullReject
              ? "Apotek dan kurir sama-sama tanda tangan. Bawa kembali SELURUH paket."
              : "Apotek dan kurir sama-sama tanda tangan. Pisahkan barang retur dari yang lain."}
          </p>
        </div>
        <PhotoCapture
          token={token}
          docType="delivery_note"
          existing={dnShots[1]}
          onChange={reload}
          guide={<DnReturnCloseUpGuide />}
          label={
            fullReject
              ? "Foto Delivery Note (close-up keterangan penolakan)"
              : "Foto bagian retur Delivery Note (close-up)"
          }
          hint="Bagian bawah DN yang sudah diisi kondisi penerimaan + kolom retur."
        />
        {/* Both of these accept several shots: a partial return can send back parcels from
            more than one PO, and one frame rarely covers every label or every box. */}
        <PhotoCapture
          token={token}
          docType="rejected_goods"
          multiple
          all={capturesBy.get("rejected_goods") ?? []}
          onChange={reload}
          label={fullReject ? "Foto seluruh paket yang diretur" : "Foto barang yang diretur"}
          hint="Boleh lebih dari satu foto kalau tidak muat dalam satu bingkai."
        />
        <PhotoCapture
          token={token}
          docType="awb_sticker"
          multiple
          all={capturesBy.get("awb_sticker") ?? []}
          onChange={reload}
          label="Foto label AWB"
          hint="Foto tiap label kalau ada beberapa paket retur."
        />
        <label className="block rounded-2xl border border-line bg-surface p-4">
          <span className="block text-sm font-bold">Berapa pcs barang yang diretur?</span>
          <span className="mt-1 block text-xs text-ink-muted">
            Jumlah saja, tidak perlu nama barang. Dicocokkan nanti dengan barang yang diterima.
          </span>
          <input
            className="mt-2 w-full rounded-xl border border-line bg-canvas px-4 py-3 text-base outline-none focus:border-nv-red"
            value={rejectPcs}
            onChange={(e) => setRejectPcs(e.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            autoComplete="off"
            placeholder="contoh: 3"
          />
        </label>
      </div>
    );
    footer = (
      <Next
        disabled={
          dnShots.length < 2 ||
          !first("rejected_goods") ||
          !first("awb_sticker") ||
          !rejectPcs
        }
        onClick={() => setPhase("confirm")}
        onBack={() => setPhase("delivery_note")}
      />
    );
  }

  if (phase === "confirm") {
    body = (
      <div className="space-y-4">
        <p className="text-lg font-bold">Cek sebelum kirim</p>
        <OrderContext order={order} totalKoli={totalKoli} />
        {outcome === "delivered" && !isReturn && (
          <div className="rounded-2xl bg-ok-soft p-4 text-sm text-ok">
            <b>Tidak ada barang retur.</b> Tidak perlu foto — cukup konfirmasi, lalu selesaikan
            pengantaran di aplikasi driver Ninja.
          </div>
        )}
        <div className="rounded-2xl border border-line bg-surface p-4">
          <p className="text-sm font-bold">
            {order.captures.length} foto terkumpul
          </p>
          <ul className="mt-2 space-y-1 text-xs text-ink-muted">
            {order.captures.map((c) => (
              <li key={c.id}>
                ✓ {DOC_LABELS[c.doc_type]}
                {c.po_number ? ` — ${c.po_number}` : ""}
              </li>
            ))}
          </ul>
        </div>
        {outcome === "reject" && (
          <div className="rounded-2xl bg-danger-soft p-4 text-sm text-danger">
            Ditandai sebagai <b>{fullReject ? "retur semua paket" : "retur sebagian"}</b>. Tim
            Ops akan menindaklanjuti retur ini.
          </div>
        )}
        {gateMissing.length > 0 && (
          <div className="rounded-2xl bg-warn-soft p-4 text-sm text-warn">
            <p className="font-bold">Belum lengkap:</p>
            <ul className="mt-1 list-inside list-disc">
              {gateMissing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {error && <p className="text-sm font-semibold text-danger">{error}</p>}
      </div>
    );
    footer = (
      <div className="space-y-2">
        <button
          disabled={busy}
          onClick={() =>
            doSubmit(outcome, outcome === "reject" ? (fullReject ? "semua" : "sebagian") : undefined)
          }
          className="w-full rounded-xl bg-nv-red px-4 py-3.5 text-base font-bold text-white disabled:opacity-50"
        >
          {busy ? "Mengirim…" : "Konfirmasi pengantaran"}
        </button>
        <button
          onClick={() => setPhase(outcome === "reject" ? "reject_capture" : "start")}
          className="w-full py-2 text-sm font-semibold text-ink-muted"
        >
          Kembali
        </button>
      </div>
    );
  }

  if (phase.startsWith("done")) {
    const reject = phase === "done_reject";
    const failed = phase === "done_failed";
    return (
      <Done
        awb={order.awb_id}
        pharmacy={order.pharmacy_name}
        reject={reject}
        failed={failed}
      />
    );
  }

  /* The segmented progress rail: one segment per remaining phase of the CURRENT route.
     It answers the courier's only real question at the door: how much is left? */
  const rail: Phase[] = isReturn
    ? ["start", "delivery_note", "confirm"]
    : outcome === "reject"
      ? ["start", "delivery_note", "reject_capture", "confirm"]
      : ["start", "confirm"];
  const railAt = Math.max(0, rail.indexOf(phase));

  return (
    <div className="no-scroll-shell flex flex-col bg-canvas">
      <div className="brand-hairline shrink-0" />
      <header className="shrink-0 border-b border-line bg-surface px-5 pb-3 pt-3">
        <div className="font-mono text-base font-semibold tracking-tight">{order.awb_id}</div>
        <div className="mt-0.5 text-xs text-ink-muted">{order.pharmacy_name}</div>
        <div className="mt-2.5 flex gap-1" aria-hidden>
          {rail.map((p, i) => (
            <span
              key={p}
              className={`h-1 flex-1 rounded-full transition-colors duration-150 ${
                i <= railAt ? "bg-nv-red" : "bg-canvas-soft"
              }`}
            />
          ))}
        </div>
      </header>

      <div key={phase} className="phase-in flex-1 overflow-y-auto px-5 py-5">{body}</div>

      {footer && <footer className="shrink-0 border-t border-line bg-surface px-5 py-4">{footer}</footer>}
    </div>
  );
}

/* --------------------------------------------------------------- pieces --- */

const DOC_LABELS: Record<DocType, string> = {
  pharmacy_pod: "Foto apotek",
  receiver_pod: "Foto penerima",
  delivery_note: "Delivery Note",
  sp_manual: "SP Manual",
  rejected_goods: "Barang retur",
  awb_sticker: "Label AWB",
  return_form: "BA Retur",
};

function OrderContext({ order, totalKoli }: { order: CourierOrder; totalKoli: number }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <p className="text-sm font-bold">{order.pharmacy_name}</p>
      <p className="mt-1 text-xs text-ink-muted">{order.address}</p>
      <p className="mt-3 text-sm">
        <b>{totalKoli}</b> koli · <b>{order.po_lines.length}</b> PO
      </p>
      <ul className="mt-2 space-y-0.5">
        {order.po_lines.map((p) => (
          <li key={p.po_number} className="font-mono text-[11px] text-ink-muted">
            {p.po_number} — {p.koli} koli
          </li>
        ))}
      </ul>
      {order.is_return && order.item_detail && (
        <p className="mt-3 rounded-xl bg-canvas-soft p-3 text-xs">{order.item_detail}</p>
      )}
    </div>
  );
}

function BigChoice({
  label,
  sub,
  tone,
  onClick,
}: {
  label: string;
  sub: string;
  tone?: "danger";
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-2xl border p-4 text-left ${
        tone === "danger" ? "border-danger/30 bg-danger-soft" : "border-line bg-surface"
      }`}
    >
      <span className={`block font-bold ${tone === "danger" ? "text-danger" : ""}`}>{label}</span>
      <span className="mt-0.5 block text-xs text-ink-muted">{sub}</span>
    </button>
  );
}

function Attest({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4">
      <input
        type="checkbox"
        className="mt-0.5 h-5 w-5 accent-nv-red"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="text-sm font-semibold">{label}</span>
    </label>
  );
}

function Next({
  disabled,
  hint,
  hideNext,
  onClick,
  onBack,
}: {
  disabled?: boolean;
  hint?: string;
  hideNext?: boolean;
  onClick?: () => void;
  onBack?: () => void;
}) {
  return (
    <div className="space-y-2">
      {hint && <p className="text-center text-xs font-semibold text-warn">{hint}</p>}
      {!hideNext && (
        <button
          disabled={disabled}
          onClick={onClick}
          className="w-full rounded-xl bg-nv-red px-4 py-3.5 text-base font-bold text-white disabled:opacity-40"
        >
          Lanjut
        </button>
      )}
      {onBack && (
        <button onClick={onBack} className="w-full py-2 text-sm font-semibold text-ink-muted">
          Kembali
        </button>
      )}
    </div>
  );
}

function Done({
  awb,
  pharmacy,
  reject,
  failed,
}: {
  awb: string;
  pharmacy: string;
  reject: boolean;
  failed: boolean;
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-canvas px-5 py-8">
      <div className="flex-1">
        <div
          className={`grid h-14 w-14 place-items-center rounded-full text-2xl ${
            failed ? "bg-danger-soft text-danger" : "bg-ok-soft text-ok"
          }`}
        >
          {failed ? "!" : "✓"}
        </div>
        <h1 className="mt-4 text-xl font-bold">
          {failed ? "Laporan gagal kirim terkirim" : "Pengantaran terkonfirmasi"}
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          {pharmacy} · <span className="font-mono">{awb}</span>
        </p>

        <div className="mt-6 rounded-2xl border-2 border-nv-red bg-nv-red-soft p-4">
          <p className="text-sm font-bold text-nv-red">Jangan lupa!</p>
          <p className="mt-1 text-sm">
            Selesaikan juga pengantaran ini di <b>aplikasi driver Ninja</b>. Aplikasi ini hanya
            merekam dokumen — status paket tidak otomatis tertutup.
          </p>
        </div>

        {reject && (
          <div className="mt-4 rounded-2xl border border-line bg-surface p-4">
            <p className="text-sm font-bold">Ada barang retur — laporkan sekarang</p>
            <p className="mt-1 text-sm text-ink-muted">
              <b>Screenshot halaman ini</b> dan kirim ke Station IC / Spv supaya tim DE membuatkan
              TID retur.
            </p>
            <p className="mt-3 text-xs font-semibold uppercase text-ink-muted">AWB yang diretur</p>
            <p className="font-mono text-sm">{awb}</p>
          </div>
        )}
      </div>

      <p className="pt-8 text-center text-xs text-ink-muted">
        Aman ditutup. Membuka link ini lagi menampilkan status terakhir.
      </p>
    </div>
  );
}

function Fullscreen({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone?: "danger";
}) {
  return (
    <div className="grid min-h-dvh place-items-center bg-canvas px-6 text-center">
      <div>
        <p className={`text-lg font-bold ${tone === "danger" ? "text-danger" : ""}`}>{title}</p>
        <p className="mt-2 max-w-xs text-sm text-ink-muted">{body}</p>
      </div>
    </div>
  );
}

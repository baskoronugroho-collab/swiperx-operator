import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, api } from "../../lib/api";
import type { CourierOrder, DocType, FailReason, Outcome } from "../../lib/api";
import PhotoCapture from "./PhotoCapture";

type Phase =
  | "start"
  | "pharmacy_pod"
  | "receiver_pod"
  | "delivery_note"
  | "sp_manual"
  | "reject_question"
  | "reject_capture"
  | "confirm"
  | "fail_reason"
  | "fail_photo"
  | "done_delivered"
  | "done_reject"
  | "done_failed";

/** The courier app. Opened from the tokenized link with no login — the token is the
 *  credential. Phased, one decision per screen, and it never scrolls the whole page
 *  (PRD FR-D1): the header and footer are fixed, only the middle scrolls. */
export default function CourierApp() {
  const { token = "" } = useParams();
  const [order, setOrder] = useState<CourierOrder | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("start");
  const [outcome, setOutcome] = useState<Outcome>("delivered");
  /** True when "Retur semua paket" was chosen up front (QC feedback, 27 Jul): a full
   *  reject skips the SP-Manual step (nothing is accepted, so no SP can be requested)
   *  and submits return_type "semua", not "sebagian". */
  const [fullReject, setFullReject] = useState(false);
  const [spPos, setSpPos] = useState<string[]>([]);
  const [failReason, setFailReason] = useState<FailReason | null>(null);
  const [failNote, setFailNote] = useState("");
  const [gateMissing, setGateMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const o = await api.courier.order(token);
      setOrder(o);
      if (o.terminal) setPhase(o.status === "delivery_failed" ? "done_failed" : "done_delivered");
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
      await api.courier.submit(token, { outcome: target, return_type: returnType });
      setPhase(target === "reject" ? "done_reject" : "done_delivered");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Gagal mengirim. Coba lagi.");
    } finally {
      setBusy(false);
    }
  }

  async function doFail() {
    if (!failReason) return;
    setBusy(true);
    setError(null);
    try {
      await api.courier.fail(token, { fail_reason: failReason, reason_note: failNote || undefined });
      setPhase("done_failed");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? "Foto bukti belum ada."
          : "Gagal mengirim. Coba lagi.",
      );
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

  if (phase === "start") {
    body = (
      <div className="space-y-4">
        <OrderContext order={order} totalKoli={totalKoli} />
        <p className="text-sm font-bold">Apa yang terjadi di lokasi?</p>
        <div className="space-y-2">
          <BigChoice
            label={isReturn ? "Tidak ada barang retur (sukses)" : "Pengantaran normal"}
            sub={isReturn ? "Tetap minta form retur ditandatangani meski kosong" : "Semua paket diterima"}
            onClick={() => {
              setOutcome("delivered");
              setFullReject(false);
              setPhase(isReturn ? "delivery_note" : "pharmacy_pod");
            }}
          />
          <BigChoice
            label={isReturn ? "Ada barang retur ditarik" : "Retur semua paket"}
            sub={isReturn ? "Bawa kembali barang + BA retur" : "Apotek menolak seluruh kiriman"}
            onClick={() => {
              setOutcome("reject");
              setFullReject(!isReturn);
              setPhase(isReturn ? "delivery_note" : "pharmacy_pod");
            }}
          />
          <BigChoice
            label="Gagal kirim"
            sub="Tidak ada serah terima sama sekali"
            tone="danger"
            onClick={() => setPhase("fail_reason")}
          />
        </div>
      </div>
    );
  }

  if (phase === "pharmacy_pod") {
    body = (
      <PhotoCapture
        token={token}
        docType="pharmacy_pod"
        existing={first("pharmacy_pod")}
        onChange={reload}
        label="Foto apotek"
        hint="Tampak depan apotek / lokasi penerima."
      />
    );
    footer = <Next disabled={!first("pharmacy_pod")} onClick={() => setPhase("receiver_pod")} />;
  }

  if (phase === "receiver_pod") {
    body = (
      <PhotoCapture
        token={token}
        docType="receiver_pod"
        existing={first("receiver_pod")}
        onChange={reload}
        label="Foto penerima"
        hint="Orang yang menerima paket. Wajib Apoteker (APJ) atau TTK — bukan security."
      />
    );
    footer = (
      <Next
        disabled={!first("receiver_pod")}
        onClick={() => setPhase("delivery_note")}
        onBack={() => setPhase("pharmacy_pod")}
      />
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
        onClick={() =>
          // Full reject skips SP-Manual entirely — no package is accepted, so there is
          // no SP to request from the pharmacy (QC feedback slide 5).
          setPhase(isReturn ? "confirm" : fullReject ? "reject_capture" : "sp_manual")
        }
        onBack={() => setPhase(isReturn ? "start" : "receiver_pod")}
      />
    );
  }

  if (phase === "sp_manual") {
    body = (
      <div className="space-y-4">
        <div className="rounded-2xl bg-warn-soft p-4 text-sm text-warn">
          <p className="font-bold">Cek Faktur tiap PO</p>
          <p className="mt-1">
            Kalau tertulis <b>SP Manual</b> → minta SP ke apotek dan foto. Kalau tertulis{" "}
            <b>SP Elektronik + Prekursor</b> → SP sudah menempel, tidak perlu minta. Kalau{" "}
            <b>Non-Prekursor</b> → tidak perlu SP sama sekali.
          </p>
        </div>
        <p className="text-sm font-bold">Tandai PO yang butuh SP Manual</p>
        <div className="space-y-2">
          {order.po_lines.map((po) => {
            const flagged = spPos.includes(po.po_number);
            const shot = capturesBy.get("sp_manual")?.find((c) => c.po_number === po.po_number);
            return (
              <div key={po.po_number} className="rounded-2xl border border-line bg-surface p-3">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-nv-red"
                    checked={flagged}
                    onChange={(e) =>
                      setSpPos((prev) =>
                        e.target.checked
                          ? [...prev, po.po_number]
                          : prev.filter((p) => p !== po.po_number),
                      )
                    }
                  />
                  <span className="flex-1">
                    <span className="block font-mono text-xs">{po.po_number}</span>
                    <span className="block text-xs text-ink-muted">{po.koli} koli</span>
                  </span>
                  {shot && <span className="text-xs font-semibold text-ok">✓ SP</span>}
                </label>
                {flagged && (
                  <div className="mt-3">
                    <PhotoCapture
                      token={token}
                      docType="sp_manual"
                      poNumber={po.po_number}
                      existing={shot}
                      onChange={reload}
                      label="Foto SP Manual"
                      hint="Prekursor → gunakan template SP Prekursor."
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
    const pending = spPos.filter(
      (p) => !capturesBy.get("sp_manual")?.some((c) => c.po_number === p),
    );
    footer = (
      <Next
        disabled={pending.length > 0}
        hint={pending.length > 0 ? `${pending.length} SP Manual belum difoto` : undefined}
        onClick={() => setPhase(outcome === "reject" ? "reject_capture" : "reject_question")}
        onBack={() => setPhase("delivery_note")}
      />
    );
  }

  if (phase === "reject_question") {
    body = (
      <div className="space-y-4">
        <p className="text-lg font-bold">Ada barang yang ditolak / diretur?</p>
        <p className="text-sm text-ink-muted">
          Kalau ada sebagian barang yang tidak diterima apotek, pilih “Ya”.
        </p>
        <div className="space-y-2">
          <BigChoice
            label="Tidak ada"
            sub="Semua paket diterima"
            onClick={() => {
              setOutcome("delivered");
              setPhase("confirm");
            }}
          />
          <BigChoice
            label="Ya, ada retur sebagian"
            sub="Isi BA retur dan foto barangnya"
            tone="danger"
            onClick={() => {
              setOutcome("reject");
              setFullReject(false);
              setPhase("reject_capture");
            }}
          />
        </div>
      </div>
    );
    footer = <Next hideNext onBack={() => setPhase("sp_manual")} />;
  }

  if (phase === "reject_capture") {
    const dnShots = capturesBy.get("delivery_note") ?? [];
    body = (
      <div className="space-y-4">
        <div className="rounded-2xl bg-danger-soft p-4 text-sm text-danger">
          <p className="font-bold">Minta apotek isi bagian retur di Delivery Note</p>
          <p className="mt-1">Apotek dan kurir sama-sama tanda tangan. Pisahkan barang retur dari yang lain.</p>
        </div>
        <PhotoCapture
          token={token}
          docType="delivery_note"
          existing={dnShots[1]}
          onChange={reload}
          label="Foto bagian retur Delivery Note (close-up)"
          hint="Bagian bawah DN yang sudah diisi kondisi penerimaan + kolom retur."
        />
        <PhotoCapture
          token={token}
          docType="rejected_goods"
          existing={first("rejected_goods")}
          onChange={reload}
          label="Foto barang yang diretur"
          hint="Satu foto keseluruhan barang retur — bukan per item."
        />
        <PhotoCapture
          token={token}
          docType="awb_sticker"
          existing={first("awb_sticker")}
          onChange={reload}
          label="Foto label AWB"
        />
      </div>
    );
    footer = (
      <Next
        disabled={dnShots.length < 2 || !first("rejected_goods") || !first("awb_sticker")}
        onClick={() => setPhase("confirm")}
        onBack={() =>
          setPhase(isReturn || fullReject ? "delivery_note" : "reject_question")
        }
      />
    );
  }

  if (phase === "confirm") {
    body = (
      <div className="space-y-4">
        <p className="text-lg font-bold">Cek sebelum kirim</p>
        <OrderContext order={order} totalKoli={totalKoli} />
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
          onClick={() => setPhase(outcome === "reject" ? "reject_capture" : "reject_question")}
          className="w-full py-2 text-sm font-semibold text-ink-muted"
        >
          Kembali
        </button>
      </div>
    );
  }

  if (phase === "fail_reason") {
    body = (
      <div className="space-y-4">
        <p className="text-lg font-bold">Kenapa gagal kirim?</p>
        <div className="space-y-2">
          {order.fail_reasons.map((r) => (
            <button
              key={r.code}
              onClick={() => setFailReason(r.code)}
              className={`w-full rounded-2xl border p-3 text-left text-sm ${
                failReason === r.code
                  ? "border-nv-red bg-nv-red-soft font-semibold"
                  : "border-line bg-surface"
              }`}
            >
              {r.id}
              <span className="block text-xs text-ink-muted">{r.en}</span>
            </button>
          ))}
        </div>
        <textarea
          className="w-full rounded-xl border border-line px-3 py-2 text-sm"
          rows={2}
          placeholder="Catatan tambahan (opsional)"
          value={failNote}
          onChange={(e) => setFailNote(e.target.value)}
        />
      </div>
    );
    footer = (
      <Next disabled={!failReason} onClick={() => setPhase("fail_photo")} onBack={() => setPhase("start")} />
    );
  }

  if (phase === "fail_photo") {
    body = (
      <div className="space-y-4">
        <PhotoCapture
          token={token}
          docType="awb_sticker"
          existing={first("awb_sticker")}
          onChange={reload}
          label="Foto bukti"
          hint="Foto lokasi / kondisi yang membuktikan alasan gagal kirim."
        />
        <p className="text-xs text-ink-muted">
          Foto diambil langsung dan waktunya dicatat untuk keperluan pemeriksaan.
        </p>
        {error && <p className="text-sm font-semibold text-danger">{error}</p>}
      </div>
    );
    footer = (
      <div className="space-y-2">
        <button
          disabled={!first("awb_sticker") || busy}
          onClick={doFail}
          className="w-full rounded-xl bg-danger px-4 py-3.5 text-base font-bold text-white disabled:opacity-50"
        >
          {busy ? "Mengirim…" : "Kirim laporan gagal"}
        </button>
        <button onClick={() => setPhase("fail_reason")} className="w-full py-2 text-sm font-semibold text-ink-muted">
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

  /* The segmented progress rail: one segment per remaining phase of the CURRENT route
     through the wizard (routes differ — full reject skips SP-Manual, returns skip PODs).
     It answers the courier's only real question at the door: how much is left? */
  const rail: Phase[] = phase === "fail_reason" || phase === "fail_photo"
    ? ["fail_reason", "fail_photo"]
    : isReturn
      ? ["start", "delivery_note", "confirm"]
      : fullReject
        ? ["start", "pharmacy_pod", "receiver_pod", "delivery_note", "reject_capture", "confirm"]
        : ["start", "pharmacy_pod", "receiver_pod", "delivery_note", "sp_manual", "reject_question",
           ...(outcome === "reject" ? (["reject_capture"] as Phase[]) : []), "confirm"];
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

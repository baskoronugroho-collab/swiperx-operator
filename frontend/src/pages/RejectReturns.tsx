import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { RejectReturn } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "../components/ui";

const TABS = [
  { key: "pending_ack", label: "Not yet acknowledged" },
  { key: "acknowledged", label: "Awaiting action" },
  { key: "tids_sent", label: "Closed — TIDs sent" },
  { key: "rts_requested", label: "Closed — RTS triggered" },
  { key: "", label: "All" },
] as const;

/** Lane 3 — the reject-return worklist, as a flat filterable LIST (27 Jul): the cards
 *  didn't scale past a handful of rows. Stage tabs + free-text search; each row expands
 *  for proof photos and the TID action. */
export default function RejectReturns() {
  const [tab, setTab] = useState<string>("pending_ack");
  const [rows, setRows] = useState<RejectReturn[] | null>(null);
  const [rtsShipper, setRtsShipper] = useState("11398434");
  const [q, setQ] = useState("");
  /* Per-column filters (19 Aug request): each narrows independently, on top of the tabs
     and the free-text search. All client-side — the list is capped at 500 rows. */
  const [fType, setFType] = useState("");
  const [fOrigin, setFOrigin] = useState("");
  const [fHub, setFHub] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async () => {
    setRows(null);
    try {
      const r = await api.returns.list(tab || undefined);
      setRows(r.returns);
      if ("rts_shipper_id" in r) setRtsShipper((r as { rts_shipper_id: string }).rts_shipper_id);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? "No access." : "Couldn’t load the worklist.");
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  const hubs = useMemo(
    () => Array.from(new Set((rows ?? []).map((r) => r.hub_name).filter(Boolean))).sort() as string[],
    [rows],
  );

  const filtered = useMemo(() => {
    if (!rows) return null;
    const term = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (fType && r.return_type !== fType) return false;
      if (fOrigin === "unknown" ? !r.origin_unknown : fOrigin && r.origin !== fOrigin) return false;
      if (fHub && r.hub_name !== fHub) return false;
      if (!term) return true;
      return [r.original_awb_id, r.pharmacy_name, r.city ?? "", r.return_tids ?? "", r.hub_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [rows, q, fType, fOrigin, fHub]);

  /* Bulk origin fix: only offered while the unknown filter is on, and only rows still
     unknown are touched server-side — a recorded origin is never overwritten from here. */
  async function bulkSetOrigin(origin: string) {
    if (!filtered) return;
    const ids = filtered.filter((r) => r.origin_unknown).map((r) => r.id);
    if (ids.length === 0) return;
    setBulkBusy(true);
    try {
      await api.returns.setOrigin(ids, origin);
      await load();
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Reject returns</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Every reject flagged by a courier. Acknowledge it, then close it. A{" "}
            <strong className="font-semibold text-ink">partial</strong> return needs replacement
            TIDs minted on the RTS account{" "}
            <span className="font-mono">{rtsShipper}</span>; a{" "}
            <strong className="font-semibold text-ink">whole-delivery refusal</strong> needs no new
            TID at all — trigger RTS on the original forward tracking number instead.
          </p>
        </div>
        <a
          href={api.returns.exportUrl()}
          className="rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-canvas-soft"
        >
          Export CSV
        </a>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl bg-canvas-soft p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition ${
                tab === t.key ? "bg-surface text-ink shadow-sm" : "text-ink-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          className={`${inputClass} max-w-xs`}
          placeholder="Search AWB, pharmacy, city, TID, hub…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className={`${inputClass} w-auto`} value={fType} onChange={(e) => setFType(e.target.value)}>
          <option value="">Type: all</option>
          <option value="sebagian">Sebagian</option>
          <option value="semua">Semua</option>
        </select>
        <select className={`${inputClass} w-auto`} value={fOrigin} onChange={(e) => setFOrigin(e.target.value)}>
          <option value="">Origin: all</option>
          <option value="TMP_DEPOK">TMP Depok</option>
          <option value="TMP_SURABAYA">TMP Surabaya</option>
          <option value="unknown">Origin unknown</option>
        </select>
        <select className={`${inputClass} w-auto`} value={fHub} onChange={(e) => setFHub(e.target.value)}>
          <option value="">Hub: all</option>
          {hubs.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
      </div>

      {fOrigin === "unknown" && filtered && filtered.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl bg-warn-soft px-4 py-3 text-sm">
          <span className="font-semibold text-warn">
            {filtered.filter((r) => r.origin_unknown).length} row(s) have no origin — a return
            cannot be exported until it knows which warehouse to go back to.
          </span>
          <span className="text-ink-muted">Set all shown to:</span>
          <Button variant="ghost" disabled={bulkBusy} onClick={() => bulkSetOrigin("TMP_DEPOK")}>
            TMP Depok
          </Button>
          <Button variant="ghost" disabled={bulkBusy} onClick={() => bulkSetOrigin("TMP_SURABAYA")}>
            TMP Surabaya
          </Button>
        </div>
      )}

      {error && <ErrorNote>{error}</ErrorNote>}
      {!filtered && !error && <Spinner label="Loading…" />}
      {filtered && filtered.length === 0 && (
        <EmptyState
          title={q ? "No matches" : "Nothing here"}
          body={!q && tab === "pending_ack" ? "No rejects waiting to be acknowledged." : undefined}
        />
      )}

      {filtered && filtered.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-3">AWB</th>
                  <th className="px-4 py-3">Pharmacy</th>
                  <th className="px-4 py-3">City</th>
                  <th className="px-4 py-3">Hub</th>
                  <th className="px-4 py-3">Origin</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Rejected</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3">Ack</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <Row
                    key={r.id}
                    row={r}
                    open={openId === r.id}
                    onToggle={() => setOpenId(openId === r.id ? null : r.id)}
                    onChange={load}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function StageBadge({ stage }: { stage: RejectReturn["stage"] }) {
  if (stage === "rts_requested") return <Badge tone="ok">RTS triggered</Badge>;
  if (stage === "tids_sent") return <Badge tone="ok">TIDs sent</Badge>;
  if (stage === "acknowledged") return <Badge tone="warn">Awaiting action</Badge>;
  return <Badge tone="danger">Not acknowledged</Badge>;
}

function Row({
  row,
  open,
  onToggle,
  onChange,
}: {
  row: RejectReturn;
  open: boolean;
  onToggle: () => void;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tids, setTids] = useState("");

  async function toggleAck(v: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.returns.acknowledge(row.id, v);
      onChange();
    } catch {
      setError("Couldn’t update.");
      setBusy(false);
    }
  }

  async function requestRts() {
    setBusy(true);
    setError(null);
    try {
      await api.returns.requestRts(row.id);
      onChange();
    } catch (err) {
      setError(
        err instanceof ApiError && err.detail === "not_acknowledged"
          ? "Acknowledge first."
          : "Couldn’t save.",
      );
      setBusy(false);
    }
  }

  async function sendTids() {
    setBusy(true);
    setError(null);
    try {
      await api.returns.sendTids(row.id, tids);
      onChange();
    } catch (err) {
      setError(
        err instanceof ApiError && err.detail === "not_acknowledged"
          ? "Acknowledge first."
          : "Couldn’t save.",
      );
      setBusy(false);
    }
  }

  return (
    <>
      <tr className="border-t border-line hover:bg-canvas-soft/50">
        <td className="px-4 py-3"><span className="awb-chip">{row.original_awb_id}</span></td>
        <td className="px-4 py-3">{row.pharmacy_name}</td>
        <td className="px-4 py-3 text-ink-muted">{row.city ?? "—"}</td>
        <td className="px-4 py-3 font-mono text-xs">{row.hub_name ?? "—"}</td>
        <td className="px-4 py-3">
          {row.origin_unknown ? (
            <Badge tone="warn">unknown</Badge>
          ) : (
            <span className="text-xs">{row.origin === "TMP_SURABAYA" ? "TMP Surabaya" : "TMP Depok"}</span>
          )}
        </td>
        <td className="px-4 py-3">
          <Badge tone={row.return_type === "semua" ? "danger" : "info"}>
            {row.return_type === "semua" ? "Semua" : "Sebagian"}
          </Badge>
        </td>
        <td className="px-4 py-3 whitespace-nowrap text-xs text-ink-muted">{row.rejected_at}</td>
        <td className="px-4 py-3">
          <StageBadge stage={row.stage} />
        </td>
        <td className="px-4 py-3">
          <input
            type="checkbox"
            className="h-5 w-5 accent-nv-red"
            checked={!!row.acknowledged_at}
            disabled={busy || row.stage === "tids_sent"}
            onChange={(e) => toggleAck(e.target.checked)}
            title="Acknowledge"
          />
        </td>
        <td className="px-4 py-3">
          <button onClick={onToggle} className="text-xs font-semibold text-nv-red hover:underline">
            {open ? "Close" : row.stage === "tids_sent" ? "Detail" : "Handle"}
          </button>
        </td>
      </tr>

      {open && (
        <tr className="border-t border-line bg-canvas-soft/40">
          <td colSpan={10} className="px-4 py-4">
            <div className="flex flex-wrap items-start gap-6">
              {row.proof_photos.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase text-ink-muted">Proof from the door</p>
                  <div className="flex gap-2">
                    {row.proof_photos.map((p, i) => (
                      <a key={i} href={p.photo_url} target="_blank" rel="noreferrer">
                        <img
                          src={p.photo_url}
                          alt={p.doc_type}
                          className="h-24 w-24 rounded-lg border border-line object-cover"
                        />
                        <span className="mt-1 block text-center text-[10px] text-ink-muted">{p.doc_type}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              <div className="min-w-72 flex-1">
                {/* A full reject closes by triggering RTS on the ORIGINAL forward tracking
                    number — no second TID exists to paste, so the TID box would be a trap. */}
                {row.closes_by === "rts" ? (
                  row.stage === "rts_requested" ? (
                    <div className="text-sm">
                      <p>
                        <span className="font-semibold">RTS triggered</span> on{" "}
                        <span className="font-mono">{row.original_awb_id}</span>
                      </p>
                      <p className="mt-1 text-xs text-ink-muted">
                        {row.rts_requested_at} by {row.rts_requested_by_email ?? "—"}
                        {row.acknowledged_by_email && ` · acknowledged by ${row.acknowledged_by_email}`}
                      </p>
                    </div>
                  ) : (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">
                        Whole delivery refused
                      </p>
                      <p className="mb-2 max-w-md text-sm text-ink-muted">
                        No new return TID is needed. Trigger <strong className="text-ink">RTS</strong>{" "}
                        on the forward tracking number{" "}
                        <span className="font-mono text-ink">{row.original_awb_id}</span> in Ninja,
                        then record it here.
                      </p>
                      <Button onClick={requestRts} disabled={busy || !row.acknowledged_at}>
                        Mark RTS triggered
                      </Button>
                      {!row.acknowledged_at && (
                        <p className="mt-1.5 text-xs text-ink-muted">
                          Tick the Ack checkbox first — it records who is handling this reject.
                        </p>
                      )}
                      {error && <p className="mt-1.5 text-sm font-semibold text-danger">{error}</p>}
                    </div>
                  )
                ) : row.stage === "tids_sent" ? (
                  <div className="text-sm">
                    <p>
                      <span className="font-semibold">Replacement TIDs:</span>{" "}
                      <span className="font-mono">{row.return_tids}</span>
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">
                      {row.tids_sent_at} by {row.tids_sent_by_email ?? "—"}
                      {row.acknowledged_by_email && ` · acknowledged by ${row.acknowledged_by_email}`}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">
                      Replacement return TID(s)
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <input
                        className={`${inputClass} max-w-sm`}
                        placeholder="Paste the TID(s) DE created — comma separated"
                        value={tids}
                        onChange={(e) => setTids(e.target.value)}
                        disabled={!row.acknowledged_at}
                      />
                      <Button onClick={sendTids} disabled={busy || !row.acknowledged_at || !tids.trim()}>
                        Mark TIDs sent
                      </Button>
                    </div>
                    {!row.acknowledged_at && (
                      <p className="mt-1.5 text-xs text-ink-muted">
                        Tick the Ack checkbox first — it records who is handling this reject.
                      </p>
                    )}
                    {error && <p className="mt-1.5 text-sm font-semibold text-danger">{error}</p>}
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

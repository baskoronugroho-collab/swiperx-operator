import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { RejectReturn } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "../components/ui";

const TABS = [
  { key: "pending_ack", label: "Not yet acknowledged" },
  { key: "acknowledged", label: "Awaiting TIDs" },
  { key: "tids_sent", label: "Closed" },
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
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

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

  const filtered = useMemo(() => {
    if (!rows) return null;
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((r) =>
      [r.original_awb_id, r.pharmacy_name, r.city ?? "", r.return_tids ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [rows, q]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Reject returns</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Every reject flagged by a courier. Acknowledge it, then record the replacement TIDs
            created on the RTS account <span className="font-mono">{rtsShipper}</span>.
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
          placeholder="Filter AWB, pharmacy, city, TID…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

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
  if (stage === "tids_sent") return <Badge tone="ok">TIDs sent</Badge>;
  if (stage === "acknowledged") return <Badge tone="warn">Awaiting TIDs</Badge>;
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
          <td colSpan={8} className="px-4 py-4">
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
                {row.stage === "tids_sent" ? (
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

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { RejectReturn, ReturnStage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "../components/ui";

/** Lane 3 — the reject-return pipeline (24 Aug rework).
 *
 *      pending_validator → pending_de_upload → pending_print → printed     (sebagian)
 *                        → pending_de_upload → rts_triggered               (semua)
 *
 *  One flat, filterable list with checkbox selection: the toolbar offers exactly the bulk
 *  actions the current tab's stage supports, and the server re-checks stage + role on every
 *  one, so a mis-click can never move a row somewhere its history doesn't support. */

const TABS: { key: string; label: string }[] = [
  { key: "pending_validator", label: "Pending Validator" },
  { key: "pending_de_upload", label: "Pending DE upload" },
  { key: "pending_print", label: "Pending print" },
  { key: "closed", label: "Closed" },
  { key: "", label: "All" },
];
const CLOSED: ReturnStage[] = ["printed", "rts_triggered", "tids_sent"];

export default function RejectReturns() {
  const { has } = useAuth();
  const [tab, setTab] = useState<string>("pending_validator");
  const [rows, setRows] = useState<RejectReturn[] | null>(null);
  const [q, setQ] = useState("");
  const [fType, setFType] = useState("");
  const [fOrigin, setFOrigin] = useState("");
  const [fHub, setFHub] = useState("");
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRows(null);
    setSel(new Set());
    try {
      // Tabs map to derived stages; "closed" is a client-side union of the terminal ones.
      const r = await api.returns.list(tab && tab !== "closed" ? tab : undefined);
      setRows(tab === "closed" ? r.returns.filter((x) => CLOSED.includes(x.stage)) : r.returns);
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
      return [r.original_awb_id, r.return_awb_id ?? "", r.pharmacy_name, r.city ?? "", r.hub_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [rows, q, fType, fOrigin, fHub]);

  const shown = filtered ?? [];
  const selected = shown.filter((r) => sel.has(r.id));
  const pick = (list: RejectReturn[], pred: (r: RejectReturn) => boolean) =>
    (selected.length > 0 ? selected : list).filter(pred).map((r) => r.id);

  async function run(label: string, fn: () => Promise<{ updated: number }>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fn();
      setNotice(`${label}: ${res.updated} row(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn’t save (${err.detail}).` : "Couldn’t save.");
      setBusy(false);
    } finally {
      setBusy(false);
    }
  }

  /* Stage-appropriate bulk actions. Acting on the SELECTION when there is one, otherwise
     on everything shown — matching how "bulk" was asked for on the whiteboard. */
  const canValidate = has("validator", "program_manager");
  const canDe = has("implant", "de");
  const canPrint = has("station_ic", "implant", "de");

  const validateIds = pick(shown, (r) => r.stage === "pending_validator");
  const ocIds = pick(shown, (r) => r.stage === "pending_de_upload" && r.closes_by === "return_oc");
  const rtsIds = pick(shown, (r) => r.stage === "pending_de_upload" && r.closes_by === "rts");
  const printIds = pick(shown, (r) => r.stage === "pending_print");
  const unknownIds = pick(shown, (r) => r.origin_unknown && !CLOSED.includes(r.stage));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Reject returns</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Every reject a courier files, walked through one pipeline: the{" "}
            <strong className="font-semibold text-ink">Validator</strong> checks the photos, then a{" "}
            <strong className="font-semibold text-ink">partial</strong> return gets its{" "}
            <span className="font-mono">-R01</span> return OC exported, uploaded and printed, while a{" "}
            <strong className="font-semibold text-ink">whole-delivery refusal</strong> is bulk-marked{" "}
            <strong className="font-semibold text-ink">RTS</strong> on its original AWB — no new
            tracking number, no print step.
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
          placeholder="Search AWB, pharmacy, city, hub…"
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

      {/* ---- stage toolbar: only the actions this tab's rows can take ---- */}
      {(canValidate || canDe || canPrint) && shown.length > 0 && tab !== "closed" && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
          <span className="text-xs font-semibold uppercase text-ink-muted">
            {selected.length > 0 ? `${selected.length} selected` : "All shown"}
          </span>
          {canValidate && validateIds.length > 0 && (
            <Button disabled={busy} onClick={() => run("Validated", () => api.returns.validate(validateIds))}>
              Validate ({validateIds.length})
            </Button>
          )}
          {canDe && ocIds.length > 0 && (
            <>
              <a href={api.returns.exportOcUrl()}>
                <Button variant="ghost" disabled={busy}>
                  Export return OC (.xlsx)
                </Button>
              </a>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run("Marked uploaded", () => api.returns.markUploaded(ocIds))}
              >
                Mark OC uploaded ({ocIds.length})
              </Button>
            </>
          )}
          {canDe && rtsIds.length > 0 && (
            <>
              <a href={api.returns.exportRtsUrl()}>
                <Button variant="ghost" disabled={busy}>
                  Export RTS list (.csv)
                </Button>
              </a>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run("RTS marked", () => api.returns.markRts(rtsIds))}
              >
                Mark RTS triggered ({rtsIds.length})
              </Button>
            </>
          )}
          {canPrint && printIds.length > 0 && (
            <Button disabled={busy} onClick={() => run("Printed", () => api.returns.markPrinted(printIds))}>
              Mark printed &amp; labelled ({printIds.length})
            </Button>
          )}
          {unknownIds.length > 0 && (
            <span className="ml-auto flex flex-wrap items-center gap-2">
              <Badge tone="warn">{unknownIds.length} origin unknown</Badge>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run("Origin set", () => api.returns.setOrigin(unknownIds, "TMP_DEPOK"))}
              >
                Set Depok
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run("Origin set", () => api.returns.setOrigin(unknownIds, "TMP_SURABAYA"))}
              >
                Set Surabaya
              </Button>
            </span>
          )}
        </div>
      )}

      {notice && (
        <div className="rounded-xl border border-ok/25 bg-ok-soft px-4 py-3 text-sm text-ok">{notice}</div>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      {!filtered && !error && <Spinner label="Loading…" />}
      {filtered && filtered.length === 0 && (
        <EmptyState
          title={q || fType || fOrigin || fHub ? "No matches" : "Nothing here"}
          body={tab === "pending_validator" ? "No rejects waiting for validation." : undefined}
        />
      )}

      {filtered && filtered.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-nv-red"
                      checked={selected.length === shown.length && shown.length > 0}
                      onChange={(e) =>
                        setSel(e.target.checked ? new Set(shown.map((r) => r.id)) : new Set())
                      }
                    />
                  </th>
                  <th className="px-4 py-3">AWB</th>
                  <th className="px-4 py-3">Pharmacy</th>
                  <th className="px-4 py-3">Hub</th>
                  <th className="px-4 py-3">Origin</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3 text-right">Pcs</th>
                  <th className="px-4 py-3">Rejected</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <Row
                    key={r.id}
                    row={r}
                    checked={sel.has(r.id)}
                    onCheck={(v) => {
                      const next = new Set(sel);
                      if (v) next.add(r.id);
                      else next.delete(r.id);
                      setSel(next);
                    }}
                    open={openId === r.id}
                    onToggle={() => setOpenId(openId === r.id ? null : r.id)}
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

function StageBadge({ stage }: { stage: ReturnStage }) {
  if (stage === "printed") return <Badge tone="ok">Printed &amp; labelled</Badge>;
  if (stage === "rts_triggered") return <Badge tone="ok">RTS triggered</Badge>;
  if (stage === "tids_sent") return <Badge tone="ok">Closed (legacy TIDs)</Badge>;
  if (stage === "pending_print") return <Badge tone="warn">Pending print</Badge>;
  if (stage === "pending_de_upload") return <Badge tone="warn">Pending DE upload</Badge>;
  return <Badge tone="danger">Pending Validator</Badge>;
}

function Row({
  row,
  checked,
  onCheck,
  open,
  onToggle,
}: {
  row: RejectReturn;
  checked: boolean;
  onCheck: (v: boolean) => void;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="border-t border-line align-middle hover:bg-canvas-soft/60">
        <td className="px-4 py-3">
          <input
            type="checkbox"
            className="h-4 w-4 accent-nv-red"
            checked={checked}
            onChange={(e) => onCheck(e.target.checked)}
          />
        </td>
        <td className="px-4 py-3">
          <span className="awb-chip">{row.original_awb_id}</span>
          {row.return_awb_id && (
            <span className="mt-1 block font-mono text-[11px] text-ink-muted">→ {row.return_awb_id}</span>
          )}
        </td>
        <td className="px-4 py-3">
          {row.pharmacy_name}
          <span className="block text-xs text-ink-muted">{row.city ?? ""}</span>
        </td>
        <td className="px-4 py-3 font-mono text-xs">{row.hub_name ?? "—"}</td>
        <td className="px-4 py-3">
          {row.origin_unknown ? (
            <Badge tone="warn">unknown</Badge>
          ) : (
            <span className="text-xs">{row.origin === "TMP_SURABAYA" ? "TMP Surabaya" : "TMP Depok"}</span>
          )}
        </td>
        <td className="px-4 py-3">
          <Badge tone={row.return_type === "semua" ? "danger" : "neutral"}>{row.return_type}</Badge>
        </td>
        <td className="px-4 py-3 text-right tabular-nums">{row.reject_pcs ?? "—"}</td>
        <td className="whitespace-nowrap px-4 py-3 text-xs text-ink-muted">{row.rejected_at}</td>
        <td className="px-4 py-3">
          <StageBadge stage={row.stage} />
        </td>
        <td className="px-4 py-3">
          <button onClick={onToggle} className="text-xs font-semibold text-nv-red hover:underline">
            {open ? "Close" : "Detail"}
          </button>
        </td>
      </tr>

      {open && (
        <tr className="border-t border-line bg-canvas-soft/40">
          <td colSpan={10} className="px-4 py-4">
            <div className="flex flex-wrap gap-6">
              {row.proof_photos.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">
                    Door evidence — what the Validator judges
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {row.proof_photos.map((p, i) => (
                      <a key={i} href={p.photo_url} target="_blank" rel="noreferrer">
                        <img
                          src={p.photo_url}
                          alt={p.doc_type}
                          className="h-24 w-24 rounded-lg border border-line object-cover"
                        />
                      </a>
                    ))}
                  </div>
                </div>
              )}
              <div className="min-w-64 text-sm">
                <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">Trail</p>
                <ul className="space-y-1 text-xs text-ink-muted">
                  <li>Rejected {row.rejected_at} — {row.reject_pcs ?? "?"} pcs reported at the door</li>
                  {row.validated_at && (
                    <li>✓ Validated {row.validated_at} by {row.validated_by_email ?? "—"}</li>
                  )}
                  {row.de_uploaded_at && (
                    <li>
                      ✓ Return OC uploaded {row.de_uploaded_at} by {row.de_uploaded_by_email ?? "—"} —{" "}
                      <span className="font-mono">{row.return_awb_id}</span>
                    </li>
                  )}
                  {row.printed_at && (
                    <li>✓ Printed &amp; labelled {row.printed_at} by {row.printed_by_email ?? "—"}</li>
                  )}
                  {row.rts_requested_at && (
                    <li>
                      ✓ RTS triggered on <span className="font-mono">{row.original_awb_id}</span>{" "}
                      {row.rts_requested_at} by {row.rts_requested_by_email ?? "—"}
                    </li>
                  )}
                  {row.return_tids && <li>Legacy TIDs: <span className="font-mono">{row.return_tids}</span></li>}
                </ul>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../lib/api";
import type { VasilList, VasilReason, VasilReturn, VasilView } from "../lib/api";
import ReturnDetail from "../components/ReturnDetail";
import VasilPhotos from "../components/VasilPhotos";
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "../components/ui";

/** Migrate to Vasil Operator — superadmin and KAM tick reject returns off as uploaded to
 *  Vasil Operator. A separate list: nothing here changes a reject return's stage, and
 *  "Delete" only hides the AWB from this page (it stays on Reject returns). */

const TABS: { key: VasilView; label: string }[] = [
  { key: "pending", label: "Pending upload" },
  { key: "done", label: "Done upload" },
  { key: "unable", label: "Unable to upload" },
  { key: "all", label: "All" },
];

const REASON_LABEL: Record<VasilReason, string> = {
  dn: "No proper DN photos",
  item: "No item photos",
  sp_manual: "No SP manual photos",
};
const REASON_KEYS: VasilReason[] = ["dn", "item", "sp_manual"];

const STAGE_LABEL: Record<string, string> = {
  pending_de_upload: "Pending DE upload",
  pending_print: "Pending print",
  printed: "Printed & labelled",
  rts_triggered: "RTS triggered",
  tids_sent: "Closed (legacy TIDs)",
};

export default function VasilMigration() {
  const [tab, setTab] = useState<VasilView>("pending");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [reason, setReason] = useState<VasilReason | "">("");
  const [rows, setRows] = useState<VasilReturn[] | null>(null);
  const [counts, setCounts] = useState<VasilList["reason_counts"] | null>(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  // The reasons dialog: which AWBs, what's ticked, and whether it edits or newly flags.
  const [dialog, setDialog] = useState<{ ids: number[]; picked: Set<VasilReason>; edit: boolean } | null>(null);

  const filters = useMemo(
    () => ({ dateFrom, dateTo, reason: tab === "unable" ? reason : "" }) as const,
    [dateFrom, dateTo, reason, tab],
  );

  const load = useCallback(
    async (silent = false) => {
      if (!silent) {
        setRows(null);
        setSel(new Set());
      }
      try {
        const r = await api.vasil.list(tab, filters);
        setRows(r.returns);
        setCounts(r.reason_counts);
        setError(null);
      } catch (err) {
        setRows([]);
        setError(err instanceof ApiError ? `Couldn’t load (${err.detail}).` : "Couldn’t load.");
      }
    },
    [tab, filters],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!rows) return null;
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((r) =>
      [r.original_awb_id, r.return_awb_id ?? "", r.pharmacy_name, r.city ?? "", r.hub_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [rows, q]);

  const shown = filtered ?? [];
  const selected = shown.filter((r) => sel.has(r.id));

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
    } finally {
      setBusy(false);
    }
  }

  const ids = (pred: (r: VasilReturn) => boolean) => selected.filter(pred).map((r) => r.id);
  const doneIds = (list: VasilReturn[]) => list.filter((r) => r.vasil_status === "pending").map((r) => r.id);
  const backIds = (list: VasilReturn[]) =>
    list.filter((r) => r.vasil_status === "done" || r.vasil_status === "unable").map((r) => r.id);
  const flagIds = (list: VasilReturn[]) =>
    list.filter((r) => r.vasil_status !== "unable").map((r) => r.id);
  const editIds = (list: VasilReturn[]) => list.filter((r) => r.vasil_status === "unable").map((r) => r.id);

  function openDialog(list: number[], edit: boolean, initial: VasilReason[] = []) {
    if (list.length > 0) setDialog({ ids: list, picked: new Set(initial), edit });
  }

  async function saveDialog() {
    if (!dialog || dialog.picked.size === 0) return;
    const reasons = REASON_KEYS.filter((k) => dialog.picked.has(k));
    const { ids: target, edit } = dialog;
    setDialog(null);
    await run(
      edit ? "Reasons updated" : "Marked unable to upload",
      () => (edit ? api.vasil.setReasons(target, reasons) : api.vasil.markUnable(target, reasons)),
    );
  }

  function remove(list: number[]) {
    if (list.length === 0) return;
    if (
      !window.confirm(
        `Remove ${list.length} AWB(s) from this page? They stay on Reject returns — only hidden here.`,
      )
    )
      return;
    void run("Removed from this page", () => api.vasil.hide(list));
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/returns" className="text-xs font-semibold text-ink-muted hover:text-ink">
            ← Reject returns
          </Link>
          <h1 className="mt-1 text-xl font-bold">Migrate to Vasil Operator</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Every reject return, with a checklist for what has been uploaded to Vasil Operator.
            Ticking an AWB here doesn&rsquo;t change anything on Reject returns, and removing one
            only hides it from this page.
          </p>
        </div>
        <a
          href={api.vasil.exportUrl(tab, filters)}
          className="rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-canvas-soft"
        >
          Export CSV ({TABS.find((t) => t.key === tab)?.label})
        </a>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl bg-canvas-soft p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => {
                setNotice(null);
                setTab(t.key);
              }}
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
        <label className="flex items-center gap-2 whitespace-nowrap text-sm text-ink-muted">
          Rejected from
          <input
            type="date"
            className={`${inputClass} w-auto`}
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          to
          <input
            type="date"
            className={`${inputClass} w-auto`}
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </label>
        {(dateFrom || dateTo) && (
          <button
            className="text-xs font-semibold text-nv-red hover:underline"
            onClick={() => {
              setDateFrom("");
              setDateTo("");
            }}
          >
            Clear dates
          </button>
        )}
      </div>

      {tab === "unable" && counts && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase text-ink-muted">Photos to fix</span>
          <button
            onClick={() => setReason("")}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${
              reason === "" ? "border-nv-red text-nv-red" : "border-line text-ink-muted"
            }`}
          >
            All reasons
          </button>
          {REASON_KEYS.map((k) => (
            <button
              key={k}
              onClick={() => setReason(reason === k ? "" : k)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                reason === k ? "border-nv-red text-nv-red" : "border-line text-ink-muted"
              }`}
            >
              {REASON_LABEL[k]} · {counts[k]}
            </button>
          ))}
        </div>
      )}

      {shown.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
          <span className="text-xs font-semibold uppercase text-ink-muted">
            {selected.length > 0 ? `${selected.length} selected` : "Select rows for bulk actions"}
          </span>
          {(tab === "pending" || tab === "all") && (
            <Button
              disabled={busy || doneIds(selected).length === 0}
              onClick={() => run("Marked done", () => api.vasil.markDone(doneIds(selected)))}
            >
              Done upload ({doneIds(selected).length})
            </Button>
          )}
          {tab !== "unable" && (
            <Button
              variant="ghost"
              disabled={busy || flagIds(selected).length === 0}
              onClick={() => openDialog(flagIds(selected), false)}
            >
              Unable to upload ({flagIds(selected).length})
            </Button>
          )}
          {(tab === "unable" || tab === "all") && (
            <Button
              variant="ghost"
              disabled={busy || editIds(selected).length === 0}
              onClick={() => openDialog(editIds(selected), true)}
            >
              Edit reasons ({editIds(selected).length})
            </Button>
          )}
          {tab !== "pending" && (
            <Button
              variant="ghost"
              disabled={busy || backIds(selected).length === 0}
              onClick={() => run("Moved to pending", () => api.vasil.markPending(backIds(selected)))}
            >
              Move to pending ({backIds(selected).length})
            </Button>
          )}
          <Button
            variant="danger"
            disabled={busy || selected.length === 0}
            onClick={() => remove(ids(() => true))}
          >
            Delete ({selected.length})
          </Button>
        </div>
      )}

      {error && <ErrorNote>{error}</ErrorNote>}
      {notice && <p className="text-sm font-semibold text-ok">{notice}</p>}
      {!filtered && !error && <Spinner label="Loading…" />}
      {filtered && filtered.length === 0 && (
        <EmptyState
          title={q ? "No matches" : "Nothing here"}
          body={tab === "pending" && !q ? "Nothing waiting to be uploaded to Vasil Operator." : undefined}
        />
      )}

      {filtered && filtered.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-3 py-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-nv-red"
                      checked={selected.length === shown.length && shown.length > 0}
                      onChange={(e) =>
                        setSel(e.target.checked ? new Set(shown.map((r) => r.id)) : new Set())
                      }
                    />
                  </th>
                  <th className="px-3 py-3">AWB</th>
                  <th className="px-3 py-3">Pharmacy</th>
                  <th className="px-3 py-3">Hub</th>
                  <th className="px-3 py-3">Origin</th>
                  <th className="px-3 py-3">Type</th>
                  <th className="px-3 py-3 text-right">Pcs</th>
                  <th className="px-3 py-3">Rejected</th>
                  <th className="px-3 py-3">Stage</th>
                  <th className="px-3 py-3">Vasil</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <Fragment key={r.id}>
                    <tr className="border-t border-line align-middle hover:bg-canvas-soft/60">
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-nv-red"
                          checked={sel.has(r.id)}
                          onChange={(e) => {
                            const next = new Set(sel);
                            if (e.target.checked) next.add(r.id);
                            else next.delete(r.id);
                            setSel(next);
                          }}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <span className="awb-chip">{r.original_awb_id}</span>
                        {r.po_number && (
                          <span className="mt-1 block break-all font-mono text-[11px] text-ink-muted">
                            PO {r.po_number}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {r.pharmacy_name}
                        <span className="block text-xs text-ink-muted">{r.city ?? ""}</span>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs">{r.hub_name ?? "—"}</td>
                      <td className="px-3 py-3 text-xs">
                        {r.origin === "TMP_SURABAYA" ? "TMP Surabaya" : r.origin ? "TMP Depok" : "—"}
                      </td>
                      <td className="px-3 py-3">
                        <Badge tone={r.return_type === "semua" ? "danger" : "neutral"}>{r.return_type}</Badge>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{r.reject_pcs ?? "—"}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-xs text-ink-muted">{r.rejected_at}</td>
                      <td className="px-3 py-3 text-xs">{STAGE_LABEL[r.stage] ?? r.stage}</td>
                      <td className="px-3 py-3">
                        {r.vasil_status === "done" ? (
                          <Badge tone="ok">Done</Badge>
                        ) : r.vasil_status === "unable" ? (
                          <Badge tone="danger">Unable</Badge>
                        ) : (
                          <Badge tone="warn">Pending</Badge>
                        )}
                        {r.vasil_status === "unable" && (
                          <span className="mt-1 block max-w-44 text-[11px] text-ink-muted">
                            {r.unable_reasons.map((k) => REASON_LABEL[k]).join(", ")}
                          </span>
                        )}
                        {r.vasil_done_at && (
                          <span className="mt-1 block whitespace-nowrap text-[11px] text-ink-muted">
                            {r.vasil_done_at.slice(0, 16)}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex max-w-[15rem] flex-wrap items-center gap-1.5">
                          {r.vasil_status === "pending" ? (
                            <>
                              <Button
                                className="!px-3 !py-1.5 text-xs"
                                disabled={busy}
                                onClick={() => run("Marked done", () => api.vasil.markDone([r.id]))}
                              >
                                Done upload
                              </Button>
                              <Button
                                variant="ghost"
                                className="!px-3 !py-1.5 text-xs"
                                disabled={busy}
                                onClick={() => openDialog([r.id], false)}
                              >
                                Unable
                              </Button>
                            </>
                          ) : (
                            <>
                              {r.vasil_status === "unable" ? (
                                <Button
                                  variant="ghost"
                                  className="!px-3 !py-1.5 text-xs"
                                  disabled={busy}
                                  onClick={() => openDialog([r.id], true, r.unable_reasons)}
                                >
                                  Edit reasons
                                </Button>
                              ) : (
                                <Button
                                  variant="ghost"
                                  className="!px-3 !py-1.5 text-xs"
                                  disabled={busy}
                                  onClick={() => openDialog([r.id], false)}
                                >
                                  Unable
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                className="!px-3 !py-1.5 text-xs"
                                disabled={busy}
                                onClick={() => run("Moved to pending", () => api.vasil.markPending([r.id]))}
                              >
                                Move to pending
                              </Button>
                            </>
                          )}
                          <Button
                            variant="quiet"
                            className="!px-2 !py-1.5 text-xs"
                            disabled={busy}
                            onClick={() => remove([r.id])}
                          >
                            Delete
                          </Button>
                          <button
                            onClick={() => setOpenId(openId === r.id ? null : r.id)}
                            className="px-1 text-xs font-semibold text-nv-red hover:underline"
                          >
                            {openId === r.id ? "Close" : "Detail"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {openId === r.id && (
                      <tr className="border-t border-line bg-canvas-soft/40">
                        <td colSpan={11} className="px-4 py-4">
                          <ReturnDetail row={r} hidePhotos />
                          <VasilPhotos row={r} onChanged={() => void load(true)} />
                          {r.vasil_done_by_email && (
                            <p className="mt-3 text-xs text-ink-muted">
                              Marked done {r.vasil_done_at} by {r.vasil_done_by_email}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {dialog && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-xl">
            <h2 className="text-base font-bold">
              {dialog.edit ? "Edit reasons" : "Unable to upload"} · {dialog.ids.length} AWB
            </h2>
            <p className="mt-1 text-xs text-ink-muted">Which photos need fixing? Pick one or more.</p>
            <div className="mt-3 space-y-2">
              {REASON_KEYS.map((k) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-nv-red"
                    checked={dialog.picked.has(k)}
                    onChange={(e) => {
                      const next = new Set(dialog.picked);
                      if (e.target.checked) next.add(k);
                      else next.delete(k);
                      setDialog({ ...dialog, picked: next });
                    }}
                  />
                  {REASON_LABEL[k]}
                </label>
              ))}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialog(null)}>
                Cancel
              </Button>
              <Button disabled={dialog.picked.size === 0 || busy} onClick={() => void saveDialog()}>
                Save
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

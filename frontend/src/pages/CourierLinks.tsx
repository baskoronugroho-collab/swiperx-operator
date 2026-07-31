import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import type { CourierLink } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "../components/ui";

/** Every courier link created, on screen and copyable — so an operator can find and hand
 *  over a single link without downloading the .csv (guide §5 step 8). */
export default function CourierLinks() {
  const [rows, setRows] = useState<CourierLink[] | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(async (term: string) => {
    setRows(null);
    try {
      const r = await api.oc.links(term || undefined);
      setRows(r.links);
      setError(null);
    } catch {
      setError("Couldn’t load the links.");
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  async function copy(url: string, key: string) {
    await navigator.clipboard.writeText(url);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }

  async function copyAll() {
    if (!rows?.length) return;
    await navigator.clipboard.writeText(
      rows.map((r) => `${r.awb_id}\t${r.pharmacy_name}\t${r.courier_url}`).join("\n"),
    );
    setCopied("__all__");
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Courier links</h1>
          <p className="mt-1 text-sm text-ink-muted">
            One link per AWB. This is the same link injected into the delivery-instruction
            column of the OC upload — couriers open it with no login.
          </p>
        </div>
        <Button variant="ghost" onClick={copyAll} disabled={!rows?.length}>
          {copied === "__all__" ? "Copied" : "Copy all"}
        </Button>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void load(q);
        }}
        className="flex gap-2"
      >
        <input
          className={inputClass}
          placeholder="Search AWB, pharmacy or city…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Button type="submit">Search</Button>
        {q && (
          <Button
            variant="ghost"
            type="button"
            onClick={() => {
              setQ("");
              void load("");
            }}
          >
            Clear
          </Button>
        )}
      </form>

      {error && <ErrorNote>{error}</ErrorNote>}
      {!rows && !error && <Spinner label="Loading…" />}
      {rows && rows.length === 0 && (
        <EmptyState
          title={q ? "No matches" : "No links yet"}
          body={q ? undefined : "Links appear here as soon as you create orders."}
        />
      )}

      {rows && rows.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-3">AWB</th>
                  <th className="px-4 py-3">Pharmacy</th>
                  <th className="px-4 py-3">City</th>
                  <th className="px-4 py-3 text-right">Koli</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Courier link</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.awb_id} className="border-t border-line align-top">
                    <td className="px-4 py-3"><span className="awb-chip">{r.awb_id}</span></td>
                    <td className="px-4 py-3">
                      {r.pharmacy_name}
                      {r.is_return && (
                        <span className="ml-2">
                          <Badge tone="info">Return</Badge>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{r.city ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{r.koli}</td>
                    <td className="px-4 py-3">
                      <Badge tone={r.status === "created" ? "neutral" : "info"}>{r.status}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <code className="awb-chip max-w-72 truncate text-[11px]">{r.courier_url}</code>
                        <Button
                          variant="quiet"
                          className="px-2 py-1 text-xs"
                          onClick={() => copy(r.courier_url, r.awb_id)}
                        >
                          {copied === r.awb_id ? "Copied" : "Copy"}
                        </Button>
                        <a
                          href={r.courier_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-semibold text-nv-red hover:underline"
                        >
                          Open
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

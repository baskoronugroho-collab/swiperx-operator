import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { Hub, HubPatch, Origin } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

/** Superadmin-only hub master (hubs.py). One table feeds two pickers:
 *  - the courier link lists every ACTIVE hub;
 *  - Order Creation lists hubs that are active AND switched on for it.
 *  Changes apply immediately — no deploy. A hub already on an AWB can be deactivated but
 *  not deleted, because the AWB keeps pointing at its name. */

const ERRORS: Record<string, string> = {
  bad_hub_name: "Hub names are 2–32 characters: letters, digits and hyphens (e.g. SUB-GY5).",
  already_exists: "That hub is already on the list.",
  bad_origin: "Pick an origin from the list.",
  hub_in_use: "This hub is on existing AWBs, so it can’t be deleted. Deactivate it instead.",
  not_found: "That hub no longer exists. Reload the page.",
};

function message(err: unknown, fallback: string): string {
  return err instanceof ApiError ? (ERRORS[err.detail] ?? fallback) : fallback;
}

type Filter = "all" | "oc" | "inactive";

export default function Hubs() {
  const [hubs, setHubs] = useState<Hub[] | null>(null);
  const [origins, setOrigins] = useState<Origin[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    try {
      const r = await api.hubs.list();
      setHubs(r.hubs);
      setOrigins(r.origins);
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Only a superadmin can manage hubs."
          : "Couldn’t load the hub list.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Replace one row in place so a toggle doesn't reshuffle or re-fetch ~100 rows.
  const replace = (h: Hub) => setHubs((prev) => prev && prev.map((x) => (x.hub_name === h.hub_name ? h : x)));

  const shown = useMemo(() => {
    const q = query.trim().toUpperCase();
    return (hubs ?? []).filter(
      (h) =>
        (!q || h.hub_name.includes(q)) &&
        (filter === "all" ||
          (filter === "oc" && h.active && h.oc_enabled) ||
          (filter === "inactive" && !h.active)),
    );
  }, [hubs, query, filter]);

  const ocCount = (hubs ?? []).filter((h) => h.active && h.oc_enabled).length;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Hubs</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The hub list behind the Order Creation dropdown and the courier link. Changes apply
          straight away — no deploy needed.
        </p>
      </header>

      <AddHubForm
        origins={origins}
        onDone={(h) => {
          setNotice(
            h.oc_enabled
              ? `${h.hub_name} added. It shows in Order Creation now.`
              : `${h.hub_name} added to the courier list. Switch on “Order Creation” to offer it there too.`,
          );
          void load();
        }}
      />

      {notice && (
        <div className="rounded-xl border border-ok/25 bg-ok-soft px-4 py-3 text-sm text-ok">{notice}</div>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      {!hubs && !error && <Spinner label="Loading…" />}

      {hubs && (
        <Card className="p-0">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
            <input
              className={`${inputClass} max-w-xs`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search hubs (e.g. SUB-)"
              aria-label="Search hubs"
            />
            <div className="flex gap-1.5" role="group" aria-label="Filter hubs">
              {(
                [
                  ["all", `All (${hubs.length})`],
                  ["oc", `In Order Creation (${ocCount})`],
                  ["inactive", `Inactive (${hubs.filter((h) => !h.active).length})`],
                ] as [Filter, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={filter === key}
                  onClick={() => setFilter(key)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                    filter === key ? "border-nv-red bg-nv-red-soft text-nv-red" : "border-line bg-surface text-ink-muted"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {shown.length === 0 ? (
            <div className="p-6">
              <EmptyState title="No hubs match" body="Try a different search or filter." />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                  <tr>
                    <th className="px-4 py-3">Hub</th>
                    <th className="px-4 py-3">Origin (returns fallback)</th>
                    <th className="px-4 py-3">Order Creation</th>
                    <th className="px-4 py-3">Active</th>
                    <th className="px-4 py-3">On AWBs</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {shown.map((h) => (
                    <HubRow
                      key={h.hub_name}
                      hub={h}
                      origins={origins}
                      onSaved={replace}
                      onDeleted={(name) => {
                        setHubs((prev) => prev && prev.filter((x) => x.hub_name !== name));
                        setNotice(`${name} deleted.`);
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function AddHubForm({ origins, onDone }: { origins: Origin[]; onDone: (h: Hub) => void }) {
  const [name, setName] = useState("");
  const [origin, setOrigin] = useState("");
  // Default on: the usual reason to add a hub here is to offer it in Order Creation.
  const [ocEnabled, setOcEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const h = await api.hubs.create({
        hub_name: name.trim().toUpperCase(),
        origin: origin || null,
        active: true,
        oc_enabled: ocEnabled,
      });
      onDone(h);
      setName("");
      setOrigin("");
      setOcEnabled(true);
    } catch (err) {
      setError(message(err, "Couldn’t add the hub. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-bold">Add a hub</h2>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Hub name" hint="As it appears in Ninja Van, e.g. SUB-GY5.">
            <input
              className={`${inputClass} uppercase`}
              value={name}
              onChange={(e) => setName(e.target.value.toUpperCase())}
              placeholder="SUB-GY5"
              maxLength={32}
              required
            />
          </Field>
          <Field label="Origin" hint="Optional. The warehouse returns fall back to.">
            <select className={inputClass} value={origin} onChange={(e) => setOrigin(e.target.value)}>
              <option value="">Not set</option>
              {origins.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={ocEnabled} onChange={(e) => setOcEnabled(e.target.checked)} />
          Show in the Order Creation dropdown
        </label>
        {error && <ErrorNote>{error}</ErrorNote>}
        <Button type="submit" disabled={busy || name.trim().length < 2}>
          {busy ? "Adding…" : "Add hub"}
        </Button>
      </form>
    </Card>
  );
}

function Toggle({
  on,
  disabled,
  label,
  onChange,
}: {
  on: boolean;
  disabled?: boolean;
  label: string;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 rounded-full transition disabled:opacity-50 ${on ? "bg-nv-red" : "bg-line"}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all ${on ? "left-[22px]" : "left-0.5"}`}
      />
    </button>
  );
}

function HubRow({
  hub,
  origins,
  onSaved,
  onDeleted,
}: {
  hub: Hub;
  origins: Origin[];
  onSaved: (h: Hub) => void;
  onDeleted: (name: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(patch: HubPatch) {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api.hubs.update(hub.hub_name, patch));
    } catch (err) {
      setError(message(err, "Couldn’t save."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${hub.hub_name}? It disappears from both pickers. This can't be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.hubs.remove(hub.hub_name);
      onDeleted(hub.hub_name);
    } catch (err) {
      setError(message(err, "Couldn’t delete."));
      setBusy(false);
    }
  }

  return (
    <tr className={`border-t border-line align-top ${hub.active ? "" : "bg-canvas-soft/60"}`}>
      <td className="px-4 py-3">
        <span className="font-mono font-semibold">{hub.hub_name}</span>
        {!hub.active && (
          <span className="ml-2">
            <Badge>Inactive</Badge>
          </span>
        )}
        {error && <p className="mt-1 text-xs font-semibold text-danger">{error}</p>}
      </td>
      <td className="px-4 py-3">
        <select
          className={`${inputClass} py-1.5 text-xs`}
          value={hub.origin ?? ""}
          disabled={busy}
          aria-label={`Origin for ${hub.hub_name}`}
          onChange={(e) => void save({ origin: e.target.value || null })}
        >
          <option value="">Not set</option>
          {origins.map((o) => (
            <option key={o.code} value={o.code}>
              {o.label}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3">
        <Toggle
          on={hub.oc_enabled}
          disabled={busy}
          label={`Show ${hub.hub_name} in Order Creation`}
          onChange={(v) => void save({ oc_enabled: v })}
        />
        {hub.oc_enabled && !hub.active && (
          <p className="mt-1 text-xs text-ink-muted">Hidden while inactive</p>
        )}
      </td>
      <td className="px-4 py-3">
        <Toggle
          on={hub.active}
          disabled={busy}
          label={`${hub.hub_name} active`}
          onChange={(v) => void save({ active: v })}
        />
      </td>
      <td className="px-4 py-3 tabular-nums text-ink-muted">{hub.awb_count.toLocaleString()}</td>
      <td className="px-4 py-3 text-right">
        {hub.awb_count === 0 ? (
          <button
            type="button"
            onClick={remove}
            disabled={busy}
            className="text-xs font-semibold text-danger hover:underline disabled:opacity-50"
          >
            Delete
          </button>
        ) : (
          <span className="text-xs text-ink-muted" title="On existing AWBs — deactivate instead">
            In use
          </span>
        )}
      </td>
    </tr>
  );
}

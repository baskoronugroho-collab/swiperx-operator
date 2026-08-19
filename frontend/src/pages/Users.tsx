import { useCallback, useEffect, useState } from "react";

import { ALL_ROLES, ApiError, api } from "../lib/api";
import type { ManagedUser, Role } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, Button, Card, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

/** What each role actually grants, read off the route guards in App.tsx/Shell.tsx and the
 *  `require_roles(...)` dependencies in the backend — not aspirational. `grants: []` means
 *  the role currently opens nothing beyond being able to sign in; those lanes aren't built
 *  in the v3 cut (SCOPE_V3_MVP.md §4). Superadmin is a wildcard in BOTH layers
 *  (security.require_roles and auth.has), so it passes every check. */
const ROLE_INFO: Record<Role, { label: string; blurb: string; grants: string[] }> = {
  superadmin: {
    label: "Superadmin",
    blurb: "Full access to everything, plus the only role that can manage users.",
    grants: ["Users — register people, assign roles, deactivate", "Every page below"],
  },
  // DE = Data Entry. Implant is part of the DE team, placed at the SwipeRx site — same job,
  // two names, so the two roles are deliberately identical. Either one is fine to assign.
  de: {
    label: "DE",
    blurb: "Data Entry — runs order creation. Same access as Implant.",
    grants: ["Order creation", "Upload history", "Courier links", "Reject returns", "Manual link"],
  },
  implant: {
    label: "Implant",
    blurb: "Part of the DE team, placed at the SwipeRx site. Same access as DE.",
    grants: ["Order creation", "Upload history", "Courier links", "Reject returns", "Manual link"],
  },
  station_ic: {
    label: "Station IC",
    blurb: "Station in-charge: finds a courier's link and handles rejects at the station.",
    grants: ["Courier links", "Reject returns"],
  },
  program_manager: {
    label: "Program Manager",
    blurb: "Oversight of the reject/return loop. No order creation.",
    grants: ["Reject returns"],
  },
  validator: {
    label: "Validator",
    blurb: "Reserved for document validation — that lane is not built yet in this cut.",
    grants: [],
  },
  swiperx: {
    label: "SwipeRx",
    blurb: "Reserved for SwipeRx's own read-only report — not built yet in this cut.",
    grants: [],
  },
};

const ROLE_LABELS: Record<Role, string> = Object.fromEntries(
  (Object.keys(ROLE_INFO) as Role[]).map((r) => [r, ROLE_INFO[r].label]),
) as Record<Role, string>;

/** Superadmin-only: register colleagues by Google email and manage their roles —
 *  including granting superadmin to someone else. Role changes take effect on the
 *  person's NEXT sign-in (roles are baked into the session at mint time). */
export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<ManagedUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers((await api.users.list()).users);
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Only a superadmin can manage users."
          : "Couldn’t load the user list.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Users</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Register colleagues by their Ninja Van Google email and assign roles. A role change
          applies the next time that person signs in.
        </p>
      </header>

      <RegisterForm
        onDone={(email) => {
          setNotice(`${email} registered. They can sign in now.`);
          void load();
        }}
      />

      {notice && (
        <div className="rounded-xl border border-ok/25 bg-ok-soft px-4 py-3 text-sm text-ok">
          {notice}
        </div>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      {!users && !error && <Spinner label="Loading…" />}

      {users && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Roles</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <UserRow key={u.id} user={u} isSelf={u.google_email === me?.email} onChange={load} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <RoleReference />
    </div>
  );
}

/** The assign UI is only usable if you know what you're granting, so the matrix lives
 *  next to it rather than in a document nobody opens. */
function RoleReference() {
  return (
    <Card>
      <h2 className="font-bold">What each role can do</h2>
      <p className="mt-1 text-sm text-ink-muted">
        A person can hold several roles at once — access is the union of them. Changes apply on
        that person&rsquo;s next sign-in.
      </p>
      <div className="mt-4 space-y-3">
        {ALL_ROLES.map((r) => {
          const info = ROLE_INFO[r];
          return (
            <div key={r} className="border-t border-line pt-3 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={r === "superadmin" ? "danger" : "neutral"}>{info.label}</Badge>
                <span className="text-sm text-ink-muted">{info.blurb}</span>
              </div>
              {info.grants.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {info.grants.map((g) => (
                    <span
                      key={g}
                      className="rounded-full border border-line bg-canvas-soft px-2.5 py-0.5 text-xs text-ink-muted"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs italic text-ink-muted">
                  Opens no pages yet — assigning it lets the person sign in and nothing more.
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function RegisterForm({ onDone }: { onDone: (email: string) => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<Role[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.users.register(email.trim(), name.trim(), roles);
      onDone(email.trim());
      setEmail("");
      setName("");
      setRoles([]);
    } catch (err) {
      setError(
        err instanceof ApiError && err.detail === "already_registered"
          ? "That email is already registered."
          : err instanceof ApiError && err.detail === "no_valid_role"
            ? "Pick at least one role."
            : "Couldn’t register. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-bold">Register a user</h2>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Google email">
            <input
              className={inputClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nama@ninjavan.co"
              required
            />
          </Field>
          <Field label="Name">
            <input
              className={inputClass}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              required
            />
          </Field>
        </div>
        <RolePicker value={roles} onChange={setRoles} />
        {error && <ErrorNote>{error}</ErrorNote>}
        <Button type="submit" disabled={busy || roles.length === 0}>
          {busy ? "Registering…" : "Register"}
        </Button>
      </form>
    </Card>
  );
}

function RolePicker({ value, onChange }: { value: Role[]; onChange: (r: Role[]) => void }) {
  return (
    <div>
      <span className="mb-1.5 block text-sm font-semibold">Roles (one or more)</span>
      <div className="flex flex-wrap gap-2">
        {ALL_ROLES.map((r) => {
          const on = value.includes(r);
          return (
            <button
              key={r}
              type="button"
              title={`${ROLE_INFO[r].blurb}${
                ROLE_INFO[r].grants.length ? `\n\nOpens: ${ROLE_INFO[r].grants.join(", ")}` : "\n\nOpens nothing yet."
              }`}
              onClick={() => onChange(on ? value.filter((x) => x !== r) : [...value, r])}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                on ? "border-nv-red bg-nv-red-soft text-nv-red" : "border-line bg-surface text-ink-muted"
              }`}
            >
              {ROLE_LABELS[r]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function UserRow({
  user,
  isSelf,
  onChange,
}: {
  user: ManagedUser;
  isSelf: boolean;
  onChange: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [roles, setRoles] = useState<Role[]>(user.roles);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveRoles() {
    setBusy(true);
    setError(null);
    try {
      await api.users.update(user.id, { roles });
      setEditing(false);
      onChange();
    } catch {
      setError("Couldn’t save.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    setBusy(true);
    try {
      await api.users.update(user.id, { active: !user.active });
      onChange();
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-t border-line align-top">
      <td className="px-4 py-3 font-semibold">
        {user.name}
        {isSelf && <span className="ml-2 text-xs font-normal text-ink-muted">(you)</span>}
      </td>
      <td className="px-4 py-3 text-ink-muted">{user.google_email}</td>
      <td className="px-4 py-3">
        {editing ? (
          <div className="space-y-2">
            <RolePicker value={roles} onChange={setRoles} />
            <div className="flex gap-2">
              <Button className="px-3 py-1.5 text-xs" onClick={saveRoles} disabled={busy || roles.length === 0}>
                Save
              </Button>
              <Button
                variant="quiet"
                className="px-2 py-1 text-xs"
                onClick={() => {
                  setRoles(user.roles);
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
            {error && <p className="text-xs font-semibold text-danger">{error}</p>}
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {user.roles.length ? (
              user.roles.map((r) => (
                <Badge key={r} tone={r === "superadmin" ? "danger" : "neutral"}>
                  {ROLE_LABELS[r]}
                </Badge>
              ))
            ) : (
              <span className="text-xs text-ink-muted">no role</span>
            )}
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        <Badge tone={user.active ? "ok" : "neutral"}>{user.active ? "Active" : "Inactive"}</Badge>
      </td>
      <td className="px-4 py-3">
        {!editing && (
          <div className="flex gap-3 whitespace-nowrap">
            <button
              onClick={() => setEditing(true)}
              className="text-xs font-semibold text-nv-red hover:underline"
            >
              Edit roles
            </button>
            {/* Deactivating yourself would lock the last superadmin out — blocked client-side. */}
            {!isSelf && (
              <button
                onClick={toggleActive}
                disabled={busy}
                className="text-xs font-semibold text-ink-muted hover:text-ink"
              >
                {user.active ? "Deactivate" : "Reactivate"}
              </button>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

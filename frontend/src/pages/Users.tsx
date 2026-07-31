import { useCallback, useEffect, useState } from "react";

import { ALL_ROLES, ApiError, api } from "../lib/api";
import type { ManagedUser, Role } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, Button, Card, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

const ROLE_LABELS: Record<Role, string> = {
  superadmin: "Superadmin",
  program_manager: "Program Manager",
  de: "DE",
  implant: "Implant",
  station_ic: "Station IC",
  validator: "Validator",
  swiperx: "SwipeRx",
};

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
    </div>
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

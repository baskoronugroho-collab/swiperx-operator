import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";
import type { Role } from "../lib/api";

/* PRD FR-OC0 keeps Order creation, Reject OC and Reject returns as separate menus.
   Reject OC is deferred in the v3 cut (SCOPE_V3_MVP.md §4) so it is absent, not merged. */
const NAV: { to: string; label: string; roles: Role[]; end?: boolean }[] = [
  { to: "/orders/new", label: "Order creation", roles: ["implant", "de"] },
  { to: "/links", label: "Courier links", roles: ["implant", "de", "station_ic"] },
  { to: "/orders", label: "Upload history", roles: ["implant", "de"], end: true },
  { to: "/returns", label: "Reject returns", roles: ["implant", "de", "station_ic", "program_manager", "validator"] },
  // Produces a real, working courier link. Started life as the phase-1 field-test tool and
  // still serves that, but it is also the route for a one-off order with no TMP template.
  // Sits last because it is the exception, not the daily flow.
  { to: "/manual", label: "Manual link", roles: ["implant", "de"] },
  // Only superadmin ever holds this role check — the shell filter hides it for everyone else.
  { to: "/users", label: "Users", roles: ["superadmin"] },
];

export default function Shell() {
  const { user, has, logout } = useAuth();
  const navigate = useNavigate();
  const items = NAV.filter((n) => has(...n.roles));

  return (
    <div className="min-h-dvh">
      <div className="brand-hairline" />
      <header className="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="grid h-8 w-8 place-items-center rounded-[10px] bg-nv-red font-display text-sm font-bold text-white">
              S
            </div>
            <div className="leading-tight">
              <div className="font-display text-sm font-bold">SwipeRx Operator</div>
              <div className="text-[11px] text-ink-muted">Alpha 0.1</div>
            </div>
          </div>

          <nav className="hidden items-center gap-1 sm:flex">
            {items.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm font-semibold transition ${
                    isActive ? "bg-nv-red-soft text-nv-red" : "text-ink-muted hover:text-ink"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-xs font-semibold">{user?.name}</div>
              <div className="text-[11px] text-ink-muted">{user?.roles.join(", ") || "no role"}</div>
            </div>
            <button
              onClick={async () => {
                await logout();
                navigate("/signin");
              }}
              className="text-xs font-semibold text-ink-muted hover:text-nv-red"
            >
              Sign out
            </button>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto border-t border-line px-5 py-2 sm:hidden">
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  isActive ? "bg-nv-red-soft text-nv-red" : "text-ink-muted"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-7">
        <Outlet />
      </main>
    </div>
  );
}

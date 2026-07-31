import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api } from "./api";
import type { Role, User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  /** Roles are baked into the session at mint time (backend security.py), so a role
   *  change only takes effect on next sign-in. */
  has: (...roles: Role[]) => boolean;
  refresh: () => Promise<void>;
  devLogin: (email: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await api.auth.me());
    } catch (err) {
      // 401 is the normal signed-out case, not an error worth surfacing.
      if (!(err instanceof ApiError) || err.status !== 401) console.error(err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      has: (...roles) => {
        if (!user) return false;
        if (user.roles.includes("superadmin")) return true;
        return roles.some((r) => user.roles.includes(r));
      },
      refresh,
      devLogin: async (email) => {
        await api.auth.devLogin(email);
        await refresh();
      },
      logout: async () => {
        await api.auth.logout();
        setUser(null);
      },
    }),
    [user, loading, refresh],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

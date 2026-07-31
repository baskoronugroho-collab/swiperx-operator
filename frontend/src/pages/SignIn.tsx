import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button, Card, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

export default function SignIn() {
  const { user, loading, devLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [methods, setMethods] = useState<{ google: boolean; dev_login: boolean } | null>(null);

  useEffect(() => {
    // Ask the deployment what's configured rather than guessing: on this portal
    // GOOGLE_CLIENT_ID is unset, so offering the Google button would dead-end on a 503.
    api
      .version()
      .then((v) => setMethods(v.auth ?? { google: true, dev_login: true }))
      .catch(() => setMethods({ google: true, dev_login: true }));
  }, []);

  if (loading) {
    return (
      <div className="grid h-dvh place-items-center">
        <Spinner label="Loading…" />
      </div>
    );
  }
  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await devLogin(email.trim());
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "That account isn’t registered or is inactive. Ask the Ninja Van team to add it."
          : err instanceof ApiError && err.status === 404
            ? "Dev login is disabled on this environment — use Google sign-in."
            : "Sign-in failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center px-5 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-nv-red text-base font-bold text-white">
            S
          </div>
          <div className="leading-tight">
            <div className="font-bold">SwipeRx Operator</div>
            <div className="text-xs text-ink-muted">Delivery compliance &amp; returns</div>
          </div>
        </div>

        <Card>
          {methods?.google && (
            <a
              href={api.auth.googleLoginUrl()}
              className="flex w-full items-center justify-center rounded-xl bg-nv-red px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-nv-red-dark"
            >
              Sign in with Google Workspace
            </a>
          )}

          {methods?.dev_login !== false && (
            <>
              {methods?.google && (
                <div className="my-5 flex items-center gap-3 text-xs text-ink-muted">
                  <span className="h-px flex-1 bg-line" />
                  dev login (stopgap)
                  <span className="h-px flex-1 bg-line" />
                </div>
              )}

              <form onSubmit={submit} className="space-y-3">
                <Field label="Work email">
                  <input
                    className={inputClass}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                    required
                  />
                </Field>
                {error && <ErrorNote>{error}</ErrorNote>}
                <Button type="submit" disabled={busy} className="w-full">
                  {busy ? "Signing in…" : "Continue"}
                </Button>
              </form>

              <p className="mt-4 text-xs text-ink-muted">
                Your Ninja Van address must already be registered. If it isn’t, ask a
                superadmin to add it under user management.
              </p>
            </>
          )}
        </Card>

        <p className="mt-4 text-center text-xs text-ink-muted">
          Couriers don’t sign in — they open the link sent with the delivery.
        </p>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button, Card, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

/**
 * On a deployed environment this page is unreachable: Substrait's SSO gateway has
 * already signed the user in, so /api/auth/me always resolves and <Protected> never
 * redirects here. It exists for local development, where there is no gateway in front
 * of the app and the dev-login stopgap stands in for it.
 */
export default function SignIn() {
  const { user, loading, devLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [methods, setMethods] = useState<{ sso_proxy: boolean; dev_login: boolean } | null>(
    null,
  );

  useEffect(() => {
    // Ask the deployment how it identifies people rather than guessing.
    api
      .version()
      .then((v) => setMethods(v.auth ?? { sso_proxy: true, dev_login: false }))
      .catch(() => setMethods({ sso_proxy: true, dev_login: false }));
  }, []);

  if (loading || methods === null) {
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
            ? "Dev login is switched off on this environment."
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
          {methods.dev_login ? (
            <>
              <p className="mb-4 text-xs text-ink-muted">
                Local development. On the deployed app you are signed in by Ninja Van
                Single Sign-On before you get here.
              </p>
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
                The address must already be registered under user management.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold">Sign-in is handled by Ninja Van</p>
              <p className="mt-2 text-sm text-ink-muted">
                This app is behind Single Sign-On. Reload the page to be signed in. If you
                keep landing here, your address isn’t allowed to open the app yet — ask the
                Ninja Van team to add it.
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

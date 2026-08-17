"use client";

/**
 * Sign in — locked 49.2, Step 47 §47.1.
 *
 * Only the **password fallback** is offered, because that is the only mechanism
 * the API implements: the OIDC routes need a JWT/JWKS client library (a dependency
 * requiring approval) and the deployment's identity-provider configuration. Locked
 * 47.1.3 makes corporate SSO the *primary* mechanism, so this screen is the
 * fallback and says so rather than presenting itself as the intended route.
 *
 * S-7 — the API returns an identical response for an unknown account, a wrong
 * credential and a disabled account. This screen must not undo that by phrasing
 * them differently, so it renders the server's single message unchanged.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      await refresh();
      router.push("/contracts");
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>LegalMind</h1>
      <p className="hint">
        Password sign-in is a controlled fallback. Corporate single sign-on is the
        primary mechanism where it is configured.
      </p>

      <ErrorBanner error={error} />

      <form onSubmit={submit} className="card">
        <label>
          Work email
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="hint">
        Accounts are created by an administrator. LegalMind does not create an
        account on first sign-in.
      </p>
    </>
  );
}

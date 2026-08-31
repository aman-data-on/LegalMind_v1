"use client";

/**
 * Sign in — locked 49.2, Step 47 §47.1.
 *
 * Only the **password fallback** is offered, because that is the only mechanism
 * the API implements: the OIDC routes need a JWT/JWKS client library (a dependency
 * requiring approval) and the deployment's identity-provider configuration. Locked
 * 47.1.3 makes corporate SSO the *primary* mechanism. The owner's copy directive
 * (DD-3 addendum) removed visible prose about it — the user cannot act on a
 * mechanism the page does not offer. When OIDC ships, it arrives as a real
 * sign-in control, not as prose.
 *
 * S-7 — the API returns an identical response for an unknown account, a wrong
 * credential and a disabled account. This screen must not undo that by phrasing
 * them differently, so it renders the server's single message unchanged, and
 * deliberately does **not** style either field as individually invalid on a
 * failed attempt — that would hand back exactly the per-field disclosure S-7
 * exists to prevent.
 *
 * Visual composition (DD-4, docs/design/DESIGN_DECISIONS.md): owner-supplied
 * deep-navy workspace — floating document geometry behind a centered glass
 * card. The environment is decorative (`aria-hidden`) and non-interactive, so
 * the tab order runs straight into the form. Controls from the source mock
 * that name capabilities the product does not have (SSO button, forgot
 * password, Google account chip, request access) are deliberately absent;
 * adding a dead control would misrepresent the product (rule 4 in spirit) and
 * was explicitly excluded by the owner's earlier brief.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { Field } from "@/components/Primitives";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      await refresh();
      router.push("/workspace");
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div className="login__scene" aria-hidden="true">
        <div className="login__tri login__tri--a" />
        <div className="login__ring" />
        <div className="login__tri login__tri--b" />
        <div className="login__tri login__tri--c" />
        <div className="login__tri login__tri--d" />
        <div className="login__glow" />
      </div>

      <header className="login__top">
        <p className="login__brand">LegalMind</p>
        {/* Placeholder destination — owner-directed (DD-4 addendum); no product
            page exists for it yet. */}
        <p className="login__toplink">
          New here? <a href="#">Learn what LegalMind does</a>
        </p>
      </header>

      <div className="login__main">
        <div className="login__card">
          {/* Owner-directed heading (DD-4 addendum): the mock's tagline replaces
              the plain task heading. */}
          <h1>Smart legal review, built in.</h1>

          <form onSubmit={submit} className="login__form">
            <Field id="login-email" label="Work email">
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                autoFocus
                required
                placeholder="Enter your work email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>

            <Field id="login-password" label="Password">
              <div className="login__pw">
                <input
                  id="login-password"
                  type={reveal ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                {/*
                  Presentation-only visibility toggle. It never touches what is
                  submitted, and the accessible name states the action while the
                  pressed state carries the current condition.
                */}
                <button
                  type="button"
                  className="login__reveal"
                  onClick={() => setReveal((value) => !value)}
                  aria-pressed={reveal}
                  aria-label={reveal ? "Hide password" : "Show password"}
                >
                  {reveal ? "Hide" : "Show"}
                </button>
              </div>
            </Field>

            <ErrorBanner error={error} />

            <button type="submit" className="login__submit" disabled={busy}>
              <span>{busy ? "Signing in…" : "Sign in"}</span>
              {busy ? <span className="login__spinner" aria-hidden="true" /> : null}
            </button>

            {/*
              A label change alone is not reliably announced; this mirrors the
              `role="status" aria-live="polite"` pattern the design system
              documents for busy states.
            */}
            <span className="visually-hidden" role="status" aria-live="polite">
              {busy ? "Signing in…" : ""}
            </span>
          </form>

          {/*
            Google sign-in — owner-directed placeholder (DD-4 addendum). It links
            to the locked 49.2 OIDC entry route (`GET /api/v1/auth/oidc/start` →
            redirect to the identity provider), which the backend does not
            implement yet. Deliberately an <a>, not a fetch: the OIDC flow is a
            top-level navigation, so when the backend ships this control starts
            working with no frontend change. Generic wording — the page cannot
            know who the user is before they authenticate.
          */}
          <a className="login__google" href="/api/v1/auth/oidc/start">
            <span className="login__google-mark" aria-hidden="true">
              G
            </span>
            Sign in with Google
          </a>

          {/* Placeholder destination — owner-directed (DD-4 addendum). */}
          <p className="login__alt">
            Not a customer yet? <a href="#">Request access</a>
          </p>

          {/* The one recovery path on a page with no signup or reset flow —
              placed as the card's small print, per the owner's reference. */}
          <p className="login__note">Accounts are created by an administrator.</p>
        </div>
      </div>
    </div>
  );
}

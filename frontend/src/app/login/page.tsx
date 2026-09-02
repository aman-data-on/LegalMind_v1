"use client";

/**
 * Sign in — locked 49.2, Step 47 §47.1.
 *
 * Both locked mechanisms are now offered. Locked 47.1.3 makes corporate SSO via
 * OIDC the *primary* mechanism and password login "a controlled fallback"; the
 * backend registered the two OIDC routes on 2026-09-01, so the Google control
 * below is a live sign-in path rather than the placeholder it was.
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
import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { Field } from "@/components/Primitives";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { type SsoOutcome, ssoNotice, ssoOutcomeOf } from "@/lib/sso";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [ssoOutcome, setSsoOutcome] = useState<SsoOutcome | null>(null);

  /*
   * The SSO result arrives as a query value because the callback is a top-level
   * navigation, not a fetch. Read after mount from `window.location` rather than
   * with `useSearchParams`, which would force this route into a Suspense boundary
   * for no benefit — the value is only ever present on a redirect-in.
   *
   * The S-7 reasoning and the copy itself live in `@/lib/sso` — one outcome for
   * every cause, and an unrecognised value renders nothing.
   */
  useEffect(() => {
    setSsoOutcome(
      ssoOutcomeOf(new URLSearchParams(window.location.search).get("sso")),
    );
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      await refresh();
      router.push("/dashboard");
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
            Corporate SSO — the locked 49.2 entry route
            (`GET /api/v1/auth/oidc/start` → redirect to the identity provider).
            Deliberately an <a>, not a fetch: OIDC is a top-level navigation, and
            an XHR cannot follow a cross-origin consent redirect.

            Generic wording, and generic on purpose — the page cannot know who the
            user is before they authenticate, so it never names an account or a
            domain. The mark is decorative and hidden from assistive technology;
            the accessible name comes from the visible label.
          */}
          {ssoOutcome ? (
            <p className="login__sso-alert" role="alert">
              {ssoNotice(ssoOutcome)}
            </p>
          ) : null}

          <a className="login__google" href="/api/v1/auth/oidc/start">
            <svg
              className="login__google-mark"
              viewBox="0 0 18 18"
              width="18"
              height="18"
              aria-hidden="true"
              focusable="false"
            >
              <path
                fill="#4285F4"
                d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62Z"
              />
              <path
                fill="#34A853"
                d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.34A9 9 0 0 0 9 18Z"
              />
              <path
                fill="#FBBC05"
                d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.94H.96a9 9 0 0 0 0 8.12l3.01-2.34Z"
              />
              <path
                fill="#EA4335"
                d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.94l3.01 2.34C4.68 5.16 6.66 3.58 9 3.58Z"
              />
            </svg>
            Continue with Google
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

/**
 * The corporate-SSO outcome carried back on the sign-in redirect — S-7.
 *
 * A separate module for one reason: this is the whole of the presentation policy
 * for SSO failure, and it is testable without rendering. Locked S-7 gives the API
 * ONE indistinguishable outcome for every cause that could disclose account state
 * — an account bound elsewhere, a disabled account, an unverified email, a
 * replayed state, a provider error — so `failed` must have exactly one sentence
 * and must name no cause. Keeping the mapping here, rather than inline in the
 * page, is what lets a test assert that.
 *
 * Two outcomes are safe to distinguish, and both are argued at the callback in
 * `backend/legalmind/api/routers/auth.py`:
 *
 * - `unavailable` — the deployment has no identity provider configured. Says
 *   nothing about any account.
 * - `domain` — the address is outside the permitted corporate domain. The check
 *   runs before any database lookup, and the permitted domain is already public in
 *   the authorization request's `hd` parameter, so naming it costs nothing.
 *
 * A fourth outcome is a security decision, not a copy change: every additional
 * value is another bit readable off the login screen.
 */

export type SsoOutcome = "failed" | "unavailable" | "domain";

const NOTICES: Record<SsoOutcome, string> = {
  // Deliberately says only that it did not complete, and points at the fallback
  // locked 47.1.3 keeps available. Not styled or worded as the user's mistake:
  // the most common cause by far is closing the Google consent screen.
  failed:
    "Sign-in with Google did not complete. Try again, or sign in with your work email.",
  unavailable:
    "Sign-in with Google is unavailable. Sign in with your work email.",
  // Names the requirement, never the address that failed it — echoing user input
  // into the page is how a redirect parameter becomes a phishing surface.
  domain:
    "Use your Leapswitch work account. Personal Google accounts cannot sign in here.",
};

/** Narrow an untrusted query value. Anything unrecognised renders nothing at all
 *  — the value arrives from the URL bar and is never echoed. */
export function ssoOutcomeOf(value: string | null): SsoOutcome | null {
  return value === "failed" || value === "unavailable" || value === "domain"
    ? value
    : null;
}

export function ssoNotice(outcome: SsoOutcome | null): string | null {
  return outcome ? NOTICES[outcome] : null;
}

/**
 * The sign-in screen's corporate-SSO control — locked 47.1.3 (OD-9), S-7.
 *
 * Two properties are worth a test rather than a comment.
 *
 * **The SSO control is a navigation, not a fetch.** OIDC is a top-level redirect
 * to the identity provider; an XHR cannot follow a cross-origin consent flow. If
 * someone "improves" this into a button with an onClick handler, sign-in breaks in
 * a way that only shows up against a real IdP — so the anchor and its href are
 * pinned here.
 *
 * **S-7 survives the presentation layer.** The API returns ONE outcome for every
 * SSO failure (unknown account, disabled account, wrong email domain, unverified
 * email, replayed state, provider error). A screen that phrased them differently
 * would rebuild the account-enumeration oracle the backend refuses to be.
 *
 * Rendered with `renderToStaticMarkup`, like every other suite here — this project
 * has no DOM testing library and adding one is a rule 19 dependency decision. The
 * failure copy is therefore asserted through `@/lib/sso`, which is exactly why
 * that mapping is a separate pure module.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ssoNotice, ssoOutcomeOf } from "@/lib/sso";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/session", () => ({ useSession: () => ({ refresh: vi.fn() }) }));

async function markup(): Promise<string> {
  const { default: LoginPage } = await import("@/app/login/page");
  return renderToStaticMarkup(<LoginPage />);
}

describe("47.1.3 — corporate SSO is offered as a real control", () => {
  it("points at the locked 49.2 entry route", async () => {
    expect(await markup()).toContain('href="/api/v1/auth/oidc/start"');
  });

  it("is an anchor, because the flow leaves the origin", async () => {
    const html = await markup();
    // The <a> carrying the SSO href — a <button> here could not follow a
    // cross-origin consent redirect.
    expect(html).toMatch(/<a[^>]+href="\/api\/v1\/auth\/oidc\/start"/);
  });

  it("labels the control and hides the mark from assistive technology", async () => {
    const html = await markup();
    expect(html).toContain("Continue with Google");
    expect(html).toMatch(/<svg[^>]+aria-hidden="true"/);
  });

  it("shows no SSO notice on a plain page load", async () => {
    expect(await markup()).not.toContain('role="alert"');
  });
});

describe("S-7 — one SSO failure message, naming no cause", () => {
  it("announces the failure and offers the locked fallback", () => {
    const notice = ssoNotice("failed")!;
    expect(notice).toMatch(/did not complete/i);
    expect(notice).toMatch(/work email/i);
  });

  it("never hints at why", () => {
    const notice = ssoNotice("failed")!.toLowerCase();
    // Each of these would answer a question the backend deliberately refuses to
    // answer: whether the account exists, whether it is disabled, whether the
    // address is inside the permitted domain.
    for (const leak of ["account", "not found", "unknown", "disabled", "domain",
                        "permission", "verified", "expired", "invalid"]) {
      expect(notice).not.toContain(leak);
    }
  });

  it("distinguishes an unconfigured deployment, which discloses no account state", () => {
    expect(ssoNotice("unavailable")).toMatch(/unavailable/i);
  });

  it("renders nothing for an unrecognised or hostile query value", () => {
    for (const hostile of ["<script>alert(1)</script>", "FAILED", "", null,
                            "unauthorized", "DOMAIN"]) {
      expect(ssoOutcomeOf(hostile)).toBeNull();
      expect(ssoNotice(ssoOutcomeOf(hostile))).toBeNull();
    }
  });
});

describe("the corporate-domain refusal is the one safe exception", () => {
  it("tells the user what is required", () => {
    const notice = ssoNotice("domain")!;
    expect(notice).toMatch(/work account/i);
    expect(notice).toMatch(/personal google/i);
  });

  it("never echoes an address back into the page", () => {
    // The address came from a redirect parameter. Echoing user input into the
    // login screen is how this becomes a phishing surface.
    expect(ssoNotice("domain")).not.toMatch(/@/);
  });

  it("stays a closed set — a fourth outcome is a security decision", () => {
    // If this fails because an outcome was added, argue it at the callback in
    // routers/auth.py first: every extra value is another bit an attacker can
    // read off the login screen.
    const recognised = ["failed", "unavailable", "domain"]
      .map(ssoOutcomeOf).filter(Boolean);
    expect(recognised).toHaveLength(3);
    for (const other of ["expired", "denied", "no_account", "disabled",
                          "not_found", "forbidden"]) {
      expect(ssoOutcomeOf(other)).toBeNull();
    }
  });
});

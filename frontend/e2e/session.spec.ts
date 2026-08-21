import { expect, test } from "@playwright/test";

import { CSRF_COOKIE, SESSION_COOKIE, csrfToken, fixture } from "./support";

/**
 * The session cookie — locked S-3, SEC-01, 47.1.1.
 *
 * **This is the file that justifies having a browser at all.** S-3 requires the session
 * cookie to be `HttpOnly`, and no test outside a real browser can prove it: `HttpOnly`
 * is not a server behaviour, it is a browser behaviour. A `TestClient` sees the
 * attribute in a header and reads the value anyway. Only a browser enforces the thing
 * the attribute asks for — that script cannot reach the value.
 *
 * These specs drive the login form themselves rather than reusing a stored session,
 * because the login and logout flow is what they test. That is three logins; S-5's
 * limiter allows ten per 300s, so the suite stays inside the locked control rather than
 * relaxing it.
 */

test.describe("S-3 — the session cookie is not reachable from script", () => {
  test.beforeEach(async ({ page }) => {
    const account = fixture().accounts.owner;
    await page.goto("/login");
    await page.getByLabel("Work email").fill(account.email);
    await page.getByLabel("Password").fill(account.password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/contracts/, { timeout: 20_000 });
  });

  test("document.cookie exposes the CSRF token and never the session", async ({
    page,
  }) => {
    const visibleToScript = await page.evaluate(() => document.cookie);

    // The double-submit pair, and which half script may see. The CSRF cookie is
    // deliberately readable — the application's own fetch wrapper reads it — while the
    // session cookie is the half an XSS must not be able to exfiltrate.
    expect(visibleToScript).toContain(CSRF_COOKIE);
    expect(visibleToScript).not.toContain(SESSION_COOKIE);

    // And the browser does hold it: absent from script, present on the wire.
    const session = (await page.context().cookies()).find(
      (c) => c.name === SESSION_COOKIE,
    );
    expect(session, "the session cookie should exist in the jar").toBeTruthy();
    expect(session!.httpOnly).toBe(true);
    expect(session!.sameSite).toBe("Strict");
    // Secure is set even here. The harness runs on http://localhost, which browsers
    // treat as a trustworthy origin, so the attribute is honoured rather than weakened
    // for the tests — the same reason the pytest harness uses https://testserver.
    expect(session!.secure).toBe(true);
  });

  test("a request with the session cookie but no CSRF header is refused", async ({
    page,
  }) => {
    // The session cookie travels automatically — which is exactly why S-3 needs a
    // second factor. Omitting the header must fail even though the caller is
    // authenticated, or the cookie alone would authorize a cross-site write.
    const response = await page.request.post("/api/v1/contracts", {
      headers: { "Content-Type": "application/json" },
      data: { name: "CSRF probe" },
    });

    expect(response.status()).toBe(403);
    expect((await response.json()).error.code).toBe("CSRF_TOKEN_INVALID");
  });

  test("signing out leaves no usable session in the browser", async ({ page }) => {
    const token = await csrfToken(page);
    const loggedOut = await page.request.post("/api/v1/auth/logout", {
      headers: { "X-CSRF-Token": token },
    });
    expect(loggedOut.ok()).toBeTruthy();

    // 47.1.1 r2 — a request after logout is indistinguishable from never having signed
    // in. Checked through the browser's own jar, so a cookie the server failed to clear
    // would be caught rather than assumed cleared.
    const after = await page.request.get("/api/v1/auth/session");
    expect(after.status()).toBe(401);
  });
});

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { expect, test as setup } from "@playwright/test";

import { SNAPSHOT_PATH, fixture, signIn, storageStatePath } from "./support";

/**
 * One-time setup: sign in once per account, and publish the configuration once.
 *
 * Both halves exist because the locked design pushed back on the first draft of this
 * suite, and the harness was wrong rather than the product:
 *
 * 1. **Authoring configuration is a `LEGAL_ADMIN` act.** `configuration.draft` and
 *    `configuration.publish` belong to `LEGAL_ADMIN` under Step 23; `USER` and
 *    `LEGAL_REVIEWER` hold neither. Every spec initially tried to publish as itself
 *    and was correctly refused with 403. Publishing is also **global** (Step 29
 *    activates Requirements and pins the latest version of every ACTIVE one), so doing
 *    it once as `admin` is both the authorized path and the only coherent one.
 *
 * 2. **Signing in repeatedly hits S-5.** The login limiter allows 10 attempts per
 *    300s per client address, and seventeen specs signing in from one address exhausted
 *    it — the control working exactly as locked. Sessions are therefore established
 *    once here and reused via `storageState`, so the suite performs three logins
 *    instead of seventeen. (`session.spec.ts` still drives the form itself, because the
 *    login and logout flow is what it tests.)
 *
 * The limiter is left **enabled** throughout; the e2e API only raises the configurable
 * threshold, which locked 49.10 and `ratelimit.py` both call deployment configuration
 * rather than a specified control level. Nothing here disables a control or weakens a
 * cookie attribute.
 */

const ACCOUNTS = ["admin", "owner", "counsel"] as const;

for (const label of ACCOUNTS) {
  setup(`sign in as ${label}`, async ({ page }) => {
    const account = fixture().accounts[label];

    await signIn(page, account);

    const path = storageStatePath(label);
    mkdirSync(dirname(path), { recursive: true });
    await page.context().storageState({ path });
  });
}

setup("publish the STRUCTURAL configuration", async ({ browser }) => {
  const f = fixture();
  const context = await browser.newContext({
    storageState: storageStatePath("admin"),
  });
  const page = await context.newPage();
  // `page.request` shares the context's cookies, so the session and CSRF pair are the
  // real ones rather than synthesized headers.
  const csrf = decodeURIComponent(
    (await context.cookies()).find((c) => c.name === "legalmind_csrf")!.value,
  );
  const headers = { "Content-Type": "application/json", "X-CSRF-Token": csrf };

  const listed = await page.request.get("/api/v1/requirements");
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const code = f.configuration.requirement_code;
  const exists = ((await listed.json()).data ?? []).some(
    (r: { code: string }) => r.code === code,
  );

  if (!exists) {
    const created = await page.request.post("/api/v1/requirements", {
      headers,
      data: { code },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const requirement = (await created.json()).data;

    const versioned = await page.request.post(
      `/api/v1/requirements/${requirement.id}/versions`,
      {
        headers,
        data: {
          name: f.configuration.name,
          description: f.configuration.description,
          evaluator_type: f.configuration.evaluator_type,
          company_standard: f.configuration.company_standard,
          mapping_rules: f.configuration.mapping_rules,
          evaluation_rules: f.configuration.evaluation_rules,
          legal_rule: f.configuration.legal_rule,
        },
      },
    );
    expect(versioned.ok(), await versioned.text()).toBeTruthy();
  }

  const published = await page.request.post("/api/v1/configuration/publish", {
    headers,
    data: { requirement_codes: [code] },
  });
  // D-1 — a publish is refused outright if mapping rules omit `confirm_threshold`.
  // If this fails, the fixture is incomplete rather than the endpoint being broken.
  expect(published.ok(), await published.text()).toBeTruthy();
  const snapshot = (await published.json()).data;

  writeFileSync(
    join(__dirname, SNAPSHOT_PATH),
    JSON.stringify({ configuration_snapshot_id: snapshot.id }, null, 2),
  );
  await context.close();
});

import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { APIResponse, Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Shared scaffolding for the browser suite.
 *
 * Two rules shape everything here:
 *
 * 1. **Nothing writes to the database.** Fixtures are built through the real
 *    endpoints, so if an endpoint would refuse the setup, the suite finds out. The one
 *    exception is the account bootstrap, which locked 47.1.3 r3 puts outside the API
 *    on purpose — see `backend/tools/e2e_bootstrap.py`.
 * 2. **No locked control is weakened to make the harness work.** Where the locked
 *    design refused an earlier draft of this suite, the suite changed: configuration is
 *    published by `LEGAL_ADMIN` (Step 23) and sessions are reused rather than
 *    re-established (S-5). See `auth.setup.ts`.
 *
 * Every configured value in the fixture is `STRUCTURAL` and carries no legal meaning
 * (rule 21); the bootstrap that emits it says so, and so does its `provenance` field.
 */

export const FIXTURE_PATH = join(__dirname, ".fixture.json");
export const SNAPSHOT_PATH = ".fixture-snapshot.json";
export const CSRF_COOKIE = "legalmind_csrf";
export const SESSION_COOKIE = "legalmind_session";

export type AccountLabel = "admin" | "owner" | "counsel";

export interface Fixture {
  database_url: string;
  provenance: string;
  accounts: Record<
    AccountLabel,
    { email: string; password: string; user_id: string; roles: string[] }
  >;
  document: { path: string; filename: string; mime: string; paragraphs: string[] };
  configuration: {
    requirement_code: string;
    name: string;
    description: string;
    evaluator_type: string;
    company_standard: Record<string, unknown>;
    mapping_rules: Record<string, unknown>;
    evaluation_rules: Record<string, unknown>;
    legal_rule: { rule_type: string; configuration: Record<string, unknown> };
  };
}

export function fixture(): Fixture {
  return JSON.parse(readFileSync(FIXTURE_PATH, "utf8")) as Fixture;
}

export function storageStatePath(label: AccountLabel): string {
  return join(__dirname, ".auth", `${label}.json`);
}

export function snapshotId(): string {
  const raw = JSON.parse(readFileSync(join(__dirname, SNAPSHOT_PATH), "utf8"));
  return raw.configuration_snapshot_id as string;
}

/**
 * The CSRF token, read the way the application's own script reads it.
 *
 * S-3's double-submit pair: the session cookie is `HttpOnly` and travels
 * automatically, and this is the half a cross-origin caller cannot forge. Read from
 * the cookie jar rather than hard-coded, so a spec cannot pass while the mechanism is
 * broken.
 */
export async function csrfToken(page: Page): Promise<string> {
  const cookie = (await page.context().cookies()).find((c) => c.name === CSRF_COOKIE);
  if (!cookie) throw new Error("no CSRF cookie — is the session established?");
  return decodeURIComponent(cookie.value);
}

/** POST through the browser context, so the real cookies and CSRF header apply. */
export async function apiPost(
  page: Page,
  path: string,
  body?: unknown,
): Promise<APIResponse> {
  return page.request.post(`/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await csrfToken(page),
    },
    ...(body === undefined ? {} : { data: body as Record<string, unknown> }),
  });
}

async function postOk(page: Page, path: string, body?: unknown): Promise<any> {
  const response = await apiPost(page, path, body);
  expect(
    response.ok(),
    `POST ${path} failed: ${response.status()} ${await response.text()}`,
  ).toBeTruthy();
  return (await response.json()).data;
}

/**
 * Build one Review from the STRUCTURAL fixture: contract → upload → Review → analysis.
 *
 * The upload sends the file as the raw body with `X-Filename`, which is the shape the
 * endpoint takes (38.24) — chosen there to keep a multipart parser off the path that
 * handles untrusted input (34.16).
 *
 * Analysis runs inline in this configuration (no broker), so the response already
 * carries the outcome; see `playwright.config.ts`.
 */
export async function createAnalysedReview(
  page: Page,
  { analyse = true }: { analyse?: boolean } = {},
): Promise<{ reviewId: string }> {
  const f = fixture();

  const contract = await postOk(page, "/contracts", {
    name: `Structural MSA ${Date.now()}`,
    // Step 6 / owner Q9: the uploader declares the Document Type; analysis
    // refuses an undeclared one rather than evaluating everything.
    contract_type: "MSA",
  });

  const upload = await page.request.post(
    `/api/v1/contracts/${contract.id}/document-versions`,
    {
      headers: {
        "Content-Type": f.document.mime,
        "X-Filename": f.document.filename,
        "X-CSRF-Token": await csrfToken(page),
      },
      data: readFileSync(f.document.path),
    },
  );
  expect(
    upload.ok(),
    `upload failed: ${upload.status()} ${await upload.text()}`,
  ).toBeTruthy();
  const uploaded = (await upload.json()).data;

  const review = await postOk(page, "/reviews", {
    document_version_id: uploaded.document_version.id,
    configuration_snapshot_id: snapshotId(),
  });

  if (analyse) await postOk(page, `/reviews/${review.id}/analyze`);
  return { reviewId: review.id };
}

/** The Evaluation ids on a Review, read through the API the browser uses. */
export async function evaluationIds(page: Page, reviewId: string): Promise<string[]> {
  const response = await page.request.get(`/api/v1/reviews/${reviewId}/findings`);
  expect(response.ok(), await response.text()).toBeTruthy();
  const findings = (await response.json()).data;
  return findings.flatMap((finding: any) =>
    finding.evaluations.map((e: any) => e.id),
  );
}

/**
 * Drive the real login form. The single owner of the login-page selector
 * strategy: `exact` on the password label because the screen also has a
 * "Show password" reveal control (DD-4) that substring matching would catch.
 */
export async function signIn(
  page: import("@playwright/test").Page,
  account: { email: string; password: string },
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Work email").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/contracts/, { timeout: 20_000 });
}

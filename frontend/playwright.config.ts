import { defineConfig, devices } from "@playwright/test";

/**
 * Browser-workflow tests — locked Step 39's stack table (`Pytest + Playwright`,
 * "backend/domain + **real browser workflow testing**").
 *
 * --------------------------------------------------------------------------
 * What this suite is, and is not
 * --------------------------------------------------------------------------
 * Locked 54.1's six tiers contain **no browser tier**, and 54.7's release gate does
 * not list one. This suite is therefore **supporting**, not a locked tier and not a
 * release gate. It exists for the small number of locked properties that cannot be
 * proved anywhere else:
 *
 *   S-3       the session cookie is unreadable from JavaScript
 *   LEGAL-02  confidential fields are absent from what reaches the *page*
 *   52.7      no optimistic UI — rendered state is re-read from the server
 *   52.3+47.6 a hidden control AND an endpoint that refuses it anyway
 *
 * It deliberately does not restate what the 468 backend and 53 frontend tests cover.
 * Duplicating them here would buy nothing and cost minutes per run.
 *
 * --------------------------------------------------------------------------
 * Why plain http://localhost is correct here
 * --------------------------------------------------------------------------
 * The session cookie is `Secure; SameSite=Strict; HttpOnly` (S-3). Browsers treat
 * `localhost` as a trustworthy origin, so a `Secure` cookie is stored and sent over
 * http — verified empirically before this file was written, not assumed. **No locked
 * cookie attribute is weakened for the harness**, which is the same rule the pytest
 * harness follows by using `https://testserver`.
 *
 * Requests go to the Next server, which proxies `/api/v1/*` to the API exactly as
 * production's single origin does (see `next.config.ts`). So the suite exercises the
 * real same-origin path rather than a CORS arrangement that production never uses.
 *
 * Analysis runs **inline** here: no `LEGALMIND_BROKER_URL` is set, so the suite needs
 * no Redis. The queued path is covered by `backend/tests/test_worker.py` and by the
 * poll-rule tests in `src/__tests__/analysis-queue.test.ts`.
 */

const E2E_DATABASE_URL =
  process.env.LEGALMIND_E2E_DATABASE_URL ??
  "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_e2e";

const API_PORT = process.env.LEGALMIND_E2E_API_PORT ?? "8099";
const WEB_PORT = process.env.LEGALMIND_E2E_WEB_PORT ?? "3099";

/** Handed to both servers so the API and the browser agree on one environment. */
const backendEnv = {
  LEGALMIND_ENVIRONMENT: "development",
  LEGALMIND_DATABASE_URL: E2E_DATABASE_URL,
  LEGALMIND_STORAGE_ROOT: "../backend/.e2e/objects",
  // Quiet by default so a suite run is readable; raise it to collect a real log
  // corpus for the 53.3 redaction check (`docs/08-testing/INDEPENDENT_VERIFICATION.md`).
  LEGALMIND_LOG_LEVEL: process.env.LEGALMIND_LOG_LEVEL ?? "WARNING",
  // S-5's login limiter stays ENABLED; only its threshold is raised. Locked 49.10 and
  // `ratelimit.py` both state that thresholds are deployment configuration and "not a
  // specified control level", so this is a deployment value, not a weakened control —
  // unlike a cookie attribute, which the harness never touches. The suite still keeps
  // logins to three by reusing sessions (see `auth.setup.ts`); this only stops repeated
  // local runs within one 300-second window from failing on the previous run's attempts.
  LEGALMIND_RATELIMIT_LOGIN_MAX: "200",
};

export default defineConfig({
  testDir: "./e2e",
  // Serial. Every spec builds its own contract and Review through the API, but they
  // share one database and one configuration namespace; publishing a snapshot is a
  // global act (Step 29 activates Requirements), so concurrent publishes would race
  // over what "the latest ACTIVE configuration" means. Correctness over minutes.
  workers: 1,
  fullyParallel: false,
  // A flaky legal-system test is a defect to fix, not to paper over.
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",

  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    // Establishes the three sessions and publishes the configuration once. Every
    // other project depends on it, so the ordering is declared rather than implied by
    // filenames.
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],

  webServer: [
    {
      command: `python3 -m uvicorn legalmind.api.app:app --port ${API_PORT}`,
      cwd: "../backend",
      // `/health` is the one route unauthenticated by design (app.py), which is why
      // it is usable as a readiness probe here.
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      env: backendEnv,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // A production build, not `next dev`, for two reasons. It is what locked 55.1
      // actually deploys, so the suite exercises the same rendering path; and Next
      // refuses to start a second dev server in one directory, which made the suite
      // fail against a developer's own running server rather than against the code.
      command: `npx next build && npx next start --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { LEGALMIND_API_ORIGIN: `http://127.0.0.1:${API_PORT}` },
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});

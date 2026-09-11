import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, showDocument, storageStatePath } from "./support";

/**
 * Design QA — visual regression baselines (Phase 4/7 hardening, 2026-08-27).
 *
 * Runs ONLY under `npm run design-qa` (DESIGN_QA=1). Deliberately not part of the
 * default e2e run: the default suite's specs create data in a shared database, so
 * a screenshot's row counts would depend on spec ordering and grow with the
 * suite. Under design-qa the database is freshly bootstrapped and only this file
 * runs, so every page below renders exactly the same content every time.
 *
 * Threshold: 0.1% of pixels (maxDiffPixelRatio 0.001). Volatile content — ids in
 * headings, snapshot ids, dates — is masked rather than excluded, so a layout
 * regression under a mask's neighborhood still fails.
 *
 * Baselines are Linux/Chromium renderings FROM THIS REPO'S CI RUNNER — never from
 * a developer machine. A dev box renders fonts ~1% differently and, with the
 * embedding model present, renders a different Ask-panel index state (the page
 * height changes), so locally generated baselines fail CI every time (2026-08-30:
 * this happened twice in one afternoon). To regenerate: let job 15 fail, download
 * its `visual-regression-diffs` artifact, commit the `*-actual.png` files as the
 * new baselines, and review the image diff like any other diff.
 *
 * The guard below makes the rule mechanical: outside CI, this spec refuses both
 * `--update-snapshots` and a missing baseline (which Playwright would silently
 * write). Set `ALLOW_LOCAL_BASELINES=1` only to inspect diffs locally, never to
 * commit what it writes.
 */

test.beforeEach(({}, testInfo) => {
  if (process.env.CI || process.env.ALLOW_LOCAL_BASELINES) return;
  const mode = testInfo.config.updateSnapshots;
  if (mode === "all" || mode === "changed") {
    throw new Error(
      "visual baselines are generated in CI, never locally — do not run " +
        "--update-snapshots on a developer machine (see the header comment)",
    );
  }
});

const SHOT = {
  maxDiffPixelRatio: 0.001,
  animations: "disabled" as const,
};

test.use({
  viewport: { width: 1280, height: 900 },
  colorScheme: "light",
  reducedMotion: "reduce",
});

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("login page", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/login");
    await expect(page.getByLabel("Work email")).toBeVisible();
    await expect(page).toHaveScreenshot("login.png", SHOT);
  });
});

test.describe("signed in (counsel)", () => {
  test.use({ storageState: storageStatePath("counsel") });



  test("workspace — document pane, slice 1", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    // The workspace has opened on the ANALYSIS since 2026-09-08, so the document
    // pane is hidden until it is disclosed. This shot is of the document pane, so
    // it has to ask for it — the same way journey.spec.ts does. Without this the
    // test failed on its own precondition and never took a screenshot at all,
    // which is why no `-actual.png` for it appears in the CI diff artifact.
    await showDocument(page);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
    await expect(page).toHaveScreenshot("workspace.png", {
      ...SHOT,
      // The contract name carries a timestamp; the layout around it must not move.
      mask: [page.locator(".ws-context h1")],
    });
  });

});

test.describe("signed in (admin)", () => {
  test.use({ storageState: storageStatePath("admin") });

});

/**
 * The new-UI screens (slices 4–8), baselined at the 2026-08-31 UI freeze.
 *
 * Appended AFTER the existing tests deliberately: those create fixture data in
 * a fixed order, so every page below renders a deterministic row count under
 * design-qa's fresh database. Volatile text (timestamped names, dates, ids) is
 * masked; the layout around it is what these baselines pin.
 */
test.describe("the new UI at the freeze (counsel)", () => {
  test.use({ storageState: storageStatePath("counsel") });

  // Every test creates its own data (the file's house idiom): a failed test
  // restarts the worker process, so module-level state shared across tests is
  // lost exactly when baselines are being regenerated. Execution order is
  // fixed, so each page still renders a deterministic row count.

  const askAbout = async (page: import("@playwright/test").Page, contractId: string) => {
    const convo = await apiPost(page, "/conversations", { contract_id: contractId });
    const conversationId = (await convo.json()).data.id as string;
    await apiPost(page, `/conversations/${conversationId}/messages`, {
      question: "What does this document say about liability?",
    });
    return conversationId;
  };

  test("documents landing — intake and list", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await createAnalysedReview(page);
    await page.goto("/dashboard");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-documents.png", {
      ...SHOT,
      fullPage: true,
      /* Names carry timestamps and the Added column carries today's date — and
         until 2026-09-11 the mask covered the first and last cells only, so
         Added was compared. The baseline held 2026-09-09 and drifted a few
         digits a day, under the 1152px threshold, passing green while wrong.
         The comment named the defect the mask did not cover; both cells are
         `ws-mono`, so masking them cannot move anything outside their own box. */
      mask: [
        page.locator("tbody td:first-child"),
        page.locator("tbody td:nth-child(6)"),
        page.locator("tbody td:last-child"),
      ],
    });
  });

  test("reviews queue — filters and rows", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await createAnalysedReview(page);
    await page.goto("/dashboard/reviews");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-reviews.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator("tbody td:nth-child(1)"), page.locator("tbody td:nth-child(3)")],
    });
  });

  test("review report — counts, never a grade", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/dashboard/reviews?id=${reviewId}`);
    await expect(page.locator(".ws-stat").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-report.png", {
      ...SHOT,
      fullPage: true,
      // The document name, snapshot id and date are volatile; the tiles are not.
      mask: [page.locator(".ws-context h1"), page.locator(".ws-context .ws-mono")],
    });
  });

  test("legal queue — one flat list, ruling elsewhere", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await createAnalysedReview(page);
    await page.goto("/dashboard/legal");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-legal.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator("tbody td:nth-child(3)")],
    });
  });

  /* The Ask workspace (2026-09-11) replaced the history TABLE this baseline used
     to pin, so both shots move with it: the empty workspace a reader meets, and
     one open conversation beside its rail. Volatile text — the document name in
     the rail and in the scope line — is masked; the two-pane layout is what
     these pin.

     ⚠️ WHOEVER ADOPTS THE TWO ACTUALS FOR THESE: OPEN THEM AND LOOK.
     A green job 15 is not evidence that a baseline is correct — it is only
     evidence that the run matched whatever pixels the baseline already holds.
     `maxDiffPixelRatio: 0.001` is 1152px of 1280x900, and three baselines drifted
     UNDER that threshold and passed silently for weeks: the Client Profiles nav
     link was missing from `ws-legal`, `ws-ask-history` and `ws-transcript`, and a
     `.ws-hero__ctan` contrast fix sat unabsorbed in `workspace` (found 2026-09-11
     by reading the diff images of a run that failed for an unrelated reason, not
     by a red job 15).

     These two are NEW baselines, so their first CI run fails as missing and the
     actuals are whatever the branch renders — right or wrong. Check the nav is
     complete, the rail carries its chats, and the composer is present before
     committing them. Adopt from CI's `*-actual.png`; never `--update-snapshots`
     locally (owner, 2026-08-30). */
  test("ask — the empty workspace", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await askAbout(page, contractId);
    await page.goto("/dashboard/ask");
    await expect(page.locator(".ws-chat__railitem").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-ask-workspace.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator(".ws-chat__railmeta")],
    });
  });

  test("ask — one conversation, replayed with its citations", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    const conversationId = await askAbout(page, contractId);
    await page.goto(`/dashboard/ask?id=${conversationId}`);
    await expect(page.locator(".ws-turn").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-ask-conversation.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator(".ws-chat__railmeta"), page.locator(".ws-chat__scope")],
    });
  });

  test("research — the one disclosed placeholder", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/dashboard/research");
    await expect(page.getByRole("heading", { name: "Research", exact: true })).toBeVisible();
    await expect(page).toHaveScreenshot("ws-research.png", { ...SHOT, fullPage: true });
  });
});

test.describe("the new UI at the freeze (admin)", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("admin — users, roles, grants", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/dashboard/admin");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    /* Last sign-in and Created are real timestamps — this shot carried NO mask,
       so its baseline was pinned to the minute it was adopted (09-10 11:52) and
       has been drifting under the threshold ever since. Both columns are
       `ws-mono`: fixed advance width, so a mask here hides pixels without
       moving the row. */
    await expect(page).toHaveScreenshot("ws-admin.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator("tbody td:nth-child(6)"), page.locator("tbody td:nth-child(7)")],
    });
  });

  test("audit trail — the dense read-only table", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/dashboard/admin/audit");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page).toHaveScreenshot("ws-audit.png", {
      ...SHOT,
      // Every cell is volatile except the header, filters and grid — mask the
      // body wholesale; this baseline pins the frame, not the entries.
      mask: [page.locator("tbody")],
    });
  });
});

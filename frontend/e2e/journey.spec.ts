import { expect, test } from "@playwright/test";

import {
  askSend,
  createAnalysedReview,
  fixture,
  openAsk,
  openFindingsTab,
  openUploadPanel,
  showDocument,
  storageStatePath,
} from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The complete user journeys of the 2026-08-31 product-intent clarification
 * (§23/§31), end to end against the real backend.
 *
 * Journey 1 — upload → analyze → report → findings → ask. Chat is available the
 * moment the document is analyzed and is NOT conditional on resolving anything:
 * the ask succeeds (with an honest refusal, since no generator credential
 * exists) while a DEVIATION finding still awaits a Legal Decision.
 *
 * Journey 2 — the revised version. Uploading v2 through the workspace creates a
 * REAL new version with its own analysis; v1's document text, findings and
 * report stay reachable exactly as they were (nothing is marked resolved by the
 * upload — rule 14), and the ask surface follows the latest version honestly.
 */

const REFUSAL_TEXT =
  "Information not found in the selected document. " +
  "The available material does not answer this question.";

test("journey: upload → analysis → report → findings → ask, with findings still open", async ({
  page,
}) => {
  // ENTIRELY through the UI (2026-08-31 UX correction): one upload act chains
  // create → version → current-standards snapshot → Review → analysis.
  const f = fixture();
  await page.goto("/dashboard");
  // DD-4: upload is a disclosure behind the primary action, not an open form.
  await openUploadPanel(page);
  await page.setInputFiles('input[type="file"]', f.document.path);
  // AM-51: upload → review → workspace, with no question asked. In e2e there is
  // no generation credential, so no type is recorded and the engine measures
  // the document by its content alone.
  await page.waitForURL(/\/dashboard\?id=[0-9a-f-]{36}$/, { timeout: 45_000 });
  const contractId = page.url().match(/dashboard\?id=([0-9a-f-]{36})/)![1];

  // The workspace opens on the analysis (2026-09-08: the document no longer
  // holds the majority of the screen permanently); the document is one
  // disclosure away, and the full findings pane is the side card's second tab.
  await showDocument(page);
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  await openFindingsTab(page);
  const finding = page.locator("article[data-finding-id]").first();
  await expect(finding).toBeVisible();
  // The face says the reader's word; the engine's word is one click away. The
  // fixture's zero-tolerance rule ruled this deviation UNACCEPTABLE, so the
  // reader sees Not accepted (owner's final status decision, 2026-09-09).
  await expect(finding.locator("[data-status]")).toHaveText("Requires modification");
  await expect(finding.locator(".ws-determined")).toContainText("DEVIATION");

  // The drill (2026-08-31 v2): the summary strip's counts are pressable
  // filters — category → finding → evidence without leaving the pane.
  // The count is a `.ws-filter__n` badge beside the word since the reference-design
  // restyle (2026-09-09), so the accessible name is "Requires modification 1" with a
  // space, not "Requires modification (1)". The count itself is still asserted.
  const filters = page.locator(".ws-filter");
  await expect(filters.getByRole("button", { name: /^Requires modification\s+\d+$/ })).toBeVisible();

  /*
   * The row is ONE fixed order the reader can learn (owner, 2026-09-09): "All"
   * first and pressed on arrival, then `AM-56`'s three words in their own fixed
   * order. It used to open pre-filtered, on a requires_decision filter that
   * pushed "All" into second place — so the row a reader learned on one
   * contract was not the row the next contract gave them.
   *
   * Asserted in a browser because a click is the one thing the static suite
   * cannot make: `src/__tests__/findings-filter.test.tsx` pins the order, the
   * labels, the counts and the default; only here can the subset each filter
   * actually shows be checked.
   */
  const labels = await filters.getByRole("button").allTextContents();
  const total = Number(labels[0]!.match(/^All \((\d+)\)$/)![1]);
  const words = labels.slice(1).map((l) => l.replace(/ \(\d+\)$/, ""));
  // A subsequence of the fixed order — a word with no findings renders no
  // button, and the words that remain keep their places.
  expect(words).toEqual(
    ["Acceptable", "Requires modification", "Needs a decision"].filter((w) => words.includes(w)));
  await expect(filters.getByRole("button").first()).toHaveAttribute("aria-pressed", "true");
  const cards = page.locator("article[data-finding-id]");
  await expect(cards).toHaveCount(total);

  for (const word of words) {
    const button = filters.getByRole("button", { name: new RegExp(`^${word} \\(\\d+\\)$`) });
    const n = Number((await button.textContent())!.match(/\((\d+)\)$/)![1]);
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    // Its own count, and nothing but its own findings.
    await expect(cards).toHaveCount(n);
    for (let i = 0; i < n; i += 1) {
      await expect(cards.nth(i).locator("[data-status]").first()).toHaveText(word);
    }
  }

  // "All" comes back to every finding, which is what makes the filters undoable.
  await filters.getByRole("button", { name: /^All \(\d+\)$/ }).click();
  await expect(cards).toHaveCount(total);

  await filters.getByRole("button", { name: /^Requires modification/ }).click();
  await expect(finding).toBeVisible();
  // …and the drill ends in verbatim text: the cited excerpt sits one click
  // inside "How this was determined" (seventh pass — the face is the four
  // answers only), and its location button lights the passage in the document.
  await finding.locator(".ws-determined > summary").first().click();
  await expect(finding.locator(".ws-evidence__quote").first()).toBeVisible();
  await finding.locator(".ws-evidence__loc").first().click();
  await expect(page.locator(".ws-row--lit")).toBeVisible();

  // Finding → Ask handoff: the dock OPENS, an EDITABLE draft lands in the input,
  // and nothing sends. Opening is part of the handoff now that the input is not
  // permanently on screen — otherwise "Ask about this" would appear to do nothing.
  await finding.getByRole("button", { name: "Ask about this" }).click();
  const askInput = page.getByLabel("Your question about this document");
  await expect(askInput).toBeVisible();
  await expect(askInput).toHaveValue(/What does this document say about/);

  // Export — the analysis leaves as a real file (owner directive §30).
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/analysis\.pdf$/);

  // Chat, immediately — the open finding gates nothing (AM-25 r1).
  await (await openAsk(page)).fill("Explain the zorbulated framblewitz stipulations");
  await askSend(page).click();
  await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(REFUSAL_TEXT, {
    timeout: 20_000,
  });
  // …and the finding is still open beside it. Nothing was auto-resolved.
  await expect(finding).toContainText("Decision required");

  // The report exists and speaks in counts — reached from the Reviews queue.
  const listed = await page.request.get(`/api/v1/reviews?contract_id=${contractId}`);
  const reviewId = (await listed.json()).data[0].id;
  await page.goto(`/dashboard/reviews?id=${reviewId}`);
  await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();

  // And the Documents list now answers "what did analysis find" — a status
  // pill (real derived bucket) plus the findings cell's non-zero "review"
  // badge, matching the DEVIATION finding just recorded (2026-09-01 redesign:
  // classification names moved from a text chip to a status pill + count
  // badges — the underlying fact is the same).
  await page.goto("/dashboard");
  const row = page.locator("tbody tr").filter({ has: page.locator(`a[href="/dashboard?id=${contractId}"]`) });
  await expect(row.locator(".ws-status-pill")).toContainText("Needs attention");
  // Three badges, always in the one order, wearing the one set of tones
  // (owner, 2026-09-09): green Acceptable, amber Requires modification, red
  // Needs a decision. The fixture's DEVIATION is a Requires modification, so
  // the AMBER badge is the non-zero one — it was the red one until the tones
  // were put right.
  const badges = row.locator(".ws-findings-badge");
  await expect(badges).toHaveCount(3);
  expect(await badges.nth(0).getAttribute("class")).toContain("ws-findings-badge--ok");
  expect(await badges.nth(1).getAttribute("class")).toContain("ws-findings-badge--warn");
  expect(await badges.nth(2).getAttribute("class")).toContain("ws-findings-badge--bad");
  await expect(badges.nth(1)).not.toHaveClass(/ws-findings-badge--zero/);
});

test("journey: a revised version is a real new analysis; v1 stays historically valid", async ({
  page,
}) => {
  const f = fixture();
  const v1 = await createAnalysedReview(page);

  // Upload the revision through the workspace's own control.
  await page.goto(`/dashboard?id=${v1.contractId}`);
  await showDocument(page);
  await page.getByRole("button", { name: "Upload a revised version" }).click();
  await expect(page.getByText("becomes a NEW version")).toBeVisible();
  await page.setInputFiles('input[type="file"]', f.document.path);
  await page.getByRole("button", { name: "Upload", exact: true }).click();

  // The workspace lands on v2; the picker knows both versions.
  const picker = page.locator(".ws-version select");
  await expect(picker).toBeVisible({ timeout: 20_000 });
  await expect(picker.locator("option")).toHaveCount(2);
  await expect(picker).toHaveValue(/^(?!$)/); // a concrete id
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();

  // v2 got its OWN analysis IN THE FLOW (2026-08-31 v2: the revised upload
  // chains the same best-effort analysis as a first upload — one loop).
  await openFindingsTab(page);
  await expect(page.locator("article[data-finding-id]").first()).toBeVisible({ timeout: 20_000 });
  const contract = (await (await page.request.get(`/api/v1/contracts/${v1.contractId}`)).json()).data;
  expect(contract.document_versions.length).toBe(2);
  const listed = await page.request.get(
    `/api/v1/reviews?contract_id=${v1.contractId}`);
  const reviewIds = (await listed.json()).data.map((r: { id: string }) => r.id);
  const review2 = { id: reviewIds.find((id: string) => id !== v1.reviewId)! };
  expect(review2.id).toBeTruthy();

  // Switch to v1: its document text and ITS findings render, and Ask ANSWERS
  // ABOUT V1.
  //
  // This assertion is the inverse of what it was before 2026-09-02, and
  // deliberately so. It used to require the input to be DISABLED with a
  // "Open the latest version" button — it pinned the defect the owner reported,
  // because the server could only ever answer from the newest version and an
  // answer's citations would have pointed at evidence rows absent from this
  // page. The endpoint now takes the version being asked about (DD-15), so the
  // correct behaviour is the opposite: enabled, scoped, and saying which version
  // answers.
  await picker.selectOption({ index: 1 });
  await expect(page).toHaveURL(/[?&]version=/);
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  await openFindingsTab(page);
  await expect(page.locator("article[data-finding-id]").first()).toBeVisible();

  const v1Ask = await openAsk(page);
  await expect(v1Ask).toBeEnabled();
  await expect(page.locator(".ws-dock__scope")).toContainText("Version 1");
  await expect(page.getByRole("button", { name: "Open the latest version" })).toHaveCount(0);
  // And the request that leaves the page names v1, not the newest version.
  const [asked] = await Promise.all([
    page.waitForRequest((r) => r.url().includes("/messages") && r.method() === "POST"),
    v1Ask.fill("liability shall not exceed fees paid").then(() => askSend(page).click()),
  ]);
  expect(JSON.parse(asked.postData()!).document_version_id).toBeTruthy();
  await page.keyboard.press("Escape");

  // v1's Review and report remain exactly where they were.
  await page.goto(`/dashboard/reviews?id=${v1.reviewId}`);
  await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();

  // And the reviews queue lists both analyses.
  await page.goto("/dashboard/reviews");
  await expect(page.locator(`tr[data-review-id="${v1.reviewId}"]`)).toBeVisible();
  await expect(page.locator(`tr[data-review-id="${review2.id}"]`)).toBeVisible();
});

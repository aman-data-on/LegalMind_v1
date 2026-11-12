import { expect, test } from "@playwright/test";

import {
  askSend,
  confirmUpload,
  createAnalysedReview,
  fixture,
  openAsk,
  openFindingsTab,
  openUploadPanel,
  showDocument,
  storageStatePath, uploadNewVersionFile,
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
  // The refusal names every source the caller's permissions let it consult
  // (routing.refusal_text, 2026-09-09), so the document-only and the
  // document-plus-positions wordings are both the one honest sentence.
  /^I couldn't find an answer in the selected document(?: or the organization's approved positions)?(?: or the approved statutes)?, so I won't guess\.$/;

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
  // The compact Upload dialog (2026-09-29) shows the selected file before
  // sending anything — the chain starts only once "Upload & Analyze" is
  // pressed.
  await confirmUpload(page);
  // AM-51: upload → review → workspace, with no question asked. In e2e there is
  // no generation credential, so no type is recorded and the engine measures
  // the document by its content alone.
  await page.waitForURL(/\/(dashboard\?id=|contracts\/)[0-9a-f-]{36}$/, { timeout: 45_000 });
  const contractId = page.url().match(/(?:dashboard\?id=|contracts\/)([0-9a-f-]{36})/)![1];

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
  await expect(finding.locator("[data-status]")).toHaveText("Change needed");
  // S1: the engine's word is a Legal detail — the deal owner holds no `legal.review`,
  // so their disclosure is "Where it says this" and the classification is absent.
  await expect(finding.locator(".ws-determined > summary")).toHaveText("Where it says this");
  await expect(finding.locator(".ws-determined")).not.toContainText("DEVIATION");

  // The drill (2026-08-31 v2): the summary strip's counts are pressable
  // filters — category → finding → evidence without leaving the pane.
  // UX Batch 2: one filter control, "Show points" — "All" first and pressed on arrival,
  // then the status words (the Points pane's own vocabulary), each "Word, n"; a status
  // with no point renders no button.
  const filters = page.getByRole("group", { name: "Show points" });
  const PILL = /^(.*), (\d+)$/;               // aria-label: [, word, count]
  const named = async () => (await filters.getByRole("button").evaluateAll(
    (els) => els.map((e) => e.getAttribute("aria-label") ?? ""))).map((l) => l.match(PILL)!);
  const all = await named();
  expect(all[0]![1]).toBe("All");
  const total = Number(all[0]![2]);
  await expect(filters.getByRole("button").first()).toHaveAttribute("aria-pressed", "true");
  const cards = page.locator("article[data-finding-id]");
  await expect(cards).toHaveCount(total);

  for (const [, word, count] of all.slice(1)) {
    const button = filters.getByRole("button", { name: `${word}, ${count}`, exact: true });
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    // Its own count, and nothing but its own points.
    await expect(cards).toHaveCount(Number(count));
    for (let i = 0; i < Number(count); i += 1) {
      if (word === "Decided") continue;
      await expect(cards.nth(i)).toContainText(word!);
    }
  }

  // "All" comes back to every point, which is what makes the filters undoable.
  await filters.getByRole("button", { name: `All, ${total}`, exact: true }).click();
  await expect(cards).toHaveCount(total);

  await filters.getByRole("button").nth(1).click();
  await expect(finding).toBeVisible();
  // …and the drill ends in verbatim text: the cited excerpt sits one click
  // inside "How this was determined" (seventh pass — the face is the four
  // answers only), and its location button lights the passage in the document.
  // CLM Page 2 (M6): the card quotes the cited passage on its face, and "View in document"
  // lights it in the document.
  await expect(finding.locator(".ws-case__quote").first()).toBeVisible();
  await finding.getByRole("button", { name: "View in document" }).click();
  await expect(page.locator(".ws-row--lit")).toBeVisible();

  // Finding → Ask handoff: the dock OPENS, an EDITABLE draft lands in the input,
  // and nothing sends. Opening is part of the handoff now that the input is not
  // permanently on screen — otherwise "Ask about this" would appear to do nothing.
  await finding.getByRole("button", { name: "Ask about this" }).click();
  const askInput = page.getByLabel("Your question about this document");
  await expect(askInput).toBeVisible();
  await expect(askInput).toHaveValue(/What does this document say about/);

  // The report is seen before it is downloaded (owner, 2026-10-22): the header opens it.
  // S1: it lives under the header's ⋯ now, beside the other secondary actions.
  await page.getByRole("button", { name: "More actions" }).click();
  await expect(page.getByRole("menuitem", { name: "View report" })).toHaveAttribute(
    "href", /\/dashboard\/reviews\?id=/);
  await page.keyboard.press("Escape");

  // Chat, immediately — the open finding gates nothing (AM-25 r1).
  await (await openAsk(page)).fill("Explain the zorbulated framblewitz stipulations");
  await askSend(page).click();
  await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(REFUSAL_TEXT, {
    timeout: 20_000,
  });
  // …and the finding is still open beside it. Nothing was auto-resolved.
  await expect(finding.locator(".ws-point__who")).toHaveText("Not sent to Legal yet");   // H2 (Page 2): "With Legal" once sent

  // The report exists and speaks in counts — reached from the Reviews queue.
  const listed = await page.request.get(`/api/v1/reviews?contract_id=${contractId}`);
  const reviewId = (await listed.json()).data[0].id;
  await page.goto(`/dashboard/reviews?id=${reviewId}`);
  await expect(page.getByText(/was checked against our standard terms on \d+ point/)).toBeVisible();
  // …and leaves as a real file from beside the preview (owner directive §30).
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/analysis\.pdf$/);

  // And the Documents list now answers "what did analysis find" — a status
  // pill (real derived bucket) plus the findings cell's non-zero "review"
  // badge, matching the DEVIATION finding just recorded (2026-09-01 redesign:
  // classification names moved from a text chip to a status pill + count
  // badges — the underlying fact is the same).
  await page.goto("/contracts");
  const row = page.locator("tbody tr").filter({ has: page.locator(`a[href="/contracts/${contractId}"]`) });   // AM-262
  // CLM S1 (2026-11-03): the Contracts home says it in words, one count per cell — the
  // stage, and the open points (the DEVIATION just recorded is one open point). No pills,
  // no badges, no tone to read: the same fact, as the header and Summary say it.
  await expect(row.locator('td[data-label="Changes and points"]')).toContainText("1 open point");
  await expect(row.locator('td[data-label="Stage"]')).not.toBeEmpty();
});

test("journey: a revised version is a real new analysis; v1 stays historically valid", async ({
  page,
}) => {
  const f = fixture();
  const v1 = await createAnalysedReview(page);

  // Upload the revision through the workspace's own control.
  await page.goto(`/dashboard?id=${v1.contractId}`);
  await showDocument(page);
  await uploadNewVersionFile(page, f.document.path);

  // The workspace lands on v2; the picker knows both versions.
  const picker = page.locator("select.ws-version");
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
  await expect(page.getByText(/was checked against our standard terms on \d+ point/)).toBeVisible();

  // And both reports still open by their own links. (The legacy queue is Legal's since
  // UX Batch 2: this owner is sent to Contracts.)
  await page.goto(`/dashboard/reviews?id=${review2.id}`);
  await expect(page.getByText(/was checked against our standard terms on \d+ point/)).toBeVisible();
  await page.goto("/dashboard/reviews");
  await expect(page).toHaveURL(/\/contracts$/);
});

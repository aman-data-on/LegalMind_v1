import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { askSend, createAnalysedReview, csrfToken, fixture, openAsk, storageStatePath } from "./support";

/** Signed in as `owner` — USER and nothing else. Every assertion below is
 *  therefore what an ORDINARY user meets, not what an administrator meets. */
test.use({ storageState: storageStatePath("owner") });

/**
 * The Ask dock: a secondary floating surface, and Ask on the version you are
 * reading (owner report, 2026-09-02 — DD-15).
 *
 * These are the two properties no isolated test can prove, because both are
 * about the composed, laid-out page:
 *
 * 1. **Ask reserves no workspace height.** The static render can show that the
 *    old bar's markup is gone; only a browser can show that the document region
 *    actually GREW by what the bar used to hold, that the launcher is a 44px
 *    target, and that nothing scrolls to rest underneath it.
 *
 * 2. **Ask works on an older version, and says which version answers.** The
 *    former bar disabled its input and offered "open the latest version" — the
 *    exact behaviour reported. What is asserted here is the composed outcome: a
 *    reader on version 1 of a two-version contract can type a question, and the
 *    request that leaves the page names version 1.
 *
 * The generation gate is closed in this harness (no provider credential — CI
 * asserts that), so an ask still ends in the byte-identical refusal. That is
 * production until `AM-31` opens, and it is enough: what is under test is which
 * document was searched and how the surface behaves, not the prose.
 */

/** `AM-29` r4's constant, as `backend/legalmind/assist/state.py` declares it. */
const REFUSAL_TEXT =
  "Information not found in the selected document. " +
  "The available material does not answer this question.";

/** Upload a second document version to an existing contract, as the user would. */
async function uploadRevision(page: import("@playwright/test").Page, contractId: string) {
  const f = fixture();
  const response = await page.request.post(
    `/api/v1/contracts/${contractId}/document-versions`,
    {
      headers: {
        "Content-Type": f.document.mime,
        "X-Filename": "revised.docx",
        "X-CSRF-Token": await csrfToken(page),
      },
      data: readFileSync(f.document.path),
    },
  );
  expect(response.ok(), `revision upload failed: ${await response.text()}`).toBeTruthy();
  return (await response.json()).data.document_version;
}

test.describe("Ask is a floating secondary tool", () => {
  test("closed, it costs the workspace no height and is still a real keyboard target", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);

    const launcher = page.getByRole("button", { name: /Ask about this document/i });
    await expect(launcher).toBeVisible();

    // Touch-target minimum, and a compact footprint rather than a bar.
    const box = (await launcher.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(box.width).toBeLessThan(200);

    // The panel exists in the DOM (state survives closing) but is inert and
    // contributes nothing to layout while closed.
    const panel = page.locator(".ws-dock__panel");
    await expect(panel).toHaveCount(1);
    await expect(panel).toBeHidden();

    // The document region reaches essentially the bottom of the workspace: the
    // old bar's reserved row is genuinely gone, not merely restyled.
    const workmain = (await page.locator(".ws-workmain").boundingBox())!;
    const documentPane = (await page.locator(".ws-pane--document").boundingBox())!;
    const gapBelowDocument =
      workmain.y + workmain.height - (documentPane.y + documentPane.height);
    expect(gapBelowDocument).toBeLessThan(40);

    // And the page itself never scrolls — scroll ownership is unchanged.
    const overflowed = await page.evaluate(
      () => document.documentElement.scrollHeight > window.innerHeight + 1,
    );
    expect(overflowed).toBeFalsy();
  });

  test("opens from the keyboard, focuses the input, closes on Escape and restores focus", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);

    const launcher = page.getByRole("button", { name: /Ask about this document/i });
    await launcher.focus();
    await page.keyboard.press("Enter");

    const input = page.getByLabel("Your question about this document");
    await expect(input).toBeFocused();
    await expect(page.locator(".ws-dock__panel")).toBeVisible();
    // The launcher steps out of the way while the panel is open, so it can never
    // obscure focus inside it (WCAG 2.2 AA 2.4.11).
    await expect(launcher).toBeHidden();

    await page.keyboard.press("Escape");
    await expect(page.locator(".ws-dock__panel")).toBeHidden();
    await expect(launcher).toBeFocused();
  });

  test("the document stays usable with the panel open, and closing keeps the reading position", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);
    await page.getByRole("button", { name: /Ask about this document/i }).click();

    // Not a modal: the document is still visible and its outline still clickable,
    // so "open chat" never means "leave the document".
    await expect(page.locator(".ws-pane--document")).toBeVisible();
    const clause = page.locator(".ws-outline__list button").first();
    if (await clause.count()) {
      await clause.click();
      await expect(page.locator(".ws-dock__panel")).toBeVisible();
    }

    // A draft survives a close and reopen — the panel is kept mounted.
    const input = page.getByLabel("Your question about this document");
    await input.fill("what does clause 17 say");
    await page.getByRole("button", { name: "Close Ask" }).click();
    await expect(page.locator(".ws-dock__panel")).toBeHidden();
    await page.getByRole("button", { name: /Ask about this document/i }).click();
    await expect(input).toHaveValue("what does clause 17 say");
  });
});

test.describe("Ask answers about the version on screen", () => {
  test("an older version is asked about directly — never redirected to the latest", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    const contract = await (await page.request.get(`/api/v1/contracts/${contractId}`)).json();
    const v1 = contract.data.document_versions[0];
    await uploadRevision(page, contractId);

    // Open version 1 explicitly, exactly as the version picker does.
    await page.goto(`/dashboard?id=${contractId}&version=${v1.id}`);
    await page.getByRole("button", { name: /Ask about this document/i }).click();

    // The header states the scope instead of blocking the input.
    await expect(page.locator(".ws-dock__scope")).toContainText("Version 1");
    await expect(page.getByRole("button", { name: "Open the latest version" })).toHaveCount(0);

    const input = page.getByLabel("Your question about this document");
    await expect(input).toBeEnabled();

    // What actually leaves the page is the assertion that matters: the request
    // names version 1, so the answer and its citations belong to the page being
    // read rather than to whichever version happens to be newest.
    const [request] = await Promise.all([
      page.waitForRequest(
        (r) => r.url().includes("/messages") && r.method() === "POST",
      ),
      input.fill("liability shall not exceed fees paid").then(() =>
        page.getByRole("button", { name: /Send question|Searching/ }).click(),
      ),
    ]);
    expect(JSON.parse(request.postData()!).document_version_id).toBe(v1.id);

    // And the surface still ends where it must while the gate is closed.
    const refusal = page.locator(".ws-ask__answer--refusal").first();
    await expect(refusal).toHaveText(REFUSAL_TEXT, { timeout: 30_000 });
  });

  test("the latest version is named as latest, and its request names it too", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    const revision = await uploadRevision(page, contractId);

    await page.goto(`/dashboard?id=${contractId}`);
    await page.getByRole("button", { name: /Ask about this document/i }).click();
    await expect(page.locator(".ws-dock__scope")).toContainText("Version 2");
    await expect(page.locator(".ws-dock__scope")).toContainText("latest");

    const input = page.getByLabel("Your question about this document");
    const [request] = await Promise.all([
      page.waitForRequest(
        (r) => r.url().includes("/messages") && r.method() === "POST",
      ),
      input.fill("liability shall not exceed fees paid").then(() =>
        page.getByRole("button", { name: /Send question|Searching/ }).click(),
      ),
    ]);
    expect(JSON.parse(request.postData()!).document_version_id).toBe(revision.id);
  });

  test("a conversation survives a reload, and no confidence figure appears anywhere", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);
    await page.getByRole("button", { name: /Ask about this document/i }).click();

    const input = page.getByLabel("Your question about this document");
    await input.fill("Explain the wibblesprocket grondulated flimwrastic covenants");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(
      REFUSAL_TEXT,
      { timeout: 30_000 },
    );

    // Reload, reopen: the turn comes back from the server, citations intact.
    await page.reload();
    await page.getByRole("button", { name: /Ask about this document/i }).click();
    await expect(page.locator(".ws-ask__turn")).toHaveCount(1, { timeout: 20_000 });
    await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(REFUSAL_TEXT);

    // `AI-03` item 16 at the composed-page level.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });
});

test.describe("narrow viewport", () => {
  test("the launcher stays reachable, the sheet does not overflow, and nothing scrolls sideways", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);

    const launcher = page.getByRole("button", { name: /Ask about this document/i });
    await expect(launcher).toBeVisible();
    const box = (await launcher.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);

    await launcher.click();
    const panel = page.locator(".ws-dock__panel");
    await expect(panel).toBeVisible();
    const panelBox = (await panel.boundingBox())!;
    expect(panelBox.x).toBeGreaterThanOrEqual(0);
    expect(panelBox.x + panelBox.width).toBeLessThanOrEqual(390 + 1);

    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(sideways).toBeFalsy();

    // Escape still closes on a touch-sized viewport.
    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();
  });
});

test.describe("a transcript that spans versions", () => {
  test("a turn answered about another version is labelled, and its label survives reload", async ({
    page,
  }) => {
    // Ask on version 2 (the latest), then read version 1: the v2-scoped turn in
    // the transcript must SAY it was about version 2, because its citations
    // belong to v2's reading order and cannot land on the v1 page. Refusals are
    // version-scoped turns too — the retrieval that refused was scoped — which
    // is what lets this be proven with the generation gate closed.
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    const contract = await (await page.request.get(`/api/v1/contracts/${contractId}`)).json();
    const v1 = contract.data.document_versions[0];
    await uploadRevision(page, contractId);

    // On the latest: ask something unanswerable — a quick, version-scoped turn.
    await page.goto(`/dashboard?id=${contractId}`);
    const input = await openAsk(page);
    await input.fill("Explain the grimbulated vortexial plumbus obligations");
    await askSend(page).click();
    await expect(page.locator(".ws-ask__answer--refusal").first()).toBeVisible({
      timeout: 30_000,
    });
    // On the version it was asked about, no cross-version label appears.
    await expect(page.locator(".ws-dock__turn-version")).toHaveCount(0);

    // Switch to version 1: the same turn is now labelled as another version's.
    await page.keyboard.press("Escape");
    await page.locator(".ws-version select").selectOption(v1.id);
    await expect(page).toHaveURL(/[?&]version=/);
    await openAsk(page);
    await expect(page.locator(".ws-dock__turn-version").first()).toContainText(
      "Version 2",
      { timeout: 20_000 },
    );

    // And the label is durable — it comes from the server's replay, not from
    // memory of the live turn.
    await page.reload();
    await openAsk(page);
    await expect(page.locator(".ws-dock__turn-version").first()).toContainText(
      "Version 2",
      { timeout: 20_000 },
    );
  });
});

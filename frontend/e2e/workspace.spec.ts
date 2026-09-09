import { expect, test } from "@playwright/test";

import {
  apiPost,
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
 * Workspace slice 1 — the document pane and the cross-pane highlight, against the
 * real backend (PRODUCT_UX_ROADMAP §G: the risk slice).
 *
 * The property that matters: pointing at an evidence row — from the outline or
 * from a shared URL — scrolls to it, lights it, and moves focus to it. Everything
 * downstream (verdict click, citation click) reuses exactly this gesture.
 */

test.describe("the document pane", () => {
  test("renders the document as evidence rows under page markers, with readiness", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await showDocument(page);

    // The new shell, not the legacy chrome.
    await expect(page.locator(".ws-shell")).toBeVisible();
    await expect(page.locator(".topbar")).toHaveCount(0);

    const doc = page.locator('[data-region="document"]');
    // DD-9: the document area is two cards — the clauses card and the document
    // card under its toolbar.
    // "Contents" since 2026-09-05: this is the document's own outline, and a
    // clause is what a finding attaches to rather than a navigation target.
    await expect(doc.locator(".ws-outline__title")).toHaveText("Contents");
    await expect(doc.locator(".ws-doccard__bar")).toBeVisible();
    await expect(doc.locator(".ws-row").first()).toBeVisible();
    // A lone "Unnumbered pages" banner is noise when the WHOLE document has no
    // page model (a DOCX has none until printed) — it renders only where it
    // distinguishes a group from a numbered one elsewhere in the SAME document.
    // The fixture is entirely unnumbered, so no marker renders at all; the
    // toolbar says so plainly instead of a fake "— of —".
    await expect(doc.locator(".ws-page__marker")).toHaveCount(0);
    await expect(doc.locator(".ws-doccard__bar")).toContainText("Not paginated");
    await expect(doc.locator(".ws-readiness")).toHaveAttribute(
      "data-readiness",
      /ready|lexical-only|not-indexed/,
    );
    // Verbatim text is set in the quote voice; nothing here says "confidence".
    await expect(doc.locator(".ws-row__text").first()).toBeVisible();
    expect((await page.content()).toLowerCase()).not.toContain("confidence");
  });

  test("the outline points at a clause: it lights, scrolls and takes focus", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await showDocument(page);
    const doc = page.locator('[data-region="document"]');
    await expect(doc.locator(".ws-row").first()).toBeVisible();

    const entries = doc.locator(".ws-outline button");
    test.skip((await entries.count()) === 0, "fixture document carries no clause numbering");

    const last = entries.last();
    await last.click();
    const lit = doc.locator(".ws-row--lit");
    await expect(lit).toHaveCount(1);
    await expect(lit).toBeFocused();
    await expect(last).toHaveAttribute("aria-current", "true");
    // The URL now carries the target, so the view can be shared.
    await expect(page).toHaveURL(/[?&]evidence=[0-9a-f-]{36}/);
  });

  test("a shared link lands on the exact row", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await showDocument(page);
    const doc = page.locator('[data-region="document"]');
    await expect(doc.locator(".ws-row").first()).toBeVisible();
    const targetId = await doc.locator(".ws-row").last().getAttribute("data-evidence-id");

    await page.goto(`/dashboard?id=${contractId}&evidence=${targetId}`);
    const lit = doc.locator(".ws-row--lit");
    await expect(lit).toHaveAttribute("data-evidence-id", targetId!);
    await expect(lit).toBeFocused();
  });

  test("a contract with no upload offers a real, inline upload — never a legacy link", async ({
    page,
  }) => {
    const f = fixture();
    const created = await apiPost(page, "/contracts", {
      name: `Bare ${Date.now()}`,
      contract_type: "MSA",
    });
    const contract = (await created.json()).data;
    await page.goto(`/dashboard?id=${contract.id}`);
    await expect(page.getByRole("heading", { name: "No document uploaded yet." })).toBeVisible();
    await expect(page.locator('[data-region="document"]')).toHaveCount(0);

    // 2026-08-30 cleanup: no path back into the legacy application from here.
    await expect(page.locator('a[href^="/contracts"]')).toHaveCount(0);

    await page.setInputFiles('input[type="file"]', f.document.path);
    await page.getByRole("button", { name: "Upload" }).click();
    await showDocument(page);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  });

  test("someone else's contract reads exactly like a nonexistent one", async ({
    page,
    browser,
  }) => {
    // Counsel builds a contract the owner cannot see.
    const counsel = await browser.newContext({ storageState: storageStatePath("counsel") });
    const other = await counsel.newPage();
    const created = await apiPost(other, "/contracts", {
      name: `Theirs ${Date.now()}`,
      contract_type: "MSA",
    });
    const theirs = (await created.json()).data.id;
    await counsel.close();

    await page.goto(`/dashboard?id=${theirs}`);
    await expect(page.getByRole("heading", { name: "Not found." })).toBeVisible();
    const stolen = await page.locator(".ws-state").innerText();

    await page.goto(`/dashboard?id=00000000-0000-4000-8000-000000000000`);
    await expect(page.getByRole("heading", { name: "Not found." })).toBeVisible();
    const ghost = await page.locator(".ws-state").innerText();
    expect(stolen).toBe(ghost);
    expect(stolen.toLowerCase()).not.toContain("access");
  });
});

test.describe("the new UI is the entire post-login experience (2026-08-30 cleanup)", () => {
  test.describe("signed out", () => {
    // Overrides this file's top-level `owner` storageState: this test's whole
    // point is the SIGNED-OUT redirect, which an inherited session would hide.
    test.use({ storageState: { cookies: [], origins: [] } });

    test("a successful login lands on /dashboard, never /contracts", async ({ page }) => {
      const f = fixture();
      await page.goto("/login");
      await page.getByLabel("Work email").fill(f.accounts.owner.email);
      await page.getByLabel("Password", { exact: true }).fill(f.accounts.owner.password);
      await page.getByRole("button", { name: /sign in/i }).click();
      await page.waitForURL(/\/dashboard$/, { timeout: 20_000 });
      await expect(page.locator(".ws-shell")).toBeVisible();
      await expect(page.locator(".topbar")).toHaveCount(0);
    });

    test("a signed-out visit ends at /login — never a restricted flash (owner ruling, 2026-08-31)", async ({ page }) => {
      // Before this ruling a signed-out visit to /dashboard rendered the shell
      // with an empty nav and "Access restricted" — which reads as an RBAC
      // denial when the visitor simply isn't signed in. The correct flow is:
      // sign in first, then land per RBAC. `/` still routes through /dashboard
      // (the cleanup's own guarantee), and the workspace shell then sends the
      // signed-out visitor on to /login.
      await page.goto("/");
      await page.waitForURL(/\/login$/, { timeout: 20_000 });
      await expect(page.getByLabel("Work email")).toBeVisible();
      // Never the legacy bare-shell markup, and never the restricted note.
      await expect(page.getByText("Access restricted")).toHaveCount(0);
      await expect(page.getByText("You are signed out")).toHaveCount(0);
      await expect(page.locator(".topbar")).toHaveCount(0);
    });

    test("a deep /dashboard link, signed out, also ends at /login", async ({ page }) => {
      await page.goto("/dashboard/reviews");
      await page.waitForURL(/\/login$/, { timeout: 20_000 });
      await expect(page.getByLabel("Work email")).toBeVisible();
    });
  });

  test("the Dashboard lists documents and links only into /dashboard", async ({ page }) => {
    const created = await apiPost(page, "/contracts", {
      name: `Index ${Date.now()}`,
      contract_type: "MSA",
    });
    const contract = (await created.json()).data;

    await page.goto("/dashboard");
    await expect(page.locator(".ws-shell")).toBeVisible();
    // `AM-38` (AB-11, 2026-09-01) renamed this screen: the heading is "Dashboard".
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();

    // `exact` (2026-09-08): the row's action link is now named "Analyze <the
    // contract>" rather than a bare "Analyze" — twenty-five links all
    // announcing the same word gave a screen reader no way to tell one row's
    // action from another's. Its name therefore CONTAINS the contract name,
    // and `getByRole` matches names by substring, so the un-anchored locator
    // began resolving to two links. Both point at the same href; this asserts
    // exactly what it always did, against the document-name link alone.
    const row = page.getByRole("link", { name: contract.name, exact: true });
    await expect(row).toHaveAttribute("href", `/dashboard?id=${contract.id}`);
    await expect(page.locator('a[href^="/contracts"]')).toHaveCount(0);

    await row.click();
    await expect(page).toHaveURL(`/dashboard?id=${contract.id}`);
  });

  test("intake is upload-first: file → derived name + declared type → workspace (2026-08-31 UX correction)", async ({
    page,
  }) => {
    const f = fixture();
    await page.goto("/dashboard");
    // The primary act is still the file — DD-4 just put the input behind the
    // page's primary action rather than leaving a form open in the fold.
    await openUploadPanel(page);
    await page.setInputFiles('input[type="file"]', f.document.path);

    // AM-51 (owner, 2026-09-09): nothing to confirm and nothing to choose — no
    // type control, no knowledge-source control. The upload runs through to the
    // workspace; the engine measures the document by its content.
    await expect(page.locator(".ws-intake").getByRole("combobox")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Confirm/ })).toHaveCount(0);

    // One act lands in the workspace with the document THERE — mounted and one
    // disclosure away, never an empty-record detour and never "No document
    // uploaded yet". Since 2026-09-08 the workspace opens on the analysis, so
    // the document is disclosed rather than already filling the screen.
    await page.waitForURL(/\/dashboard\?id=[0-9a-f-]{36}$/, { timeout: 30_000 });
    await showDocument(page);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
    // No type was declared (no generation credential in e2e, no question asked),
    // and nothing pretends one was: the header carries no type chip (AM-51).
    await expect(page.locator(".ws-context")).not.toContainText(/\b(MSA|NDA|TOS|SLA)\b/);
  });
});

test.describe("the Findings pane, slice 2", () => {
  test.use({ storageState: storageStatePath("counsel") });

  test("findings render with axis chips, and an evidence link highlights the document", async ({
    page,
  }) => {
    const { reviewId, contractId } = await createAnalysedReview(page);
    const findingsResp = await page.request.get(`/api/v1/reviews/${reviewId}/findings`);
    const findings = (await findingsResp.json()).data;
    const target = findings[0].evaluations[0];

    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const pane = page.locator('[data-region="findings"]');
    await expect(pane.locator(".ws-finding").first()).toBeVisible();
    await expect(pane.locator(".ws-finding").first()).toContainText(findings[0].classification);

    if (target.evidence_refs.length > 0) {
      // 2026-08-31 v2 / seventh pass: the excerpt renders verbatim inside the
      // finding's "How this was determined", and its location button keeps the
      // highlight gesture into the document pane.
      await pane.locator(".ws-finding").first().locator(".ws-determined > summary").first().click();
      await expect(pane.locator(".ws-evidence__quote").first()).toBeVisible();
      const evidenceButton = pane.locator(".ws-evidence__loc").first();
      await evidenceButton.click();
      const lit = page.locator('[data-region="document"] .ws-row--lit');
      await expect(lit).toHaveCount(1);
      await expect(evidenceButton).toHaveAttribute("aria-current", "true");
    }
  });

  test("a decision records, and a 409 freezes the form until an explicit refresh", async ({
    page,
  }) => {
    const { reviewId, contractId } = await createAnalysedReview(page);
    const findingsResp = await page.request.get(`/api/v1/reviews/${reviewId}/findings`);
    const findings = (await findingsResp.json()).data;
    const evaluationId = findings[0].evaluations[0].id;

    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const evaluation = page.locator('[data-scope]').first();
    await expect(evaluation).toBeVisible();

    // Race the form with a decision made through the API directly.
    const csrf = decodeURIComponent(
      (await page.context().cookies()).find((c) => c.name === "legalmind_csrf")!.value,
    );
    const first = await page.request.post(`/api/v1/evaluations/${evaluationId}/decisions`, {
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      data: { decision_type: "ACCEPT_DEVIATION", justification: "STRUCTURAL — not a legal position (rule 21).", expected_version: 0 },
    });
    expect(first.status()).toBe(201);

    await evaluation.getByLabel("Justification (required)").fill("STRUCTURAL — not a legal position (rule 21).");
    await evaluation.getByRole("button", { name: "Record decision" }).click();

    await expect(evaluation.locator(".ws-decision__conflict")).toContainText("Not recorded");
    await expect(evaluation.getByRole("button", { name: "Record decision" })).toBeDisabled();

    await evaluation.getByRole("button", { name: "Refresh to see the latest decision" }).click();
    await expect(evaluation.locator(".ws-decision")).toContainText("version 1");
  });

  test("escalation is a quiet request, distinct from the decision control", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const finding = page.locator(".ws-finding").first();
    await expect(finding).toBeVisible();

    await finding.getByRole("button", { name: "Escalate for authorized review" }).click();
    await finding.getByPlaceholder("Why does this need authorized review?").fill("STRUCTURAL test escalation.");
    await finding.getByRole("button", { name: "Escalate", exact: true }).click();

    await expect(finding).toContainText("a request, not an approval");
    await expect(finding.getByRole("button", { name: "Withdraw" })).toBeVisible();
  });
});

test.describe("the Ask pane, slice 3", () => {
  // `AM-29` r4's constant as backend/legalmind/assist/state.py declares it — asserted
  // verbatim so a drift in either repository shows up as a wording mismatch.
  const REFUSAL_TEXT =
    "Information not found in the selected document. " +
    "The available material does not answer this question.";

  test("both refusal causes render the identical quiet sentence in the new pane", async ({ page }) => {
    // No Review needed — asking is not judging (`AM-25` r1). No generator credential
    // exists here (CI asserts none), so an ask that clears retrieval still cannot
    // generate: exactly production until the `AM-31` gate opens.
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);
    // Ask is a floating dock now (DD-15): a launcher, then a non-modal panel.
    // Every assertion below is unchanged — only the way the input is reached is.
    const question = await openAsk(page);
    const pane = page.locator(".ws-dock");
    const ask = askSend(page);

    // Cause 1 — retrieval hits the fixture sentence; no generator → EVIDENCE_INSUFFICIENT.
    await question.fill("liability shall not exceed fees paid");
    await ask.click();
    const first = pane.locator(".ws-ask__answer--refusal").first();
    await expect(first).toHaveText(REFUSAL_TEXT, { timeout: 20_000 });
    await expect(first).toHaveAttribute("data-state", "EVIDENCE_INSUFFICIENT");

    // Cause 2 — vocabulary the document cannot contain → NO_EVIDENCE_RETRIEVED.
    await question.fill("Explain the zorbulated quixotic framblewitz stipulations");
    await ask.click();
    const refusals = pane.locator(".ws-ask__answer--refusal");
    await expect(refusals).toHaveCount(2, { timeout: 20_000 });
    await expect(refusals.nth(1)).toHaveAttribute("data-state", "NO_EVIDENCE_RETRIEVED");
    expect(await refusals.nth(0).innerText()).toBe(await refusals.nth(1).innerText());

    // Quiet surface: no alert role inside a refusal; no confidence figure anywhere.
    await expect(pane.locator(".ws-ask__answer--refusal [role='alert']")).toHaveCount(0);
    expect((await page.locator("body").innerText()).toLowerCase()).not.toContain("confidence");
  });

  test("a compliance-shaped question is routed to Findings, not answered or refused", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);
    const question = await openAsk(page);
    const pane = page.locator(".ws-dock");
    await question.fill("Does this liability clause meet our company standard?");
    await askSend(page).click();
    const routed = pane.locator(".ws-ask__answer--routed");
    await expect(routed).toBeVisible({ timeout: 20_000 });
    await expect(routed).toContainText("Compared by the evaluator, not the assistant");
    await expect(pane.locator(".ws-ask__answer--refusal")).toHaveCount(0);
  });
});

test.describe("the 3-column redesign (2026-08-31)", () => {
  test("the Summary panel shows real counts, one way into the decisions, and honest obligations degradation", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);

    // The side card's DEFAULT tab (DD-9), labelled "Summary" since the
    // 2026-09-04 audit. It was "AI Analysis" until 2026-09-01 — the old label
    // credited a model for the one part of the product whose value is that no
    // model touched it (AI-01) — and plain "Analysis" until the audit, which
    // read as a second analysis beside "Findings" rather than as its summary.
    await expect(page.getByRole("tab", { name: "Summary", exact: true })).toHaveAttribute("aria-selected", "true");
    const panel = page.locator('[data-region="analysis"]');
    await expect(panel.locator(".ws-tiles")).toBeVisible();

    // The Summary speaks the reader's three words (owner, 2026-09-09, AM-50 r4 —
    // reversing the 2026-09-01 correction that pinned the engine's words here).
    // The engine vocabulary is unchanged underneath and lives in View details.
    const USER_WORDS = ["Accepted", "Needs review", "Not accepted", "Need legal decision"];
    const tileLabels = await panel.locator(".ws-tile__label").allTextContents();
    expect(tileLabels.length).toBeGreaterThan(0);
    for (const label of tileLabels) expect(USER_WORDS).toContain(label);
    for (const engineWord of ["DEVIATION", "MISSING", "UNABLE_TO_EVALUATE", "NEEDS A PERSON"]) {
      expect(await panel.innerText()).not.toContain(engineWord);
    }

    // The ring is real counts — a raw total in the center; the legend's
    // percentages are shares of those counts, never a grade or confidence.
    const ring = panel.locator(".ws-ring__svg");
    await expect(ring).toBeVisible();
    expect((await panel.locator(".ws-ring__total").textContent())?.trim()).toMatch(/^\d+$/);
    expect((await panel.innerText()).toLowerCase()).not.toContain("confidence");

    /*
     * Summary states HOW MANY findings need a decision and offers ONE way into
     * them — it no longer renders a card per finding beside a Findings tab that
     * opens on the very same set (2026-09-04 audit: the same question answered
     * twice in one panel). What must survive is the PATH, so it is asserted end
     * to end here: summary → the list → the passage lit in the document.
     */
    await expect(panel.getByText(/needs? a legal decision/)).toBeVisible();
    await expect(panel.locator(".ws-risk")).toHaveCount(0);
    await panel.getByRole("button", { name: /Open the list/ }).click();
    await expect(page.getByRole("tab", { name: "Findings", exact: true }))
      .toHaveAttribute("aria-selected", "true");
    // The list is the work surface: a finding's cited evidence is a button
    // labelled with the location itself (§ / title / page), and pressing it
    // lights that passage in the document pane.
    await page.locator('[data-region="findings"] .ws-finding').first()
      .locator(".ws-determined > summary").first().click();
    const cited = page.locator('[data-region="findings"] .ws-evidence__loc').first();
    await expect(cited).toBeVisible();
    await cited.click();
    await expect(page.locator(".ws-row--lit")).toBeVisible();

    // Back to Summary for the obligations assertion below.
    await page.getByRole("tab", { name: "Summary", exact: true }).click();

    // No generation credential in e2e: obligations degrade to the honest quiet
    // sentence — never an error banner, never fabricated content.
    await expect(panel.getByText("Obligations could not be extracted", { exact: false }))
      .toBeVisible({ timeout: 20_000 });
  });

  test("the outline carries DD-9 status markers derived from findings", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);
    await showDocument(page);

    // The fixture analysis yields a DEVIATION, so at least one outline row is
    // marked needs-review. Every marker is one of the three DD-9 buckets and
    // carries an accessible name — never color alone.
    const review = page.locator(".ws-outline .ws-status--review").first();
    await expect(review).toBeVisible();
    await expect(review).toHaveAttribute("aria-label", /review/i);
    const markers = page.locator(".ws-outline .ws-status");
    for (const cls of await markers.evaluateAll((els) => els.map((e) => e.className))) {
      expect(cls).toMatch(/ws-status--(match|review|missing)/);
    }
  });

  test("Ask stays reachable at the bottom of a scrolled document", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 700 });
    await page.goto(`/dashboard?id=${contractId}`);
    await showDocument(page);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();

    // Scroll the document pane to its end — Ask must still be reachable without
    // scrolling back (the 2026-08-31 complaint, which DD-15 must not regress).
    // The dock is anchored to the workspace, not to the document's scroller, so
    // it is in the same place at the end as at the start.
    await page.locator('[data-region="document"] .ws-pane__body, [data-region="document"] .ws-text').first()
      .evaluate((el) => { el.scrollTop = el.scrollHeight; });
    const launcher = page.getByRole("button", { name: /Ask about this document/i });
    await expect(launcher).toBeVisible();
    const input = await openAsk(page);
    await input.click();
    await expect(input).toBeFocused();
  });
});

test.describe("collapse behavior", () => {
  test("narrow viewports keep every region reachable as a tab, and Ask stays a floating dock", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 800, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);

    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(3);
    await expect(page.getByRole("tab", { name: "Document" })).toBeVisible();

    await page.getByRole("tab", { name: "Summary", exact: true }).click();
    await expect(page.locator('[data-region="analysis"]')).toBeVisible();
    await expect(page.locator('[data-region="document"]')).toHaveCount(0);

    // Ask is not a tab, and it never became one: the launcher is mounted on
    // EVERY tab and at every breakpoint (owner brief, 2026-08-31, preserved by
    // DD-15 — what changed is that it costs no height, not that it hides).
    const launcher = page.getByRole("button", { name: /Ask about this document/i });
    await expect(launcher).toBeVisible();
    await page.getByRole("tab", { name: "Findings" }).click();
    await expect(launcher).toBeVisible();
    // And it opens from here, on this tab, without changing tabs.
    await expect(await openAsk(page)).toBeVisible();
    await page.keyboard.press("Escape");

    // Arrow keys move between tabs — the collapsed state is keyboard-operable.
    await page.getByRole("tab", { name: "Summary", exact: true }).focus();
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Findings" })).toBeFocused();
    await expect(page.locator('[data-region="findings"]')).toBeVisible();
  });

  test("the skip link is first in the tab order and lands on the content", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await expect(page.locator(".ws-shell")).toBeVisible();

    // First tabbable element in DOM order is the skip link — headless Chromium
    // does not move focus off <body> on the very first synthetic Tab, so the tab
    // order is asserted structurally and the link's behavior is exercised directly.
    const first = page.locator('a[href], button, [tabindex]:not([tabindex="-1"])').first();
    await expect(first).toHaveClass(/ws-skip/);

    const skip = page.getByRole("link", { name: "Skip to content" });
    await skip.focus();
    await expect(skip).toBeFocused();
    await skip.press("Enter");
    await expect(page).toHaveURL(/#ws-main$/);
    await expect(page.locator("#ws-main")).toBeFocused();
  });
});

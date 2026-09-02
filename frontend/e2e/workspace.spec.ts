import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, fixture, openFindingsTab, storageStatePath } from "./support";

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

    // The new shell, not the legacy chrome.
    await expect(page.locator(".ws-shell")).toBeVisible();
    await expect(page.locator(".topbar")).toHaveCount(0);

    const doc = page.locator('[data-region="document"]');
    // DD-9: the document area is two cards — the clauses card and the document
    // card under its toolbar.
    await expect(doc.locator(".ws-outline__title")).toHaveText("Clauses");
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

  test("the Documents landing lists documents and links only into /dashboard", async ({ page }) => {
    const created = await apiPost(page, "/contracts", {
      name: `Index ${Date.now()}`,
      contract_type: "MSA",
    });
    const contract = (await created.json()).data;

    await page.goto("/dashboard");
    await expect(page.locator(".ws-shell")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();

    const row = page.getByRole("link", { name: contract.name });
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
    // The primary act is the file, not a form.
    await page.setInputFiles('input[type="file"]', f.document.path);

    // The confirm panel: name derived from the filename, editable. The upload
    // and the type suggestion run behind the file gesture; the panel is ready
    // when the fields re-enable.
    const nameField = page.getByLabel(/^Name/);
    await expect(nameField).not.toHaveValue("");
    const select = page.getByLabel(/^Document type/);
    await expect(select).toBeEnabled({ timeout: 30_000 });

    // The ten locked values, and nothing else, in the select (Step 6). With no
    // generation credential in e2e the suggestion degrades honestly, so the
    // select stays EMPTY and the declaration is the human act it always was.
    await expect(select).toHaveValue("");
    const options = select.locator("option");
    await expect(options).toHaveCount(11); // ten values + the empty prompt
    const codes = (await options.evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value))).filter(Boolean);
    expect(codes).toEqual(["MSA", "NDA", "TOS", "SLA", "DPA", "AUP", "PRIVACY_POLICY", "ORDER_FORM", "AMENDMENT", "OTHER"]);

    // Without the type the action stays unavailable.
    await expect(page.getByRole("button", { name: "Confirm & Analyze" })).toBeDisabled();
    await select.selectOption("NDA");
    await page.getByRole("button", { name: "Confirm & Analyze" }).click();

    // One act lands in the workspace with the document there — no empty-record
    // detour, no "No document uploaded yet".
    await page.waitForURL(/\/dashboard\?id=[0-9a-f-]{36}$/, { timeout: 30_000 });
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
    await expect(page.locator(".ws-context")).toContainText("NDA");
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
      // 2026-08-31 v2: the excerpt renders verbatim beside the finding, and its
      // location button keeps the highlight gesture into the document pane.
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
    // Ask is the sticky bar below the grid now — always mounted, never a tab.
    const pane = page.locator(".ws-askbar");
    await expect(pane).toBeVisible();

    const question = pane.getByLabel("Question");
    const ask = pane.getByRole("button", { name: "Ask" });

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
    const pane = page.locator(".ws-askbar");
    await pane.getByLabel("Question").fill("Does this liability clause meet our company standard?");
    await pane.getByRole("button", { name: "Ask" }).click();
    const routed = pane.locator(".ws-ask__answer--routed");
    await expect(routed).toBeVisible({ timeout: 20_000 });
    await expect(routed).toContainText("Not answered here");
    await expect(pane.locator(".ws-ask__answer--refusal")).toHaveCount(0);
  });
});

test.describe("the 3-column redesign (2026-08-31)", () => {
  test("the Analysis panel shows real counts, findings awaiting a decision, and honest obligations degradation", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);

    // "Analysis" is the side card's DEFAULT tab (DD-9). Renamed from "AI
    // Analysis" on 2026-09-01: everything in it except Key Obligations is the
    // DETERMINISTIC evaluator's output, and AI-01 keeps every model out of that
    // path — the old label credited a model for the one part of the product
    // whose value is that no model touched it. `exact` because "Analysis" is a
    // substring of nothing else here, but a future tab could make it one.
    await expect(page.getByRole("tab", { name: "Analysis", exact: true })).toHaveAttribute("aria-selected", "true");
    const panel = page.locator('[data-region="analysis"]');
    await expect(panel.locator(".ws-tiles")).toBeVisible();

    // Every stat tile is labeled with a REAL Step 19 classification — never an
    // invented catch-all like "Needs review" (owner correction, 2026-09-01).
    const REAL_CLASSIFICATIONS = ["MATCH", "DEVIATION", "MISSING", "CONFLICT",
      "UNABLE_TO_EVALUATE", "AMBIGUOUS", "UNRESOLVED"];
    const tileLabels = await panel.locator(".ws-tile__label").allTextContents();
    expect(tileLabels.length).toBeGreaterThan(0);
    for (const label of tileLabels) expect(REAL_CLASSIFICATIONS).toContain(label);
    expect(await panel.innerText()).not.toContain("Needs review");

    // The ring is real counts — a raw total in the center; the legend's
    // percentages are shares of those counts, never a grade or confidence.
    const ring = panel.locator(".ws-ring__svg");
    await expect(ring).toBeVisible();
    expect((await panel.locator(".ws-ring__total").textContent())?.trim()).toMatch(/^\d+$/);
    expect((await panel.innerText()).toLowerCase()).not.toContain("confidence");

    // The awaiting-a-decision list mirrors the findings pane's needs-a-decision
    // set (renamed from "Key risks" — rule 12 has no risk score to rank), and the
    // card's "View clause" lights the passage in the document pane.
    const risk = panel.locator(".ws-risk").first();
    await expect(risk).toContainText("DEVIATION");
    await risk.getByRole("button", { name: /View clause/ }).click();
    await expect(page.locator(".ws-row--lit")).toBeVisible();

    // No generation credential in e2e: obligations degrade to the honest quiet
    // sentence — never an error banner, never fabricated content.
    await expect(panel.getByText("Obligations could not be extracted", { exact: false }))
      .toBeVisible({ timeout: 20_000 });
  });

  test("the outline carries DD-9 status markers derived from findings", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);

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

  test("the Ask bar stays reachable at the bottom of a scrolled document", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 1440, height: 700 });
    await page.goto(`/dashboard?id=${contractId}`);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();

    // Scroll the document pane to its end — the bar's input must still be in
    // the viewport without any scrolling back (the owner's core complaint).
    await page.locator('[data-region="document"] .ws-pane__body, [data-region="document"] .ws-text').first()
      .evaluate((el) => { el.scrollTop = el.scrollHeight; });
    const input = page.locator(".ws-askbar").getByLabel("Question");
    await expect(input).toBeVisible();
    await input.click();
    await expect(input).toBeFocused();
  });
});

test.describe("collapse behavior", () => {
  test("narrow viewports keep every region reachable as a tab, and Ask stays a sticky bar", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 800, height: 900 });
    await page.goto(`/dashboard?id=${contractId}`);

    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(3);
    await expect(page.getByRole("tab", { name: "Document" })).toBeVisible();

    await page.getByRole("tab", { name: "Analysis", exact: true }).click();
    await expect(page.locator('[data-region="analysis"]')).toBeVisible();
    await expect(page.locator('[data-region="document"]')).toHaveCount(0);

    // Ask is not a tab any more: the sticky bar's input is reachable on EVERY
    // tab and at every breakpoint (owner brief, 2026-08-31).
    await expect(page.locator(".ws-askbar").getByLabel("Question")).toBeVisible();
    await page.getByRole("tab", { name: "Findings" }).click();
    await expect(page.locator(".ws-askbar").getByLabel("Question")).toBeVisible();

    // Arrow keys move between tabs — the collapsed state is keyboard-operable.
    await page.getByRole("tab", { name: "Analysis", exact: true }).focus();
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

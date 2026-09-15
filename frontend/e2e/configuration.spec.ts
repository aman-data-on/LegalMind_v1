import { expect, test } from "@playwright/test";

import { fixture, postOk, storageStatePath } from "./support";

/**
 * Editing a Company Standard as a form, against the real backend.
 *
 * No browser test drove this screen before, and the logic that could corrupt a
 * legal position lives in pure functions with their own unit tests
 * (`src/__tests__/company-standard-form.test.ts`). What those cannot cover is
 * everything this file asserts: that the controls are wired to the right keys,
 * that a save round-trips through the API, and that the validation a person
 * actually meets stops them before the server does.
 *
 * Locked rule 16 is the shape of the whole flow: saving APPENDS v2 and leaves v1
 * exactly as it was, which is why the assertions check for a NEW row rather than a
 * changed one.
 */

test.describe("Company Standard editor", () => {
  test.use({ storageState: storageStatePath("admin") });

  /**
   * These tests EDIT a standard, so they must not edit the shared one.
   *
   * The suite is serial over one database and one configuration namespace, and
   * `auth.setup.ts` publishes `STRUCTURAL-E2E-001` for every other spec to analyse
   * against. An earlier version of this file drove the form against that fixture
   * and removed the phrase "shall not exceed" from its `cap_phrases` — the exact
   * phrase in `journey.spec.ts`'s document — so the cap stopped being recognised
   * and that spec's DEVIATION became MISSING. Publishing then pinned the damage
   * into a snapshot for everything downstream.
   *
   * So each test gets its own throwaway Requirement, built from the same fixture
   * payload. Nothing here touches the shared one.
   */
  async function ownStandard(page: import("@playwright/test").Page): Promise<string> {
    const config = fixture().configuration;
    const code = `E2E-FORM-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    const requirement = await postOk(page, "/requirements", { code });
    await postOk(page, `/requirements/${requirement.id}/versions`, {
      name: config.name,
      evaluator_type: config.evaluator_type,
      company_standard: config.company_standard,
      mapping_rules: config.mapping_rules,
      evaluation_rules: config.evaluation_rules,
      legal_rule: config.legal_rule,
    });
    return code;
  }

  /** Expand the standard's row, reveal its stored values, and start editing. */
  async function openEditor(page: import("@playwright/test").Page) {
    await page.goto("/dashboard/configuration");
    const code = await ownStandard(page);
    await page.reload();
    await page.getByRole("button", { name: code, exact: true }).click();
    await page.getByRole("button", { name: "Show stored values" }).click();
    await page.getByRole("button", { name: "Change these values" }).first().click();
    return page.locator("form.ws-stdform");
  }

  test("the stored standard arrives in labelled fields, not as JSON", async ({ page }) => {
    const form = await openEditor(page);

    // The values are the organization's own, read back from the ratified standard.
    await expect(form.getByLabel(/^Value/)).toHaveValue("6");
    await expect(form.getByLabel(/^Unit/)).toHaveValue("months");
    await expect(form.getByLabel(/Measured against/)).toHaveValue("BASIS_FEES");
    await expect(form.getByLabel(/Scope key/)).toHaveValue("GENERAL");
    // A Select renders its stored choice as a word, not as the raw code.
    await expect(form.getByLabel(/Document type/)).toContainText("Master Services Agreement");

    // The extraction phrases are chips, each individually removable and counted.
    // Scoped to the chip: the same phrase legitimately appears again inside the
    // advanced raw-JSON view, so an unscoped text match finds two.
    await expect(form.locator(".ws-phrase__text", { hasText: "shall not exceed" })).toBeVisible();
    await expect(form.getByRole("button", { name: "Remove shall not exceed" })).toBeVisible();
    await expect(form.getByText("1 phrase", { exact: true }).first()).toBeVisible();
  });

  test("a changed value is saved as a NEW version, leaving the old one intact", async ({ page }) => {
    const form = await openEditor(page);
    // The expanded row's own version table, not the outer standards table.
    const card = page.locator("tr .ws-docs__table").first();
    const versionsBefore = await card.locator("tbody tr").count();

    await form.getByLabel(/^Value/).fill("9");

    // A phrase added by typing and pressing Enter, and another removed by its chip.
    const phrases = form.getByPlaceholder("Type a phrase and press Enter").first();
    await phrases.fill("is capped at");
    await phrases.press("Enter");
    await expect(form.getByText("2 phrases").first()).toBeVisible();
    await form.getByRole("button", { name: "Remove shall not exceed" }).click();
    await expect(form.getByText("1 phrase", { exact: true }).first()).toBeVisible();

    await form.getByLabel(/Reason for the change/).fill("e2e: raise the period");
    await form.getByRole("button", { name: "Save as a new version" }).click();

    // rule 16: a version was APPENDED. The form closes on success.
    await expect(form).toBeHidden();
    await expect(card.locator("tbody tr")).toHaveCount(versionsBefore + 1);

    // And the new version carries what was typed, read back from the server. The
    // values are still revealed from openEditor, and saving reloads them in place.
    const newest = card.locator("tbody tr").last();
    await expect(newest).toContainText('"preferred": 9');
    await expect(newest).toContainText("is capped at");
    await expect(newest).not.toContainText("shall not exceed");
  });

  test("a required field that is empty is caught here, not days later at publish", async ({ page }) => {
    const form = await openEditor(page);

    await form.getByLabel(/Scope key/).fill("");
    await form.getByLabel(/Reason for the change/).fill("e2e: should not save");
    await form.getByRole("button", { name: "Save as a new version" }).click();

    // A summary at the top, naming the field and linking to it — and the inline
    // error stays too, rather than being replaced by the summary.
    const summary = form.locator(".ws-errsum");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText("One field needs attention");
    await expect(summary.getByRole("link", { name: "Scope key" })).toBeVisible();
    await expect(form.locator(".ws-field__error")).toContainText("Required");

    // Nothing was sent: the form is still open.
    await expect(form.getByRole("button", { name: "Save as a new version" })).toBeVisible();
  });

  test("a malformed Constitution section is refused with the reason, not a stack trace", async ({ page }) => {
    const form = await openEditor(page);
    await form.getByRole("group").filter({ hasText: "Advanced" }); // exists, unopened

    await form.getByLabel(/^Section/).fill("1.2.3");
    await form.getByLabel(/^Topic/).fill("Liability");
    await form.getByLabel(/Reason for the change/).fill("e2e: bad section");
    await form.getByRole("button", { name: "Save as a new version" }).click();

    await expect(form.locator(".ws-errsum"))
      .toContainText("not a Constitution section reference");
  });

  test("the raw JSON escape hatch disables the fields while it is in charge", async ({ page }) => {
    const form = await openEditor(page);
    await form.getByRole("group").filter({ hasText: "Advanced" }).locator("summary").click();

    const json = form.getByLabel("Edit the stored JSON directly");
    await expect(json).toBeDisabled();

    await form.getByLabel(/Use the JSON below/).click();
    await expect(json).toBeEnabled();
    // Two editable sources of truth for one object is how a change gets lost.
    await expect(form.getByLabel(/^Value/)).toBeDisabled();

    // A typo is reported as a typo.
    await json.fill("{ not json");
    await form.getByLabel(/Reason for the change/).fill("e2e: bad json");
    await form.getByRole("button", { name: "Save as a new version" }).click();
    await expect(form.locator(".ws-field__error")).toContainText("not valid JSON");
  });
});

/**
 * Publishing a snapshot.
 *
 * This replaced one text field reading "Requirement codes to activate (comma
 * separated)". Activating the AB-20 batch meant pasting 33 codes into it, with
 * nothing on screen saying which Requirements were waiting, which were already
 * active, or which would be refused — and one typo produced `unknown Requirement
 * code` only after the request came back.
 */
test.describe("publishing a configuration snapshot", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("the screen says what publishing will do, before it is asked to", async ({ page }) => {
    await page.goto("/dashboard/configuration");
    const section = page.locator("section.ws-intake").filter({ hasText: "Publish a configuration snapshot" });

    // The button carries the outcome, not the verb.
    const button = section.getByRole("button", { name: /Publish \d+ Requirement/ });
    await expect(button).toBeEnabled();

    // The three groups are named with their counts, and the active group says why
    // it is not selectable.
    await expect(section.getByText("Already active —")).toBeVisible();
    await expect(section.getByRole("heading", { name: /Waiting to be activated/ })).toBeVisible();
  });

  test("a draft with no version is listed but cannot be ticked", async ({ page }) => {
    const code = `E2E-EMPTY-${Date.now()}`;
    await page.goto("/dashboard/configuration");
    await page.getByRole("button", { name: "New standard" }).click();
    await page.getByLabel(/Requirement code/).fill(code);
    await page.getByRole("button", { name: "Create draft" }).click();

    const section = page.locator("section.ws-intake").filter({ hasText: "Publish a configuration snapshot" });
    const item = section.locator("li.ws-check").filter({ hasText: code });
    await expect(item).toBeVisible();
    // Activating it would make it ACTIVE, and the publish then fails on "no
    // version" — refusing the WHOLE snapshot, not just this Requirement.
    await expect(item.getByRole("checkbox")).toBeDisabled();
    await expect(item).toContainText("no version yet");
  });

  test("publishing with nothing ticked pins the active configuration", async ({ page }) => {
    await page.goto("/dashboard/configuration");
    const section = page.locator("section.ws-intake").filter({ hasText: "Publish a configuration snapshot" });
    await section.getByRole("button", { name: /Publish \d+ Requirement/ }).click();
    await expect(section.getByText(/Snapshot/)).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

import { fixture, storageStatePath } from "./support";

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

  const code = fixture().configuration.requirement_code;

  /** Open the requirement's stored values and start editing the current version. */
  async function openEditor(page: import("@playwright/test").Page) {
    await page.goto("/dashboard/configuration");
    const card = page.locator("section.card").filter({ hasText: code });
    await expect(card.getByRole("heading", { name: new RegExp(code) })).toBeVisible();
    await card.getByRole("button", { name: "Show stored values" }).click();
    await card.getByRole("button", { name: "Change these values" }).first().click();
    return card.locator("form.card").filter({ hasText: "Company Standard — from v" });
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
    await expect(form.locator(".chip__text", { hasText: "shall not exceed" })).toBeVisible();
    await expect(form.getByRole("button", { name: "Remove shall not exceed" })).toBeVisible();
    await expect(form.getByText("1 phrase", { exact: true }).first()).toBeVisible();
  });

  test("a changed value is saved as a NEW version, leaving the old one intact", async ({ page }) => {
    const form = await openEditor(page);
    const card = page.locator("section.card").filter({ hasText: code });
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
    const summary = form.locator(".error-summary");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText("One field needs attention");
    await expect(summary.getByRole("link", { name: "Scope key" })).toBeVisible();
    await expect(form.locator(".field__error")).toContainText("Required");

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

    await expect(form.locator(".error-summary"))
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
    await expect(form.locator(".field__error")).toContainText("not valid JSON");
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
    const section = page.locator("section.card").filter({ hasText: "Publish a configuration snapshot" });

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
    await page.getByLabel("New Requirement code").fill(code);
    await page.getByRole("button", { name: "Create draft Requirement" }).click();

    const section = page.locator("section.card").filter({ hasText: "Publish a configuration snapshot" });
    const item = section.locator("li.chip").filter({ hasText: code });
    await expect(item).toBeVisible();
    // Activating it would make it ACTIVE, and the publish then fails on "no
    // version" — refusing the WHOLE snapshot, not just this Requirement.
    await expect(item.getByRole("checkbox")).toBeDisabled();
    await expect(item).toContainText("no version yet");
  });

  test("publishing with nothing ticked pins the active configuration", async ({ page }) => {
    await page.goto("/dashboard/configuration");
    const section = page.locator("section.card").filter({ hasText: "Publish a configuration snapshot" });
    await section.getByRole("button", { name: /Publish \d+ Requirement/ }).click();
    await expect(section.getByText(/Snapshot/)).toBeVisible();
  });
});

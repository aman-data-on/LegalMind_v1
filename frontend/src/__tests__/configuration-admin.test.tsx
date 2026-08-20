/**
 * Configuration admin read/write surface — locked rule 16, 52.4, LEGAL-02, rule 21.
 *
 * Two properties this screen must not lose:
 *
 * 1. **52.4 / LEGAL-02** — a version whose Legal Rule the response omitted renders
 *    with no marker of any kind. A dash, "hidden" or an empty labeled row would
 *    disclose that an internal legal position exists. Asserted against the real
 *    rendered markup, because the failure mode is visual.
 * 2. **Rule 16** — a Company Standard is changed by APPENDING a version. The API
 *    client must therefore expose no edit-in-place or delete affordance for a
 *    version; the only value-write path is the append-only standard endpoint.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ValueCell } from "@/app/configuration/page";
import { api } from "@/lib/api";
import type { RequirementVersion } from "@/lib/types";

/** As the LIST response delivers it: values are not included at all. */
const listed: RequirementVersion = {
  id: "rv1",
  version_number: 2,
  name: "Liability cap",
  description: null,
  evaluator_type: "NUMERIC_COMPARISON",
  created_at: "2026-08-19T10:00:00+00:00",
};

const standard = { document_type: "MSA", preferred: 6, unit: "MONTHS" };

/** As the DETAIL response delivers it to a caller permitted the legal position. */
const withLegalRule: RequirementVersion = {
  ...listed,
  created_by: "u1",
  company_standard: standard,
  legal_rule: { rule_type: "THRESHOLD", configuration: { scope_required: true } },
};

/** The same version where the Legal Rule was omitted — optional or withheld. */
const withoutLegalRule: RequirementVersion = {
  ...listed,
  created_by: "u1",
  company_standard: standard,
};

describe("52.4 — an omitted Legal Rule leaves no trace", () => {
  it("renders nothing where the response carried no legal_rule", () => {
    const html = renderToStaticMarkup(<ValueCell version={withoutLegalRule} />);

    // The stored standard IS shown — this is the admin read path, and the whole
    // reason values were added to the detail response.
    expect(html).toContain("MONTHS");
    // Nothing announces the absence of the Legal Rule.
    expect(html).not.toContain("THRESHOLD");
    expect(html).not.toContain("Legal Rule");
    expect(html).not.toContain("hidden");
    expect(html).not.toContain("—");
  });

  it("renders it for a caller who received it", () => {
    const html = renderToStaticMarkup(<ValueCell version={withLegalRule} />);
    expect(html).toContain("THRESHOLD");
    expect(html).toContain("scope_required");
  });

  it("leaves a withheld and a genuinely absent Legal Rule indistinguishable", () => {
    // The structural guarantee. Step 20 r4 makes a Legal Rule optional, so both
    // cases legitimately render as nothing — and because they render IDENTICALLY,
    // a viewer cannot infer that a position exists but was withheld.
    const withheld = renderToStaticMarkup(<ValueCell version={withoutLegalRule} />);
    const neverExisted = renderToStaticMarkup(
      <ValueCell version={{ ...listed, company_standard: standard }} />,
    );
    expect(withheld).toBe(neverExisted);
  });

  it("renders nothing at all for a version carrying no values", () => {
    // The list response's shape: no values, so no panel — not an empty box.
    expect(renderToStaticMarkup(<ValueCell version={listed} />)).toBe("");
  });
});

describe("rule 16 — values are changed by appending, never by editing", () => {
  it("exposes the append-only standard endpoint and no edit or delete path", () => {
    const surface = Object.keys(api);
    expect(surface).toContain("updateCompanyStandard");
    // No affordance that would modify or remove an existing version. Locked rule
    // 16 is what keeps a historical Review reproducible, and an API client helper
    // is the first place such a path would appear.
    expect(surface).not.toContain("editCompanyStandard");
    expect(surface).not.toContain("patchRequirementVersion");
    expect(surface).not.toContain("deleteRequirementVersion");
    expect(surface).not.toContain("deleteRequirement");
  });
});

/**
 * The Company Standard form's contract.
 *
 * Every assertion here guards a way the form could silently change the
 * organization's legal position — write a value nobody set, drop a key it does not
 * display, or suggest one. `vitest.config.ts` is `environment: "node"`, so form
 * behaviour is Playwright's job; this file covers the logic, which is exactly why
 * that logic was put in pure functions.
 */
import { describe, expect, it } from "vitest";

import {
  CONSTITUTION_BASES,
  DEFINITIONAL_UNIT_PAIRS,
  EMPTY_DRAFT,
  draftFromStandard,
  toStandard,
  unitPairKey,
  validateStandard,
  type StandardDraft,
} from "@/lib/companyStandard";

/** LIABILITY-MSA-001's stored shape, trimmed to what the assertions need. The
 *  unmodelled keys are real ones from that file, not invented padding. */
const STORED = {
  document_type: "MSA",
  constitution: {
    version: "L1.10",
    section: "9",
    topic: "Liability",
    basis: "STAKEHOLDER_CONFIRMED",
    expected_when: { confirmed_any: ["LIAB-EXCLUSIONS-MSA-001"] },
  },
  not_applicable_to: ["SLA"],
  preferred: 12,
  unit: "MONTHS",
  basis: "FEES_PAID",
  scope_key: "AGGREGATE",
  extraction: {
    cap_phrases: ["shall not exceed", "will not exceed"],
    unlimited_phrases: ["shall be unlimited"],
    units: { MONTHS: ["months", "month"], YEARS: ["years", "year"] },
    bases: { FEES_PAID: ["total fees paid"], FEES_PAID_FOR_AFFECTED_SERVICES: ["for the specific services"] },
    exceptions: [],
    general_scope: "AGGREGATE",
    composite_phrases: ["greater of"],
  },
  unit_conversions: [{ from_unit: "YEARS", to_unit: "MONTHS" }],
  _note: "a key no control on the form displays",
};

describe("draftFromStandard", () => {
  it("flattens a stored standard, nesting and all", () => {
    const draft = draftFromStandard(STORED);
    expect(draft.document_type).toBe("MSA");
    expect(draft.constitution_section).toBe("9");
    expect(draft.constitution_expected_when).toEqual(["LIAB-EXCLUSIONS-MSA-001"]);
    expect(draft.preferred).toBe("12"); // the number, as form text
    expect(draft.cap_phrases).toEqual(["shall not exceed", "will not exceed"]);
    expect(draft.unit_conversions).toEqual(["YEARS>MONTHS"]);
  });

  it("suggests nothing at all when there is no stored standard (rule 21)", () => {
    // The mechanical form of "a helpful-looking placeholder would become the
    // organization's legal position by accident". If this ever fails, the form
    // has started proposing legal content.
    const draft = draftFromStandard({});
    expect(draft).toEqual(EMPTY_DRAFT);
    for (const [key, value] of Object.entries(draft)) {
      expect(Array.isArray(value) ? value : [value].filter(Boolean),
        `${key} must start empty`).toEqual([]);
    }
  });

  it("survives a standard that is null, or the wrong shape entirely", () => {
    expect(draftFromStandard(null)).toEqual(EMPTY_DRAFT);
    expect(draftFromStandard({ constitution: "not an object", extraction: 7 }))
      .toEqual(EMPTY_DRAFT);
  });
});

describe("toStandard — the safety property", () => {
  it("leaves every key the form does not model byte-identical", () => {
    const out = toStandard(draftFromStandard(STORED), STORED);
    expect(out._note).toBe(STORED._note);
    expect(out.extraction).toMatchObject({
      units: STORED.extraction.units,
      bases: STORED.extraction.bases,
      exceptions: [],
      general_scope: "AGGREGATE",
      composite_phrases: ["greater of"],
    });
  });

  it("round-trips a real standard unchanged", () => {
    const out = toStandard(draftFromStandard(STORED), STORED);
    expect(out).toEqual(STORED);
  });

  it("round-trips through the draft in both directions", () => {
    const draft = draftFromStandard(STORED);
    expect(draftFromStandard(toStandard(draft, STORED))).toEqual(draft);
  });

  it("round-trips a PRESENCE standard, which carries no numeric half", () => {
    const presence = {
      document_type: "MSA",
      constitution: { version: "L1.10", section: "22", topic: "Governing Law", basis: "COMPANY_APPROVED" },
      expected_presence: "PRESENT",
      scope_key: "ARBITRATION",
      applicability: "REQUIRED",
    };
    expect(toStandard(draftFromStandard(presence), presence)).toEqual(presence);
  });
});

describe("toStandard — blank means absent, never empty string", () => {
  it("omits the key rather than writing \"\"", () => {
    const out = toStandard(EMPTY_DRAFT, {});
    expect("preferred" in out).toBe(false);
    expect("document_type" in out).toBe(false);
    expect("scope_key" in out).toBe(false);
    expect(out).toEqual({});
  });

  it("deletes a key when a previously-filled field is cleared", () => {
    // The alternative — "blank means leave alone" — would make deletion
    // impossible without dropping back to raw JSON.
    const draft: StandardDraft = { ...draftFromStandard(STORED), preferred: "", unit: "" };
    const out = toStandard(draft, STORED);
    expect("preferred" in out).toBe(false);
    expect("unit" in out).toBe(false);
    expect(out.basis).toBe("FEES_PAID"); // untouched neighbour
  });

  it("writes preferred as a number, never as text", () => {
    const out = toStandard({ ...EMPTY_DRAFT, preferred: " 30 " }, {});
    expect(out.preferred).toBe(30);
    expect(typeof out.preferred).toBe("number");
  });

  it("drops the constitution block entirely once its last field is cleared", () => {
    const emptied: StandardDraft = {
      ...draftFromStandard(STORED),
      constitution_version: "", constitution_section: "",
      constitution_topic: "", constitution_basis: "",
      constitution_expected_when: [],
    };
    expect("constitution" in toStandard(emptied, STORED)).toBe(false);
  });

  it("keeps the constitution block when only part of it is cleared", () => {
    const draft: StandardDraft = { ...draftFromStandard(STORED), constitution_section: "" };
    const out = toStandard(draft, STORED) as { constitution: Record<string, unknown> };
    expect("section" in out.constitution).toBe(false);
    expect(out.constitution.topic).toBe("Liability");
  });

  it("stores unit conversions in the shape the engine reads", () => {
    const out = toStandard({ ...EMPTY_DRAFT, unit_conversions: ["MONTHS>YEARS"] }, {});
    expect(out.unit_conversions).toEqual([{ from_unit: "MONTHS", to_unit: "YEARS" }]);
  });
});

describe("validateStandard", () => {
  const valid: StandardDraft = {
    ...EMPTY_DRAFT,
    document_type: "MSA",
    scope_key: "AGGREGATE",
    constitution_version: "L1.10",
    constitution_section: "9",
    constitution_topic: "Liability",
    constitution_basis: "STAKEHOLDER_CONFIRMED",
  };

  it("passes a well-formed draft", () => {
    expect(validateStandard(valid, STORED, "NUMERIC_COMPARISON")).toEqual({});
  });

  it("requires a document type, because the server refuses one without it", () => {
    expect(validateStandard({ ...valid, document_type: "" }, {}, "PRESENCE"))
      .toHaveProperty("document_type");
    expect(validateStandard({ ...valid, document_type: "CONTRACT" }, {}, "PRESENCE"))
      .toHaveProperty("document_type");
  });

  it("requires a scope key", () => {
    expect(validateStandard({ ...valid, scope_key: "  " }, {}, "PRESENCE"))
      .toHaveProperty("scope_key");
  });

  // --- the cases constitution_block_error refuses, mirrored ---
  it.each([
    ["9", true], ["17.2", true], ["31.6a", true], ["1", true],
    ["1.2.3", false], ["§9", false], ["nine", false], ["100", false],
  ])("section %s accepted=%s", (section, ok) => {
    const errors = validateStandard({ ...valid, constitution_section: section as string }, {}, "PRESENCE");
    expect("constitution_section" in errors).toBe(!ok);
  });

  it("requires a topic once the block exists", () => {
    expect(validateStandard({ ...valid, constitution_topic: "" }, {}, "PRESENCE"))
      .toHaveProperty("constitution_topic");
  });

  it("refuses a basis outside the seven", () => {
    expect(validateStandard({ ...valid, constitution_basis: "INVENTED" }, {}, "PRESENCE"))
      .toHaveProperty("constitution_basis");
  });

  it("allows a missing section only for DOCUMENT_ONLY and RETIRED", () => {
    const withoutSection = { ...valid, constitution_section: "" };
    expect(validateStandard(withoutSection, {}, "PRESENCE")).toHaveProperty("constitution_section");
    for (const basis of ["DOCUMENT_ONLY", "RETIRED"]) {
      expect(validateStandard({ ...withoutSection, constitution_basis: basis }, {}, "PRESENCE"))
        .toEqual({});
    }
  });

  it("says nothing about the constitution when the block is absent altogether", () => {
    // A pre-AM-59 snapshot legitimately carries none; the server tolerates that.
    const noBlock: StandardDraft = {
      ...EMPTY_DRAFT, document_type: "MSA", scope_key: "AGGREGATE",
    };
    expect(validateStandard(noBlock, {}, "PRESENCE")).toEqual({});
  });

  // --- the one check no layer performs today ---
  it("refuses a basis the standard's own extractor cannot recognise", () => {
    const errors = validateStandard({ ...valid, basis: "FEES_INVOICED" }, STORED, "NUMERIC_COMPARISON");
    expect(errors.basis).toMatch(/fail closed/);
  });

  it("accepts a basis that keys into extraction.bases", () => {
    expect(validateStandard({ ...valid, basis: "FEES_PAID" }, STORED, "NUMERIC_COMPARISON"))
      .toEqual({});
  });

  it("refuses a unit the standard's own extractor cannot recognise", () => {
    expect(validateStandard({ ...valid, unit: "FORTNIGHTS" }, STORED, "NUMERIC_COMPARISON"))
      .toHaveProperty("unit");
  });

  it("says nothing about basis when the standard declares no extraction map", () => {
    expect(validateStandard({ ...valid, basis: "ANYTHING" }, {}, "NUMERIC_COMPARISON")).toEqual({});
  });

  it("refuses a non-numeric preferred", () => {
    expect(validateStandard({ ...valid, preferred: "twelve" }, {}, "NUMERIC_COMPARISON"))
      .toHaveProperty("preferred");
  });

  it("refuses any unit conversion outside the four definitional pairs (AM-62)", () => {
    // DAYS<->MONTHS is the one someone will reach for, and the engine refuses it.
    expect(validateStandard({ ...valid, unit_conversions: ["DAYS>MONTHS"] }, {}, "NUMERIC_COMPARISON"))
      .toHaveProperty("unit_conversions");
    const allowed = DEFINITIONAL_UNIT_PAIRS.map(unitPairKey);
    expect(validateStandard({ ...valid, unit_conversions: allowed }, {}, "NUMERIC_COMPARISON"))
      .toEqual({});
  });
});

describe("the vocabularies the form offers", () => {
  it("offers exactly the seven recorded constitution bases", () => {
    expect(CONSTITUTION_BASES.map((b) => b.code).sort()).toEqual([
      "APPLICABLE_LAW", "COMPANY_APPROVED", "DOCUMENT_ONLY", "LEGALMIND_RULE",
      "NOT_ADOPTED", "RETIRED", "STAKEHOLDER_CONFIRMED",
    ]);
  });

  it("offers the four definitional conversions and never DAYS<->MONTHS", () => {
    expect(DEFINITIONAL_UNIT_PAIRS.map(unitPairKey).sort())
      .toEqual(["DAYS>WEEKS", "MONTHS>YEARS", "WEEKS>DAYS", "YEARS>MONTHS"]);
  });

  it("names no quantity anywhere — the form proposes no legal value (rule 21)", () => {
    // A label reading "e.g. 12 months" would be exactly the accident rule 21 names.
    const copy = [
      ...CONSTITUTION_BASES.map((b) => b.label),
      ...DEFINITIONAL_UNIT_PAIRS.map((p) => `${p.from} ${p.to}`),
    ].join(" ");
    expect(copy).not.toMatch(/\d+\s*(month|year|day|week|%)/i);
  });
});

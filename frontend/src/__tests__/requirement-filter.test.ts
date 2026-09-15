/**
 * Finding one standard among forty.
 *
 * A filter that silently drops a row on a legal-configuration screen is worse than
 * no filter: the reader concludes the standard does not exist. Every way this one
 * can hide something is asserted here.
 */
import { describe, expect, it } from "vitest";

import { ACTIVE, DEPRECATED, DRAFT } from "@/lib/publishPlan";
import {
  ANY, NO_FILTERS, STATUS_LABELS, filterRequirements, isFiltered, latestVersion, statusLabel,
} from "@/lib/requirementFilter";
import type { Requirement, RequirementVersion } from "@/lib/types";

function version(n: number, name: string, evaluator: string): RequirementVersion {
  return {
    id: `v${n}`, version_number: n, name, description: null,
    evaluator_type: evaluator, created_at: `2026-09-0${n}T10:00:00Z`,
  };
}

function requirement(code: string, status: string, versions: RequirementVersion[]): Requirement {
  return { id: code, code, status, versions, created_at: null };
}

const LIABILITY = requirement("LIABILITY-MSA-001", ACTIVE, [
  version(1, "Liability cap", "NUMERIC_COMPARISON"),
  version(2, "Liability cap", "NUMERIC_COMPARISON"),
]);
const ARBITRATION = requirement("ARBITRATION-MSA-001", ACTIVE, [
  version(1, "Arbitration clause", "PRESENCE"),
]);
const DRAFT_ONE = requirement("NEW-TOS-001", DRAFT, []);
const RETIRED_ONE = requirement("OLD-NDA-001", DEPRECATED, [
  version(1, "Withdrawn", "PRESENCE"),
]);
const ALL = [LIABILITY, ARBITRATION, DRAFT_ONE, RETIRED_ONE];

describe("filterRequirements", () => {
  it("returns everything when nothing is set", () => {
    expect(filterRequirements(ALL, NO_FILTERS)).toHaveLength(4);
    expect(isFiltered(NO_FILTERS)).toBe(false);
  });

  it("matches the code, case-insensitively and on a fragment", () => {
    const found = filterRequirements(ALL, { ...NO_FILTERS, search: "liab" });
    expect(found.map((r) => r.code)).toEqual(["LIABILITY-MSA-001"]);
    expect(filterRequirements(ALL, { ...NO_FILTERS, search: "MSA" })).toHaveLength(2);
  });

  it("also matches a version name, because that is what a reader remembers", () => {
    const found = filterRequirements(ALL, { ...NO_FILTERS, search: "arbitration clause" });
    expect(found.map((r) => r.code)).toEqual(["ARBITRATION-MSA-001"]);
  });

  it("ignores surrounding whitespace rather than finding nothing", () => {
    expect(filterRequirements(ALL, { ...NO_FILTERS, search: "  liability  " })).toHaveLength(1);
    expect(filterRequirements(ALL, { ...NO_FILTERS, search: "   " })).toHaveLength(4);
  });

  it("filters by the Step 29 lifecycle", () => {
    expect(filterRequirements(ALL, { ...NO_FILTERS, status: ACTIVE })).toHaveLength(2);
    expect(filterRequirements(ALL, { ...NO_FILTERS, status: DRAFT })).toHaveLength(1);
    expect(filterRequirements(ALL, { ...NO_FILTERS, status: DEPRECATED })).toHaveLength(1);
  });

  it("finds a Requirement by ANY version's evaluator, not only the newest", () => {
    // A Requirement whose evaluator changed between versions is still legitimately
    // found by either — filtering on the newest alone would hide its own history.
    const changed = requirement("CHANGED-001", ACTIVE, [
      version(1, "was presence", "PRESENCE"),
      version(2, "now numeric", "NUMERIC_COMPARISON"),
    ]);
    const list = [changed];
    expect(filterRequirements(list, { ...NO_FILTERS, evaluator: "PRESENCE" })).toHaveLength(1);
    expect(filterRequirements(list, { ...NO_FILTERS, evaluator: "NUMERIC_COMPARISON" })).toHaveLength(1);
  });

  it("combines every filter", () => {
    const found = filterRequirements(ALL, { search: "MSA", status: ACTIVE, evaluator: "PRESENCE" });
    expect(found.map((r) => r.code)).toEqual(["ARBITRATION-MSA-001"]);
  });

  it("never hides a Requirement that has no version", () => {
    // A draft with no version is exactly the one someone is looking for.
    expect(filterRequirements(ALL, { ...NO_FILTERS, search: "NEW-TOS" })).toHaveLength(1);
  });

  it("survives the list not having loaded", () => {
    expect(filterRequirements(null, NO_FILTERS)).toEqual([]);
  });
});

describe("the words the screen uses", () => {
  it("calls DEPRECATED 'Retired', the same as the publish screen and AM-65", () => {
    expect(statusLabel(DEPRECATED)).toBe("Retired");
    expect(statusLabel(DRAFT)).toBe("Draft");
    expect(statusLabel(ACTIVE)).toBe("Active");
  });

  it("passes an unknown status through rather than inventing a word for it", () => {
    expect(statusLabel("SOMETHING_ELSE")).toBe("SOMETHING_ELSE");
  });

  it("offers exactly the three lifecycle states as filter options", () => {
    expect(STATUS_LABELS.map((s) => s.code)).toEqual([DRAFT, ACTIVE, DEPRECATED]);
  });
});

describe("latestVersion", () => {
  it("is the newest, which is the one the row describes", () => {
    expect(latestVersion(LIABILITY)?.version_number).toBe(2);
  });

  it("is null when there is none, so the row shows an em dash rather than crashing", () => {
    expect(latestVersion(DRAFT_ONE)).toBeNull();
  });
});

describe("isFiltered", () => {
  it("is true for each constraint on its own", () => {
    expect(isFiltered({ ...NO_FILTERS, search: "x" })).toBe(true);
    expect(isFiltered({ ...NO_FILTERS, status: ACTIVE })).toBe(true);
    expect(isFiltered({ ...NO_FILTERS, evaluator: "PRESENCE" })).toBe(true);
    expect(isFiltered({ search: ANY, status: ANY, evaluator: ANY })).toBe(false);
  });
});

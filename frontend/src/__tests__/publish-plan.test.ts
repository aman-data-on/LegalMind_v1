/**
 * What the publish screen promises, before anything is sent.
 *
 * The screen's whole job here is to say in advance what
 * `POST /configuration/publish` will do. A count or a button label that is quietly
 * wrong is worse than the text field it replaces, because it looks authoritative —
 * so every number and every word the button can say is asserted here.
 */
import { describe, expect, it } from "vitest";

import { ACTIVE, DEPRECATED, DRAFT, publishPlan } from "@/lib/publishPlan";
import type { Requirement, RequirementVersion } from "@/lib/types";

const version: RequirementVersion = {
  id: "v1", version_number: 1, name: "n", description: null,
  evaluator_type: "NUMERIC_COMPARISON", created_at: null,
};

function requirement(code: string, status: string, versions = [version]): Requirement {
  return { id: code, code, status, versions, created_at: null };
}

/** The live shape after AB-20: 33 active, 7 retired, nothing in draft. */
const LIVE = [
  ...Array.from({ length: 33 }, (_, i) => requirement(`ACT-${i}`, ACTIVE)),
  ...Array.from({ length: 7 }, (_, i) => requirement(`OLD-${i}`, DEPRECATED)),
];

describe("publishPlan", () => {
  it("groups by the Step 29 lifecycle", () => {
    const plan = publishPlan([...LIVE, requirement("NEW-1", DRAFT)], []);
    expect(plan.active).toHaveLength(33);
    expect(plan.retired).toHaveLength(7);
    expect(plan.drafts).toHaveLength(1);
  });

  it("says what will happen when nothing is ticked", () => {
    const plan = publishPlan(LIVE, []);
    expect(plan.willPin).toBe(33);
    expect(plan.action).toBe("Publish 33 Requirements");
    expect(plan.blocked).toBeNull();
  });

  it("counts the ticked drafts into the snapshot, and says so", () => {
    const drafts = Array.from({ length: 8 }, (_, i) => requirement(`NEW-${i}`, DRAFT));
    const plan = publishPlan([...LIVE, ...drafts], drafts.map((d) => d.code));
    // This is the case the owner actually hit: 8 to activate, 25 already active.
    expect(plan.willPin).toBe(41);
    expect(plan.action).toBe("Activate 8 and publish 41 Requirements");
  });

  it("never lets a retired Requirement be selected (AM-65)", () => {
    // The server refuses it outright; the screen must not offer it at all.
    const plan = publishPlan(LIVE, ["OLD-0"]);
    expect(plan.selectable).not.toContain("OLD-0");
    expect(plan.willPin).toBe(33);
    expect(plan.action).toBe("Publish 33 Requirements");
  });

  it("never lets an already-active Requirement be ticked twice", () => {
    const plan = publishPlan(LIVE, ["ACT-0"]);
    expect(plan.selectable).toEqual([]);
    expect(plan.willPin).toBe(33); // not 34
  });

  it("refuses a draft with no version, because it would fail the WHOLE publish", () => {
    // Activating it makes it ACTIVE, and the publish then fails on "no version"
    // and produces no snapshot at all — not a snapshot missing one Requirement.
    const empty = requirement("NEW-EMPTY", DRAFT, []);
    const plan = publishPlan([...LIVE, empty], ["NEW-EMPTY"]);
    expect(plan.versionless.map((r) => r.code)).toEqual(["NEW-EMPTY"]);
    expect(plan.selectable).toEqual([]);
    expect(plan.willPin).toBe(33);
  });

  it("blocks the button when the publish would be refused for having nothing", () => {
    // The server's own words: "nothing to publish: no Requirement is ACTIVE".
    const plan = publishPlan([requirement("NEW-1", DRAFT)], []);
    expect(plan.willPin).toBe(0);
    expect(plan.blocked).toMatch(/no Requirement is active/);
  });

  it("unblocks as soon as one draft is ticked", () => {
    const plan = publishPlan([requirement("NEW-1", DRAFT)], ["NEW-1"]);
    expect(plan.blocked).toBeNull();
    expect(plan.action).toBe("Activate 1 and publish 1 Requirement");
  });

  it("is singular for one Requirement and plural for none", () => {
    expect(publishPlan([requirement("A", ACTIVE)], []).action).toBe("Publish 1 Requirement");
    expect(publishPlan(LIVE, []).action).toBe("Publish 33 Requirements");
  });

  it("survives the list not having loaded yet", () => {
    const plan = publishPlan(null, []);
    expect(plan.willPin).toBe(0);
    expect(plan.drafts).toEqual([]);
    expect(plan.blocked).not.toBeNull();
  });
});

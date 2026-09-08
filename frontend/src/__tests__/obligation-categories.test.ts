/**
 * The Key Obligations accordion's pure layer (owner, 2026-09-08): the server's
 * verbatim party labels become a small set of plain-language rows, mutual
 * labels merge, "Neither Party" reads as the prohibition it is, and a named
 * role keeps its own words — no "our side / their side" is invented from a
 * role label the extraction never attributed to a side.
 */

import { describe, expect, it } from "vitest";

import { obligationCategories } from "@/components/workspace/model";

const g = (party_label: string, n: number) => ({
  party_label,
  items: Array.from({ length: n }, (_, i) => ({ id: `${party_label}-${i}` })),
});

describe("obligationCategories", () => {
  it("merges the mutual labels into one row and keeps the counts", () => {
    const categories = obligationCategories([g("Both Parties", 1), g("Parties", 2), g("Each Party", 1)]);
    expect(categories).toHaveLength(1);
    expect(categories[0]!.title).toBe("Both sides must");
    expect(categories[0]!.items).toHaveLength(4);
  });

  it("reads a prohibition as one, and orders mutual → role → prohibition", () => {
    const categories = obligationCategories([
      g("Neither Party", 1), g("Receiving Party", 6), g("Both Parties", 2),
    ]);
    expect(categories.map((c) => c.title)).toEqual([
      "Both sides must", "Receiving Party must", "Neither side can",
    ]);
    expect(categories.map((c) => c.items.length)).toEqual([2, 6, 1]);
  });

  it("keeps a named role's own words — never a guessed side", () => {
    const titles = obligationCategories([g("Customer", 1), g("Service Provider", 1)])
      .map((c) => c.title);
    expect(titles).toEqual(["Customer must", "Service Provider must"]);
    expect(titles.join(" ")).not.toMatch(/our|other party/i);
  });

  it("tolerates the label carrying its own 'obligations' suffix and stray spacing", () => {
    const categories = obligationCategories([g("  both   parties  obligations ", 1)]);
    expect(categories[0]!.title).toBe("Both sides must");
  });

  it("merges the casing and the article the documents actually use", () => {
    // Every one of these labels is present in the live extraction table.
    const categories = obligationCategories([
      g("Receiving Party", 6), g("receiving party", 4), g("The Receiving Party", 1),
      g("Customer", 2), g("customer", 1),
      g("Both parties", 2), g("Each party", 1), g("Either Party", 3), g("Party", 1),
    ]);
    expect(categories.map((c) => [c.title, c.items.length])).toEqual([
      ["Both sides must", 7], ["Receiving Party must", 11], ["Customer must", 3],
    ]);
  });

  it("starts a lower-case role label with a capital", () => {
    expect(obligationCategories([g("non-disclosing party", 1)])[0]!.title)
      .toBe("Non-disclosing party must");
  });

  it("drops an empty group and survives no groups at all", () => {
    expect(obligationCategories([g("Customer", 0)])).toEqual([]);
    expect(obligationCategories([])).toEqual([]);
  });
});

/**
 * CLM round 2 (design 11 §8 U2, U7, U8; `AM-308`/`AM-309`) — static render, house idiom.
 * Pins the words: what the final contract does to each change row, the template badge,
 * the amendment link and list, and the calm sentence for a missing amendment template.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));

import { AmendmentsPanel, GovernedByLink, amendmentError } from "@/components/workspace/Amendments";
import { ScBadge } from "@/components/templates/TemplateList";
import { ApiError } from "@/lib/api";
import { blockerText, finalLine } from "@/lib/package";

const t = { key: "K~8.5", number: "8.5", heading: null };

describe("U2: the final contract line on a change row", () => {
  it("says what happens in plain words, never a code", () => {
    expect(finalLine({ answer: null, target: t, in_package: "replace" })).toBe("Goes into Annexure A, replacing clause\u00a08.5");
    expect(finalLine({ answer: null, target: t, in_package: "delete" })).toBe("Goes into Annexure A, removing clause\u00a08.5");
    expect(finalLine({ answer: null, target: t, in_package: "insert" })).toBe("Goes into Annexure A as a new clause after\u00a08.5");
    expect(finalLine({ answer: null, target: null, in_package: "replace" })).toBe("Goes into Annexure A as a replacement");
    expect(finalLine({ answer: null, target: t, in_package: "cannot" })).toBe("Can’t be written into Annexure A as it is");
  });
  it("says 'not in the final contract' only once answered, and nothing without the fields", () => {
    const answer = { answer: "keep_ours" } as never;
    expect(finalLine({ answer, target: t, in_package: "none" })).toBe("Not in the final contract. Our wording stays");
    expect(finalLine({ answer: null, target: t, in_package: "none" })).toBeNull();
    expect(finalLine({ answer })).toBeNull();
  });
});

describe("U8: the template badge", () => {
  it("says set up or not set up, and is absent without the field", () => {
    expect(renderToStaticMarkup(<ScBadge readiness={{ ready: true, missing: [] }} />)).toContain("Annexure A set up");
    expect(renderToStaticMarkup(<ScBadge readiness={{ ready: false, missing: [] }} />)).toContain("Annexure A not set up");
    expect(renderToStaticMarkup(<ScBadge />)).toBe("");
  });
});

describe("U7: amendments", () => {
  it("an amendment names the contract it amends; absent otherwise", () => {
    const html = renderToStaticMarkup(<GovernedByLink contract={{ governed_by: { id: "p1", name: "Master Services Agreement", contract_type: "MSA" } }} />);
    expect(html).toContain("Amends");
    expect(html).toContain('href="/contracts/p1"');
    expect(renderToStaticMarkup(<GovernedByLink contract={{}} />)).toBe("");
  });
  it("lists the amendments with their state, and offers Start only when allowed", () => {
    const amendments = [{ id: "a1", name: "Amendment to MSA", status: "DRAFT", signed: false, archived: false },
                        { id: "a2", name: "Amendment 2", status: "DRAFT", signed: true, archived: false }];
    const html = renderToStaticMarkup(<AmendmentsPanel contract={{ id: "c", amendments }} canStart={false} />);
    expect(html).toContain("Being prepared");
    expect(html).toContain("Signed");
    expect(html).not.toContain("Start an amendment");
    expect(renderToStaticMarkup(<AmendmentsPanel contract={{ id: "c", amendments: [] }} canStart />)).toContain("Start an amendment");
    expect(renderToStaticMarkup(<AmendmentsPanel contract={{ id: "c", amendments: [] }} canStart={false} />)).toBe("");
  });
  it("a missing amendment template reads as a calm sentence, never the raw error", () => {
    const err = new ApiError(409, "NO_AMENDMENT_TEMPLATE", "No approved amendment template yet.", "r");
    expect(amendmentError(err)).toBe("No approved amendment template yet — Legal needs to approve one first.");
    expect(blockerText({ code: "NO_AMENDMENT_TEMPLATE", message: "No approved amendment template yet." }))
      .toBe("No approved amendment template yet — Legal needs to approve one first.");
    expect(amendmentError(new ApiError(409, "CONFLICT", "only a signed contract is amended", "r")))
      .toBe("Only a signed contract is amended.");
  });
});

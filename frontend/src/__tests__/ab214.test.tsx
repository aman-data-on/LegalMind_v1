/** AB-214: the lawyer's contract-decision step (AM-413), the final dialog's words by mode,
 *  the annexure's own name on the template page, and the texts only Legal writes (AM-412). */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SpecialConditionsSetup } from "@/components/templates/TemplateApproval";
import { LegalText } from "@/components/templates/TemplateLegalText";
import { finalPlanText } from "@/lib/labels";
import { nextStep } from "@/lib/nextStep";
import type { TemplateDetail } from "@/lib/templates";

const legal = { viewer: "legal" as const, canAnswer: false };

describe("AM-413: the contract decision is the lawyer's step", () => {
  it("offers Record the decision when the server says it is due, after any points", () => {
    const due = { points_open: 0, points_for_me: 0, decision_for_me: true, sent_to_legal: true };
    expect(nextStep({ ...legal, stage: "INTERNAL_REVIEW", counts: due }))
      .toEqual({ kind: "recordDecision", label: "Record the decision" });
    expect(nextStep({ ...legal, stage: "INTERNAL_REVIEW", counts: { ...due, points_for_me: 2 } })?.kind).toBe("decide");
    expect(nextStep({ ...legal, stage: "INTERNAL_REVIEW", counts: { ...due, decision_for_me: false } })).toBeNull();
    expect(nextStep({ ...legal, stage: "FINAL", counts: due })).toBeNull();
    // never the deal owner's step
    expect(nextStep({ viewer: "owner", canAnswer: true, stage: "INTERNAL_REVIEW", counts: due })).toBeNull();
  });
});

describe("AM-413: Prepare final contract says what it makes", () => {
  it("never calls an Annexure 2 final a clean copy", () => {
    const annex = finalPlanText({ mode: "annex", agreed: [], entries: [1, 2], annex: 2 }, 5);
    expect(annex).toContain("the 2 agreed changes listed in Annexure 2");
    expect(annex).toContain("Nothing in the body is edited");
    expect(annex).not.toContain("clean copy");
    expect(finalPlanText({ mode: "annex", agreed: [], entries: [1] }, 5)).toContain("the 1 agreed change listed in Annexure A");
    expect(finalPlanText({ mode: "copy", of_version: 3, agreed: [] }, 4)).toContain("a clean copy of version 3");
  });
});

describe("AM-413: the template page uses the contract's own annexure name", () => {
  it("says Annexure 2 where the contract does, Annexure A elsewhere", () => {
    const missing = [{ code: "FRAME_NOT_APPROVED", detail: "x" }];
    const two = renderToStaticMarkup(<SpecialConditionsSetup two readiness={{ ready: false, missing }} />);
    expect(two).toContain("Agreed Amendments (Annexure 2)");
    expect(two).not.toContain("Annexure A");
    expect(renderToStaticMarkup(<SpecialConditionsSetup readiness={{ ready: false, missing }} />)).toContain("Annexure A");
  });
});

describe("AM-412: the texts only Legal can write", () => {
  const detail = (legal_text: TemplateDetail["legal_text"]) => ({ id: "t", legal_text }) as TemplateDetail;
  const none = async () => {};
  it("starts empty, suggests nothing, and says it is optional — never that a final is blocked", () => {
    const html = renderToStaticMarkup(<LegalText onDone={none} onSelect={() => {}} detail={detail([
      { which: "annexure_1", clause_key: "A", supplied: false, text: null, approved: false, editable: true },
      { which: "precedence", clause_key: "F", supplied: false, text: null, approved: false, editable: true }])} />);
    expect(html).toContain("Optional: Legal can add wording here");
    expect(html).toContain("A final contract can be prepared without it");
    expect(html).not.toMatch(/blocked|until Legal/);
    expect(html.match(/<textarea[^>]*><\/textarea>/g)).toHaveLength(2);     // empty
    expect(html).not.toContain("placeholder=");
    expect(html).toContain("LegalMind does not write or suggest these words");
  });
  it("shows what Legal saved and that it still needs approval; nothing without a place", () => {
    const html = renderToStaticMarkup(<LegalText onDone={none} onSelect={() => {}} detail={detail([
      { which: "precedence", clause_key: "F", supplied: true, text: "Typed by Legal", approved: false, editable: true }])} />);
    expect(html).toContain("Typed by Legal");
    expect(html).toContain("Not approved yet");
    expect(html).toContain("Open the clause");
    expect(renderToStaticMarkup(<LegalText onDone={none} onSelect={() => {}} detail={detail([])} />)).toBe("");
  });
});

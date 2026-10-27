/**
 * The ⚖️ Legal / 💼 Business angles and the counter-proposal card (`AM-152`) — static
 * render, house idiom. The server builds every word; these pin how it is shown.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  BusinessAngleView, CounterProposalCard, LegalAngleView,
} from "@/components/workspace/Angles";
import type { ReviewAngles } from "@/lib/types";

const MOU: ReviewAngles = {
  commercial: {
    fee_per_month: 757000, fee_text: "Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month",
    term_months: 12, term_text: "Contract Agreement: 1 Year",
    committed_value: 9084000, committed_value_text: "₹90,84,000", excludes_gst: true,
  },
  business: [],
  top_risks: [{
    finding_id: "f-1", requirement_code: "EARLY-TERM-RESTRICTION-MSA-001",
    headline: "No exit charge on a fixed-term contract",
    body: "The customer can leave before the 12-month term ends without paying for the rest of the term, on 15 days' notice.",
    money: "Up to ₹90,84,000 of committed fees is not secured (₹7,57,000 a month for 12 months, excluding GST).",
    rupees: 9084000, where: "§13 · Service Termination · page 2",
  }],
  legal: { actionable: 10, matching: 5 },
  counter_proposals: {},
};
MOU.business = MOU.top_risks;

describe("the business angle (AM-152)", () => {
  it("leads with the money the contract commits and the risk that costs the most", () => {
    const html = renderToStaticMarkup(<BusinessAngleView angles={MOU} />);
    // owner, 2026-10-21: the Summary's money only — every point is in Open points once
    expect(html).toContain("Money");
    expect(html).toContain("commits <strong>₹90,84,000</strong> of fees over 12 months");
    expect(html).toContain("No exit charge on a fixed-term contract");
    expect(html).toContain("<strong>Up to ₹90,84,000 of committed fees is not secured");
    expect(html).toContain("§13 · Service Termination · page 2");
    expect(html).not.toContain("points differ from our standards");
    expect(html).toContain(", excluding GST");
  });

  it("never says GST is excluded unless the fee's own words do", () => {
    const html = renderToStaticMarkup(<BusinessAngleView angles={{
      ...MOU, commercial: { ...MOU.commercial, excludes_gst: false } }} />);
    expect(html).toContain("over 12 months — read from");      // the lede claims nothing
  });

  it("renders nothing until the server has answered", () => {
    expect(renderToStaticMarkup(<BusinessAngleView angles={null} />)).toBe("");
  });
});

describe("the counter-proposal card (AM-152)", () => {
  it("quotes the Constitution's wording with its own label — never drafted here", () => {
    const html = renderToStaticMarkup(<CounterProposalCard proposal={{
      section: "13", kind: "DRAFTING_LANGUAGE",
      label: "Constitution §13 — illustrative clause language (Counsel validation point)",
      text: "Either Party may terminate this Agreement for convenience upon thirty (30) days’ prior written notice to the other Party.",
    }} />);
    expect(html).toContain("Recommended wording to send back");
    expect(html).toContain("<blockquote");
    expect(html).toContain("thirty (30) days’ prior written notice");
    expect(html).toContain("illustrative clause language (Counsel validation point)");
  });
});

describe("under an AI answer: the review's own findings on the clauses it cited (AM-152)", () => {
  // The owner's scenario, traced live 2026-10-16: "Can this customer walk away early
  // without paying us anything?" — the answer cited §13; these are built by the server.
  const angles: ReviewAngles = {
    ...MOU,
    legal: { actionable: 10, matching: 5, items: [{
      finding_id: "f-1", requirement_code: "EARLY-TERM-RESTRICTION-MSA-001",
      title: "The customer cannot end the agreement before the term expires",
      classification: "DEVIATION", waived: true, where: "§13 · Service Termination · page 2",
      evidence_ids: ["ev-13"],
    }, {
      finding_id: "f-9", requirement_code: "LIABILITY-MSA-001", title: "Liability cap",
      classification: "DEVIATION", waived: false, where: "Limitation of Liability · page 6",
      evidence_ids: ["ev-9"],
    }] },
    counter_proposals: { "f-1": { section: "14", kind: "COMPANY_POSITION",
      label: "Constitution §14 — the company position (no approved clause wording exists for it)",
      text: "No early exit is permitted from a fixed-term commitment without the applicable financial consequence." } },
  };

  it("shows the Legal angle, the Business angle and the counter-proposal for the cited clause only", async () => {
    const { AnswerAnglesView } = await import("@/components/workspace/Angles");
    const html = renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-13"]} />);
    expect(html).toContain("Legal angle");
    expect(html).toContain("The clause waives our position");
    expect(html).toContain("Business angle");
    expect(html).toContain("Up to ₹90,84,000 of committed fees is not secured");
    expect(html).toContain("no approved clause wording exists");
    expect(html).toContain("Our position — no approved wording to send");   // never "send back"
    // another clause's finding is never in the cited list — only under "Also in this
    // contract", folded below it (2026-10-27)
    const cited = html.split("Also in this contract")[0]!;
    expect(cited).not.toContain("Liability cap");
  });

  it("raises the contract's other open points under the answer, folded and secondary", async () => {
    const { AnswerAnglesView } = await import("@/components/workspace/Angles");
    const html = renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-13"]} />);
    expect(html).toContain("Also in this contract (1 open point)");
    expect(html).toContain("Liability cap");              // not cited, still open
    expect(html).toMatch(/<details class="ws-angle__more">/);   // folded, never open first
  });

  it("never raises a point a person already decided, nor more than three", async () => {
    const { alsoInContract } = await import("@/components/workspace/Angles");
    const base = (angles.legal.items ?? [])[1]!;
    const open = (n: number) => ({ ...base, finding_id: `o-${n}` });
    const many: ReviewAngles = { ...angles, legal: { ...angles.legal, items: [
      { ...base, finding_id: "d-1", decided: true },
      open(1), open(2), open(3), open(4)] } };
    expect(alsoInContract(many, []).map((i) => i.finding_id)).toEqual(["o-1", "o-2", "o-3"]);
  });

  it("says nothing when the answer cited no clause the review measured", async () => {
    const { AnswerAnglesView } = await import("@/components/workspace/Angles");
    expect(renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-x"]} />)).toBe("");
  });
});

describe("lawyer-grade release 1 (AM-156)", () => {
  const items = [
    { finding_id: "f-exit", requirement_code: "EARLY-TERM-RESTRICTION-MSA-001",
      title: "Early exit", classification: "DEVIATION", waived: true,
      action: "Send our wording; accepting the difference is a Legal decision",
      where: "§13 · page 2", evidence_ids: ["ev-13"] },
    { finding_id: "f-notice", requirement_code: "CONVENIENCE-NOTICE-MSA-001",
      title: "Notice", classification: "DEVIATION", waived: false,
      action: "Send our wording; accepting the difference is a Legal decision",
      where: "§13 · page 2", evidence_ids: ["ev-13"] },
    { finding_id: "f-pay", requirement_code: "PAYMENT-PERIOD-MSA-001",
      title: "Payment", classification: "MISSING", waived: false,
      where: "§4 · page 2", evidence_ids: ["ev-4"] },
  ];
  const wording = { section: "13", kind: "DRAFTING_LANGUAGE" as const,
    label: "Constitution §13 — Drafting Notes", text: "Either Party may terminate on 30 days." };
  const angles: ReviewAngles = {
    ...MOU,
    business: [{ ...MOU.top_risks[0]!, finding_id: "f-exit", risk: true,
      money: "Up to ₹87,05,500 of the ₹90,84,000 contract is not committed." }],
    top_risks: [],
    legal: { actionable: 3, matching: 5, items },
    counter_proposals: { "f-exit": wording, "f-notice": wording },
  };

  it("keeps the findings under an answer to the asked topic and its clause", async () => {
    const { answerItems } = await import("@/components/workspace/Angles");
    const kept = answerItems(angles, ["ev-13", "ev-4"], ["EARLY-TERM-RESTRICTION-MSA-001"]);
    expect(kept.map((i) => i.finding_id)).toEqual(["f-exit", "f-notice"]);   // no payment
    expect(answerItems(angles, ["ev-13", "ev-4"], []).length).toBe(3);         // no topic: all cited
    // a topic asked and none of it cited: nothing, never an unrelated finding
    expect(answerItems(angles, ["ev-4"], ["EARLY-TERM-RESTRICTION-MSA-001"])).toEqual([]);
  });

  it("leads with the money and the action, both built by the server", async () => {
    const { AnswerLeadView } = await import("@/components/workspace/Angles");
    const html = renderToStaticMarkup(<AnswerLeadView angles={angles} evidenceIds={["ev-13"]}
      topicCodes={["EARLY-TERM-RESTRICTION-MSA-001"]} />);
    expect(html).toContain("From the review:");
    expect(html).toContain("₹87,05,500");
    expect(html).toContain("accepting the difference is a Legal decision");
  });

  it("shows the same counter-proposal wording once", async () => {
    const { AnswerAnglesView } = await import("@/components/workspace/Angles");
    const html = renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-13"]}
      topicCodes={["EARLY-TERM-RESTRICTION-MSA-001"]} />);
    expect(html.split("Either Party may terminate on 30 days.").length - 1).toBe(1);
  });

  it("says why no contract value is shown", () => {
    const html = renderToStaticMarkup(<BusinessAngleView angles={{ ...angles,
      commercial: { ...MOU.commercial, committed_value_text: null,
        missing: "the fees are set out in another document" } }} />);
    expect(html).toContain("No contract value is shown: the fees are set out in another document.");
  });
});

describe("source labels and the search record (AM-156)", () => {
  it("names a clause as a lawyer does, without the redundant scope", async () => {
    const { legendWhere } = await import("@/components/workspace/AnswerProse");
    const doc = { key: "D20", kind: "document" as const, scope: "the selected document", page: 2 };
    expect(legendWhere(doc as never, "13, the selected document")).toBe("13 · page 2");
    expect(legendWhere({ ...doc, page: 5 } as never, "p.5, the selected document")).toBe("page 5");
    // the scope is cut from the end: an annexure's own comma stays
    expect(legendWhere({ ...doc, page: 4 } as never, "Annexure-2, 3, the selected document"))
      .toBe("Annexure-2, 3 · page 4");
  });

  it("folds what was searched away under the answer", async () => {
    const { AnswerProse } = await import("@/components/workspace/AnswerProse");
    const html = renderToStaticMarkup(<AnswerProse
      text={"Yes.\n\nSearched in this turn: “termination”."} />);
    expect(html).toContain("<details");
    expect(html).toContain("What was searched");
  });
});


describe("the legal angle (AM-159/AM-160)", () => {
  const issue = (n: number, action: string) => ({
    finding_id: `f-${n}`, requirement_code: `REQ-${n}`, title: `Point ${n}`,
    classification: "DEVIATION", waived: false, action, where: `${n}.1 · page 1`,
    evidence_ids: [],
  });
  const legal: ReviewAngles = {
    ...MOU,
    recommendation: "Recommendation: sign after 6 changes. An authorised person decides (§24.3).",
    legal: { actionable: 6, matching: 2, items: [
      { ...issue(1, "Send our wording; accepting the difference is a Legal decision"),
        enforceability: { section: "29.1.1", text: "A stated contractual amount or term is not automatically the legally recoverable or enforceable one (Section 28.4.1)." } },
      ...[2, 3, 4, 5, 6].map((n) => issue(n, "Legal decides — no approved wording exists for this point")),
    ] },
    observations: {
      structural: [{ kind: "NO_NONPAYMENT_REMEDY", clauses: [], evidence_ids: [],
        text: "This document states no right to suspend or terminate for non-payment.",
        basis: { section: "13", quote: "except for non-payment, security threats, or illegal use, which permit immediate suspension." },
        action: "Legal decides — the Constitution defines no boundary for this point (§23.4)" }],
      additional: [{ kind: "CROSS_REFERENCE", clauses: ["2.1"], evidence_ids: [],
        text: "Clause 2.1 refers to clause 12, which this document does not contain.", basis: null }],
    },
  };

  it("leads with the recommendation, then the open points in order, the rest folded", () => {
    const html = renderToStaticMarkup(<LegalAngleView angles={legal} />);
    expect(html).toContain("Open points (6)");
    expect(html.indexOf("Recommendation: sign after 6 changes"))
      .toBeLessThan(html.indexOf("Send our wording"));
    expect(html).toContain("Constitution §29.1.1: “A stated contractual amount");
    expect(html).toContain("<summary>1 more</summary>");           // the sixth folds away
    expect(html).toContain("This document states no right to suspend or terminate for non-payment.");
    expect(html).toContain("Constitution §13: “except for non-payment");
    expect(html).toContain("<summary>Additional points (1)</summary>");
    expect(html).not.toMatch(/reject|risk score|%/i);
  });

  it("shows nothing when the review has no angles yet", () => {
    expect(renderToStaticMarkup(<LegalAngleView angles={null} />)).toBe("");
  });
});

describe("the lawyer's second read (AM-162)", () => {
  it("shows each verified item in fixed words with its quote, folded, under its own label", () => {
    const html = renderToStaticMarkup(<LegalAngleView angles={{ ...MOU, reading: {
      label: "Found by reading — no company position covers this; Legal decides.",
      items: [{ category: "UNCAPPED", text: "Exposure with no limit",
        quote: "liability under this Agreement is unlimited", evidence_id: "e-1",
        clause: "13.1", with_finding: true }] } }} />);
    expect(html).toContain("<summary>Found by reading (1)</summary>");
    expect(html).toContain("no company position covers this; Legal decides.");
    expect(html).toContain("Exposure with no limit");
    expect(html).toContain("clause 13.1");
    expect(html).toContain("(a finding also reads this clause)");
    expect(html).toContain("“liability under this Agreement is unlimited”");
    expect(html.toLowerCase()).not.toMatch(/confidence|risk score|probab/);
  });
});

describe("open points (owner, 2026-10-21)", () => {
  it("names each point with its gap and recommendation, and one press opens it", () => {
    const opened: string[] = [];
    const item = { finding_id: "f-n", requirement_code: "CONVENIENCE-NOTICE-MSA-001",
      title: "x", classification: "DEVIATION", waived: false, action: "Send our wording",
      where: "13 · page 2", evidence_ids: [], related: [],
      case: { contract: null, standard: { section: "13", topic: null }, related: [],
              gap: "15 days in the contract vs our 30 days", business: null,
              recommendation: "Request revised wording" } };
    const angles = { ...MOU, legal: { actionable: 1, matching: 0, items: [item] } };
    const html = renderToStaticMarkup(
      <LegalAngleView angles={angles} onOpen={(id) => opened.push(id)} />);
    expect(html).toContain("Convenience notice");
    expect(html).toContain("15 days in the contract vs our 30 days");
    expect(html).toContain("Request revised wording");
    expect(html).toContain('<button type="button" class="ws-open__go"');
    expect(html.toLowerCase()).not.toMatch(/reject|confidence|%/);
  });
});

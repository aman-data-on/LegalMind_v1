/**
 * The legend must describe the mapping the server actually applies.
 *
 * A UX review (2026-09-17) reported the Arbitration finding as a logic bug: its
 * details read "Rule outcome: No rule covers this" while the card was badged
 * "Requires modification", and the legend's third card said "Needs a decision"
 * covers the case where "the company has no approved position yet". A reader
 * comparing those two concluded the badge was wrong.
 *
 * The badge is right and the legend was wrong. `AM-56` (owner, 2026-09-09) makes
 * the reader's word a PURE projection of the classification —
 * `legalmind/domain/user_status.py` takes `rule_outcome` as an argument and
 * deliberately never reads it — so a MISSING required clause is "Requires
 * modification", which is what the SECOND card already describes accurately. A
 * rule outcome of NOT_APPLICABLE does not move the word; whether a person must
 * rule on the finding travels separately, as its Finding state and the
 * pending-decision count.
 *
 * So this pins the legend against the mapping rather than against itself: each
 * card may only promise its word for cases that word actually carries.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StatusExplainer } from "@/components/workspace/AnalysisPanel";

const legend = () => renderToStaticMarkup(<StatusExplainer />).replace(/<[^>]*>/g, " ");

describe("the three-status legend matches AM-56's projection", () => {
  it("does not promise 'Needs a decision' for having no approved position", () => {
    /* The exact phrase that produced the report. Nothing in `user_status.py`
       routes "no approved position" to NEEDS_DECISION — a requirement with no
       ratified standard produces no finding at all. */
    expect(legend()).not.toMatch(/no approved position/i);
    expect(legend()).not.toMatch(/no position →/i);
  });

  it("keeps 'a required clause is absent' under Requires modification", () => {
    // MISSING → REQUIRES_MODIFICATION is the mapping, and the Arbitration
    // finding the review questioned is exactly this case.
    const text = legend();
    const warn = text.slice(text.indexOf("Deviation or missing"), text.indexOf("Unclear"));
    expect(warn).toMatch(/required clause is absent/i);
  });

  it("names only what actually reaches Needs a decision", () => {
    const text = legend();
    const bad = text.slice(text.indexOf("Unclear"));
    // UNABLE_TO_EVALUATE, CONFLICT, and the AM-63 Constitution exception.
    expect(bad).toMatch(/unclear/i);
    expect(bad).toMatch(/conflict/i);
    expect(bad).toMatch(/could not be read/i);
    expect(bad).toMatch(/unacceptable/i);
    // Rule 12 / AM-63 §24.4(1): never shown as a rejection.
    expect(bad).toMatch(/never a rejection/i);
  });

  it("still states all three words, in the one fixed order", () => {
    const text = legend();
    expect(text.indexOf("Acceptable")).toBeLessThan(text.indexOf("Requires modification"));
    expect(text.indexOf("Requires modification")).toBeLessThan(text.indexOf("Needs a decision"));
  });
});

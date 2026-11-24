import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FromOurStandard, LetteredPoints, NotesForLegal } from "@/components/workspace/LawyerView";
import type { ClientChange } from "@/lib/changes";

describe("R2 lawyer view (display only)", () => {
  it("lists a change as lettered points with who each binds and the standards", () => {
    const change = { lawyer: {
      points: [
        { letter: "a", kind: "CHANGED", before: "x", after: "Pay in 30 days.", bound: "CLIENT", benefits: "LEAPSWITCH" },
        { letter: "b", kind: "ADDED", before: null, after: "We give support.", bound: "LEAPSWITCH", benefits: "CLIENT" },
      ],
      standards: { source: "LEGAL_DECIDES" }, mutuality: "MIXED",
    } } as unknown as ClientChange;
    const html = renderToStaticMarkup(<LetteredPoints change={change} />).replaceAll("<!-- -->", "");
    expect(html).toContain("(a) Changed:");
    expect(html).toContain("Binds LeapSwitch; helps the client.");
    // U2 (UI-07): with no standard, "From our standard" says it once — never here as well
    expect(html).not.toContain("Legal decides.");
  });

  it("shows notes for Legal only when there are some", () => {
    expect(renderToStaticMarkup(<NotesForLegal list={{ notes_for_legal: [] }} />)).toBe("");
    const html = renderToStaticMarkup(<NotesForLegal list={{ notes_for_legal: [{ kind: "DUPLICATE", clauses: ["1", "2"], text: "Clause 1 repeats what clause 2 already says." }] }} />).replaceAll("<!-- -->", "");
    expect(html).toContain("Notes for Legal (1)");
  });

  it("links a note's clause to its change row, only where a row exists (R3)", () => {
    const list = { notes_for_legal: [{ kind: "CROSS_REF", clauses: ["8.3", "9"], text: "8.9 points to 8.3." }] };
    const html = renderToStaticMarkup(<NotesForLegal list={list} onPick={() => {}}
      rowFor={(n) => (n === "8.3" ? "row-83" : null)} />).replaceAll("<!-- -->", "");
    expect(html).toContain(">Go to 8.3</button>");
    expect(html).not.toContain("Go to 9");
  });

  it("says what our standard says, only from what the server sent (R3, rule 21)", () => {
    const silent = { triage: null, lawyer: { standards: { source: "LEGAL_DECIDES" } }, review: { after: [] } } as unknown as ClientChange;
    // U2 r4: with no standard the card's grid says it once; this section draws nothing
    expect(renderToStaticMarkup(<FromOurStandard change={silent} />)).toBe("");
    const said = { triage: { topics: [{ section: "13", title: "Termination", position: "Thirty days' notice." }] },
                   lawyer: { standards: { source: "HEADING_TOPIC", topics: [] } }, review: { after: [] } } as unknown as ClientChange;
    const html = renderToStaticMarkup(<FromOurStandard change={said} />).replaceAll("<!-- -->", "");
    expect(html).toContain("From our standard");
    expect(html).toContain("Thirty days&#x27; notice.");
    // a reader sent no position (LEGAL-02) sees the topic and no position text
    const hidden = { ...said, triage: { topics: [{ section: "13", title: "Termination" }] } } as unknown as ClientChange;
    const bare = renderToStaticMarkup(<FromOurStandard change={hidden} />);
    expect(bare).toContain("Termination.");
    expect(bare).not.toContain("Thirty days");
  });
});

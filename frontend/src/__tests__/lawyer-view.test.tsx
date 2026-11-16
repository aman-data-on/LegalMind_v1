import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LetteredPoints, NotesForLegal } from "@/components/workspace/LawyerView";
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
    expect(html).toContain("No standard covers this. Legal decides.");
  });

  it("shows notes for Legal only when there are some", () => {
    expect(renderToStaticMarkup(<NotesForLegal list={{ notes_for_legal: [] }} />)).toBe("");
    const html = renderToStaticMarkup(<NotesForLegal list={{ notes_for_legal: [{ kind: "DUPLICATE", clauses: ["1", "2"], text: "Clause 1 repeats what clause 2 already says." }] }} />).replaceAll("<!-- -->", "");
    expect(html).toContain("Notes for Legal (1)");
  });
});

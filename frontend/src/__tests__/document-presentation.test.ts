/**
 * DD-14 — document presentation and reader annotations, the pure parts.
 *
 * `rowPresentation` may only RECOGNISE structure already present in the
 * extracted text (title/heading/item), never manufacture it: the cases here
 * are the real MSA rows the heuristics were built against, plus the shapes
 * that must NOT match. `segmentContent` must re-emit the original string
 * exactly — marks re-wrap text, they never edit it.
 */

import { describe, expect, it } from "vitest";

import { segmentContent, type Annotation } from "@/components/workspace/annotations";
import { documentTextState, rowPresentation } from "@/components/workspace/model";

const row = (content: string, section_number: string | null = null, section_title: string | null = null) =>
  ({ content, section_number, section_title });

describe("rowPresentation (grounded on the real MSA extraction)", () => {
  it("the first short unnumbered row is the document title", () => {
    expect(rowPresentation(row("Master Services Agreement"), 0)).toBe("title");
  });

  it("the same row anywhere else is a paragraph — position is part of the shape", () => {
    expect(rowPresentation(row("Master Services Agreement"), 3)).toBe("para");
  });

  it("a long or sentence-terminated first row is never a title", () => {
    expect(rowPresentation(row("This Master Services Agreement is entered into on 28 day of the of July, 2026 by and between the parties."), 0)).toBe("para");
    expect(rowPresentation(row("Recitals follow below:"), 0)).toBe("para");
  });

  it("a row that IS its own section label renders as a heading", () => {
    expect(rowPresentation(row("1. DEFINITIONS AND INTERPRETATION", "1", "DEFINITIONS AND INTERPRETATION"), 5)).toBe("heading");
    expect(rowPresentation(row("3. SERVICES", "3", "SERVICES"), 20)).toBe("heading");
  });

  it("a dotted section number makes it a subheading", () => {
    expect(rowPresentation(row("1.2 Interpretation", "1.2", "Interpretation"), 21)).toBe("subheading");
  });

  it("a section row that carries body text stays a paragraph — §1.1's real shape", () => {
    expect(rowPresentation(
      row("1.1 Defined Terms: Capitalized terms used in this Agreement shall have the meanings assigned to them hereunder or as the case may be in the relevant clauses of this Agreement:", "1.1", "Defined Terms: Capitalized terms used in this Agreement shall have the meanings"),
      6,
    )).toBe("para");
  });

  it("enumerated definitions get the hanging-indent item shape", () => {
    expect(rowPresentation(row('(a) "Affected Party" means the Party claiming the benefit of Force Majeure.'), 7)).toBe("item");
    expect(rowPresentation(row("(B) The Parties have agreed that the provision of Services shall be governed hereby."), 4)).toBe("item");
  });

  it("a parenthesis mid-sentence is not an item lead", () => {
    expect(rowPresentation(row("The fee (as defined) is due on the Due Date."), 9)).toBe("para");
  });
});

describe("segmentContent (marks re-wrap the string, never edit it)", () => {
  const ann = (start: number, end: number, id = "a1"): Annotation =>
    ({ id, rowId: "r", start, end, note: "", created: "2026-09-02" });

  const rejoin = (content: string, annotations: Annotation[]) =>
    segmentContent(content, annotations).map((segment) => segment.text).join("");

  it("concatenation is always exactly the original content", () => {
    const content = "The liability cap is twelve months of total fees.";
    for (const anns of [
      [],
      [ann(4, 13)],
      [ann(0, 3), ann(4, 13)],
      [ann(4, 13), ann(10, 20, "a2")], // overlap
      [ann(-5, 999, "a3")],            // out of range → clamped
    ]) {
      expect(rejoin(content, anns)).toBe(content);
    }
  });

  it("marks land on the right characters", () => {
    const segments = segmentContent("abcdef", [ann(2, 4)]);
    expect(segments.map((s) => [s.text, s.annotation !== null])).toEqual([
      ["ab", false], ["cd", true], ["ef", false],
    ]);
  });

  it("an overlapping later mark keeps only its uncovered remainder", () => {
    const segments = segmentContent("abcdef", [ann(0, 4), ann(2, 6, "a2")]);
    expect(segments.map((s) => [s.text, s.annotation?.id ?? null])).toEqual([
      ["abcd", "a1"], ["ef", "a2"],
    ]);
  });
});

describe("documentTextState (the empty-state branch, 2026-09-03)", () => {
  it("calls a FAILED document unreadable, never 'still processing'", () => {
    // The bug: the pane branched on `processing_status !== "COMPLETED"` alone,
    // so a definitively failed document told the reader to "reload to check"
    // something that will never change.
    expect(documentTextState({ processing_status: "FAILED", extraction_status: "FAILED" }))
      .toBe("unreadable");
  });

  it("treats either axis carrying the failure as unreadable", () => {
    // 34.15 keeps processing and extraction as separate axes; a document whose
    // run completed but whose extraction failed is still unreadable.
    expect(documentTextState({ processing_status: "COMPLETED", extraction_status: "FAILED" }))
      .toBe("unreadable");
    expect(documentTextState({ processing_status: "FAILED", extraction_status: null }))
      .toBe("unreadable");
  });

  it("still reports genuine in-flight processing as processing", () => {
    for (const status of ["PENDING", "PROCESSING"]) {
      expect(documentTextState({ processing_status: status, extraction_status: null }))
        .toBe("processing");
    }
  });

  it("distinguishes a successfully-read document that simply has no text", () => {
    expect(documentTextState({ processing_status: "COMPLETED", extraction_status: "COMPLETE" }))
      .toBe("empty");
  });
});

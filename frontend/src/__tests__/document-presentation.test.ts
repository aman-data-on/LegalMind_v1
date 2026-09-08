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

import type { EvidenceRow } from "@/lib/types";

import { segmentContent, type Annotation } from "@/components/workspace/annotations";
import {
  documentTextState,
  findingsByEvidenceId,
  outlineOf,
  requirementHeading,
  rowPresentation,
  sequenceBreaks,
} from "@/components/workspace/model";

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

describe("the document outline (2026-09-05)", () => {
  const row = (id: string, extra: Partial<EvidenceRow> = {}): EvidenceRow => ({
    id,
    document_version_id: "v1",
    page_number: 1,
    section_number: null,
    section_title: null,
    content: "text",
    source_type: "NATIVE_TEXT",
    start_offset: 0,
    end_offset: 4,
    ...extra,
  });

  it("lists headings, not every row that starts with a number", () => {
    const rows = [
      row("a", { section_number: "13", section_title: "LIMITATION", is_heading: true }),
      row("b", { section_number: "13.1", section_title: "The total liability" }),
      row("c", { section_number: "14", section_title: "CONFIDENTIALITY", is_heading: true }),
    ];
    expect(outlineOf(rows).map((r) => r.id)).toEqual(["a", "c"]);
  });

  it("falls back to numbered rows for documents extracted before the marker existed", () => {
    // Re-extracting them would rewrite evidence a Finding already cites, so an
    // imperfect outline is the honest option — never an empty one.
    const rows = [
      row("a", { section_number: "13", section_title: "LIMITATION" }),
      row("b", { content: "unnumbered prose" }),
    ];
    expect(outlineOf(rows).map((r) => r.id)).toEqual(["a"]);
  });

  it("marks where numbering restarts, and not where it merely nests", () => {
    const rows = [
      row("a", { section_number: "1", is_heading: true }),
      row("b", { section_number: "1.2", is_heading: true }),   // sub-heading
      row("c", { section_number: "24", is_heading: true }),
      row("d", { section_number: "1", is_heading: true }),     // the annexure
    ];
    const breaks = sequenceBreaks(rows);
    expect(breaks.has("b")).toBe(false);
    expect(breaks.has("d")).toBe(true);
  });
});

describe("the review loop, both directions (2026-09-05)", () => {
  const ev = (id: string) => ({ id });
  const finding = (id: string, evidence: string[], extra: object = {}) => ({
    id, classification: "DEVIATION", requires_decision: true,
    requirement: { code: "LIABILITY-MSA-001", name: "Limitation of liability" },
    evidence: evidence.map(ev), ...extra,
  });

  it("indexes the findings that cite each evidence row", () => {
    const map = findingsByEvidenceId([finding("f1", ["e1", "e2"]), finding("f2", ["e2"])]);
    expect(map.get("e1")?.map((f) => f.id)).toEqual(["f1"]);
    // Two findings on one clause: both are returned, in the order given — the
    // reverse link invents no priority between them.
    expect(map.get("e2")?.map((f) => f.id)).toEqual(["f1", "f2"]);
  });

  it("returns nothing for evidence no finding cites", () => {
    // The honest empty state: the row renders no affordance at all rather than
    // a control that leads nowhere.
    expect(findingsByEvidenceId([finding("f1", ["e1"])]).get("e9")).toBeUndefined();
  });

  it("cites one finding once even when it names the same row twice", () => {
    const map = findingsByEvidenceId([finding("f1", ["e1", "e1"])]);
    expect(map.get("e1")).toHaveLength(1);
  });

  it("discloses nothing when the reader has no findings to see", () => {
    // A reader without finding.view is given an empty list by the server, so
    // the reverse link cannot leak the existence of a finding they may not see.
    expect(findingsByEvidenceId([]).size).toBe(0);
  });

  it("names a requirement the same way the findings pane does", () => {
    expect(requirementHeading({ code: "X", name: "Limitation of liability" }))
      .toBe("Limitation of liability");
    // The ratified config gives some requirements the same string for both;
    // the heading must not read as a code when a name adds nothing.
    expect(requirementHeading({ code: "EARLY-TERM-RESTRICTION", name: "EARLY-TERM-RESTRICTION" }))
      .toBe("Early term restriction");
    expect(requirementHeading({ code: null, name: null })).toBe("Requirement");
  });
});

/**
 * The Contents, and the paragraphs that were pretending to be headings
 * (owner's screenshot, 2026-09-08).
 *
 * A real NDA's Contents read "AND", "Information", "The information is
 * independently developed by employees of the…", then §10, §11, §12. The first
 * three are body text: the parser promotes an unnumbered line to a heading when
 * the line after it does not begin lowercase, which is true of a party block
 * and of a definitions paragraph.
 *
 * Fixed in the outline rather than in the parser, deliberately — `is_heading`
 * also feeds the mapping engine and the analysis refusal check, so re-tuning
 * detection would risk changing legal results to fix a navigation defect.
 */
describe("the Contents shows headings, not paragraphs that begin like one", () => {
  const ev = (over: Partial<EvidenceRow>): EvidenceRow => ({
    id: "x", document_version_id: "v", page_number: 1,
    section_number: null, section_title: null, content: "",
    source_type: "NATIVE_TEXT", start_offset: 0, end_offset: 0, ...over,
  } as EvidenceRow);

  // The six rows the live document actually produced, verbatim lengths.
  const real = [
    ev({ id: "s10", section_number: "10", section_title: "GOVERNING LAW & JURISDICTION",
         content: "10. GOVERNING LAW & JURISDICTION", is_heading: true }),
    ev({ id: "s11", section_number: "11", section_title: "NO REPRESENTATIONS",
         content: "11. NO REPRESENTATIONS", is_heading: true }),
    ev({ id: "s12", section_number: "12", section_title: "MISCELLANEOUS",
         content: "12. MISCELLANEOUS", is_heading: true }),
  ];
  const false_ = [
    ev({ id: "and", section_title: "AND", is_heading: true,
         content: `AND \n${"a company incorporated under the Companies Act ".repeat(16)}` }),
    ev({ id: "info", section_title: "Information", is_heading: true,
         content: `Information \n${"Subject to exceptions as stated in clause 3 hereinbelow ".repeat(3)}` }),
    ev({ id: "dev", section_title: "The information is independently developed by employees of the Receiving",
         is_heading: true,
         content: "The information is independently developed by employees of the Receiving \nParty who have not had access to the Confidential Information of the Disclosing Party." }),
  ];

  it("keeps the three real headings and drops the three paragraphs", () => {
    expect(outlineOf([...real, ...false_]).map((r) => r.id)).toEqual(["s10", "s11", "s12"]);
  });

  it("keeps a heading whose title is long, so long titles are not the test", () => {
    const long = ev({
      id: "long", section_number: "7",
      section_title: "RESTRICTION ON EARLY TERMINATION BY THE CUSTOMER FOR CONVENIENCE",
      content: "7. RESTRICTION ON EARLY TERMINATION BY THE CUSTOMER FOR CONVENIENCE",
      is_heading: true,
    });
    expect(outlineOf([long]).map((r) => r.id)).toEqual(["long"]);
  });

  it("trusts a heading the parser recorded with no title — an annexure label", () => {
    const annexure = ev({ id: "anx", content: "Annexure-1", annexure: "Annexure-1", is_heading: true });
    expect(outlineOf([annexure]).map((r) => r.id)).toEqual(["anx"]);
  });

  it("still falls back to numbered rows when filtering leaves nothing", () => {
    // A document whose ONLY heading marks are paragraphs must not lose its
    // Contents altogether — the numbered rows are the honest fallback.
    const rows = [...false_, ev({ id: "n", section_number: "3", section_title: "Term" })];
    expect(outlineOf(rows).map((r) => r.id)).toEqual(["n"]);
  });
});

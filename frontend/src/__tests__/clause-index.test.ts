/**
 * The clause index the Contents panel lists.
 *
 * Every string here is copied verbatim from an evidence row in the live
 * database (`Leapswitch MSA - Final - Feb.docx.pdf`, document version
 * c133400b, and the executed GRP MSA), U+200B included — the character that
 * made the panel empty. Do not "tidy" them.
 */

import { describe, expect, it } from "vitest";

import { clauseFromText, clauseOf, outlineOf, sequenceBreaks } from "@/components/workspace/model";
import type { EvidenceRow } from "@/lib/types";

function row(fields: Partial<EvidenceRow> & { content: string }): EvidenceRow {
  return {
    id: fields.content.slice(0, 24),
    document_version_id: "v1",
    page_number: null,
    section_number: null,
    section_title: null,
    source_type: "TEXT",
    start_offset: null,
    end_offset: null,
    ...fields,
  } as EvidenceRow;
}

describe("clauseFromText — Word list numbering split by U+200B", () => {
  it("reads the number from its own line and the title from the next", () => {
    // The exact bytes that produced an empty Contents panel.
    expect(clauseFromText({ content: "1.​\nDEFINITIONS \n1.1.​“Affiliate” shall mean" }))
      .toEqual({ number: "1", title: "DEFINITIONS" });
    expect(clauseFromText({ content: "7.​\nTERM AND TERMINATION" }))
      .toEqual({ number: "7", title: "TERM AND TERMINATION" });
    expect(clauseFromText({ content: "17.​\nLIMITATION OF LIABILITY" }))
      .toEqual({ number: "17", title: "LIMITATION OF LIABILITY" });
  });

  it("reads a number and title that share one line", () => {
    expect(clauseFromText({ content: "2.​ INTERPRETATION \n2.1.​Words of any gender" }))
      .toEqual({ number: "2", title: "INTERPRETATION" });
    expect(clauseFromText({ content: "1.13.​ “Services” or “Leapswitch Services” means" }))
      .toEqual({ number: "1.13", title: "“Services” or “Leapswitch Services” means" });
  });

  it("keeps a multi-level number whole", () => {
    // Regression: a greedy number followed by an optional dot split "2.1 The
    // Parties" into §2 titled "1 The Parties", which is a clause that does not
    // exist. The number token must end where the whitespace begins.
    expect(clauseFromText({ content: "2.1 The Parties agree that this Agreement" }))
      .toEqual({ number: "2.1", title: "The Parties agree that this Agreement" });
    expect(clauseFromText({ content: "6.1.3.1​ The Parties have mutually agreed" }))
      .toEqual({ number: "6.1.3.1", title: "The Parties have mutually agreed" });
  });

  it("refuses a bare page number", () => {
    // Pages 3 and 19 of the MSA are single-row footers reading just "3" / "19".
    // Without the trailing dot they would enter the index as clauses, and page
    // 20's footer would have adopted the heading beneath it as its title.
    expect(clauseFromText({ content: "3" })).toBeNull();
    expect(clauseFromText({ content: "20\nSignatory Details" })).toBeNull();
  });

  it("refuses text that merely begins with a word", () => {
    expect(clauseFromText({ content: "WHEREAS" })).toBeNull();
    expect(clauseFromText({ content: "​\n​" })).toBeNull();
    expect(clauseFromText({ content: "The Parties agree that this Agreement" })).toBeNull();
  });
});

describe("clauseOf — what the parser recorded wins", () => {
  it("never reinterprets a row the parser numbered", () => {
    const parsed = row({
      content: "1.1 Defined Terms: Capitalized terms used in this Agreement",
      section_number: "1.1",
      section_title: "Defined Terms",
    });
    expect(clauseOf(parsed)).toEqual({ number: "1.1", title: "Defined Terms" });
  });

  it("falls back to the row's own text only when the number is missing", () => {
    expect(clauseOf(row({ content: "17.​\nLIMITATION OF LIABILITY" })))
      .toEqual({ number: "17", title: "LIMITATION OF LIABILITY" });
  });

  it("reports no number rather than inventing one", () => {
    expect(clauseOf(row({ content: "WHEREAS", section_title: "WHEREAS" })))
      .toEqual({ number: null, title: "WHEREAS" });
  });
});

describe("outlineOf", () => {
  it("lists the document's clauses when the parser numbered none of them", () => {
    // The live shape: heading marks land on the recital blocks (long party
    // paragraphs, filtered as non-heading lines) and every real clause arrives
    // unnumbered.
    const rows = [
      row({ content: "​\n​" }),
      row({
        content: "A.​\nLeapSwitch Networks Private Limited, a company incorporated under the Companies Act, 1956 and having its registered office at 1/A2/22",
        section_title: "A.​",
        is_heading: true,
      }),
      row({ content: "WHEREAS" }),
      row({ content: "1.​\nDEFINITIONS \n1.1.​“Affiliate” shall mean" }),
      row({ content: "3" }),
      row({ content: "7.​\nTERM AND TERMINATION" }),
      row({ content: "17.​\nLIMITATION OF LIABILITY" }),
    ];
    expect(outlineOf(rows).map((r) => clauseOf(r).number)).toEqual(["1", "7", "17"]);
  });

  it("leaves a document the parser reads correctly exactly as it was", () => {
    // Real heading rows exist, so the fallback never runs and the index is the
    // parser's own — the behaviour pinned before this change.
    const rows = [
      row({ content: "1. DEFINITIONS AND INTERPRETATION", section_number: "1", section_title: "DEFINITIONS AND INTERPRETATION", is_heading: true }),
      row({ content: "1.1 Defined Terms: Capitalized terms used in this Agreement shall have the meanings assigned", section_number: "1.1", section_title: "Defined Terms" }),
      row({ content: "1.2 Interpretation", section_number: "1.2", section_title: "Interpretation", is_heading: true }),
    ];
    expect(outlineOf(rows).map((r) => r.section_number)).toEqual(["1", "1.2"]);
  });
});

describe("sequenceBreaks", () => {
  it("sees a restart in derived numbers too", () => {
    // An annexed AUP that begins again at §1 restarts whether or not the parser
    // recorded the numbers; before this the divider only appeared for stored ones.
    const rows = [
      row({ content: "23.​\nGENERAL PROVISIONS" }),
      row({ content: "1.​\nACCEPTABLE USE" }),
    ];
    expect(sequenceBreaks(rows).size).toBe(1);
  });
});

/**
 * What the reading could not read, said to the reader (R3/R4) — and where an Ask
 * source's text came from (F8). Before these fixes the footer showed only index
 * readiness, an integrity refusal read "Not yet searchable", and a cited clause
 * lost its page and its OCR/table provenance in the Sources dialog.
 */
import { describe, expect, it } from "vitest";

import { sourceWhere } from "@/components/workspace/AnswerProse";
import { READINESS_TEXT, readiness, readingNote } from "@/components/workspace/model";

describe("readingNote (R3)", () => {
  it("says nothing for a clean reading", () => {
    expect(readingNote({ extraction_status: "COMPLETE", pages_failed: [], pages_to_check: [] }))
      .toBeNull();
    expect(readingNote({ extraction_status: null })).toBeNull();
  });

  it("names the extraction status and the pages it could not read", () => {
    expect(readingNote({ extraction_status: "PARTIAL", pages_failed: [2, 5] }))
      .toBe("Partly extracted · Pages 2, 5 could not be read");
    expect(readingNote({ extraction_status: "PARTIAL", pages_failed: [3] }))
      .toBe("Partly extracted · Page 3 could not be read");
  });

  it("flags low-confidence OCR pages in words, never a figure (rule 12)", () => {
    const note = readingNote({ extraction_status: "COMPLETE", pages_to_check: [4] })!;
    expect(note).toBe("Page 4 read by OCR — check figures against the original");
    expect(note).not.toMatch(/\d+\s*%|confidence/i);
  });
});

describe("readiness after an integrity refusal (R4)", () => {
  it("is refused, not 'not yet', even with zero chunks", () => {
    const ready = readiness({ chunks: 0, embedded_chunks: 0, refused: ["REPEATED_TEXT"] });
    expect(ready).toBe("refused");
    expect(READINESS_TEXT[ready]).not.toMatch(/not yet/i);
    expect(READINESS_TEXT[ready]).not.toContain("REPEATED_TEXT");
    expect(readiness({ chunks: 0, embedded_chunks: 0, refused: [] })).toBe("not-indexed");
    // a refused RE-index keeps the previous chunks, which Ask still reads (review 2026-10-16)
    expect(readiness({ chunks: 12, embedded_chunks: 12, refused: ["REPEATED_TEXT"] }))
      .toBe("ready");
  });
});

describe("sourceWhere (F8)", () => {
  it("adds the page and how the text was read", () => {
    expect(sourceWhere({ page: 7, read_by: "OCR" }, "§9.2")).toBe("§9.2 · page 7 · read by OCR");
    expect(sourceWhere({ read_by: "TABLE" }, "§4")).toBe("§4 · from a table");
  });

  it("leaves a native clause as the legend says it, and never repeats a page", () => {
    expect(sourceWhere({}, "§9, MSA agreements only")).toBe("§9, MSA agreements only");
    expect(sourceWhere({ page: 3 }, "page 3")).toBe("page 3");
  });
});

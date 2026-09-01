/**
 * The Documents pipeline strip — `AI-01`, owner Q9, rule 12.
 *
 * This suite exists because the owner-supplied reference for this page described
 * a different product, and its copy is the kind that gets pasted back in. The
 * reference read "AI extracts text and key clauses", "Contract type & relevant
 * standards identified", and "Get risks, deviations & actionable insights".
 *
 * Each of those is wrong here in a specific, checkable way:
 *
 * - `AI-01` (reaffirmed by `AM-25`): no LLM, RAG, embedding or vector database in
 *   the AUTHORITATIVE analysis path. The interface must not advertise the one
 *   architecture that is locked out of it.
 * - Owner Q9 (2026-08-19): Document Type is DECLARED by the uploader, never
 *   inferred. `AM-34` allows a suggestion; only the human's confirmation records
 *   the type. So the strip must not promise automatic detection.
 * - Rule 12 / DESIGN.md: a Finding reconstructs as Evidence → Fact → Standard →
 *   Rule → Result. No risk score, no confidence, no "the AI thinks".
 *
 * A screen that overpromises here is not a copy problem. It tells a lawyer the
 * engine did something it did not do, which is the failure mode the whole
 * specification is arranged against.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Pipeline } from "@/components/workspace/Pipeline";

const html = () => renderToStaticMarkup(<Pipeline />);
const text = () => html().replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").toLowerCase();

describe("AI-01 — the strip never advertises the locked-out architecture", () => {
  it("does not claim AI or an LLM does the extraction or the analysis", () => {
    const copy = text();
    for (const forbidden of ["ai extract", "ai-powered", "ai powered", "our ai",
                             "llm", "rag", "embedding", "vector", "machine learning",
                             "neural", "gpt", "gemini"]) {
      expect(copy).not.toContain(forbidden);
    }
  });

  it("does not imply a probability, a confidence or a score", () => {
    // DESIGN.md's prohibition, and the same list `npm run check:terms` enforces
    // across the tree. Asserted on rendered copy, which that script cannot see.
    const copy = text();
    for (const forbidden of ["confidence", "probability", "likelihood",
                             "risk score", "score", "% sure", "accuracy"]) {
      expect(copy).not.toContain(forbidden);
    }
  });
});

describe("owner Q9 — the type is declared, never detected", () => {
  it("never promises automatic type detection", () => {
    const copy = text();
    for (const forbidden of ["automatically detect", "auto-detect", "autodetect",
                             "we detect", "detects the type", "identifies the type"]) {
      expect(copy).not.toContain(forbidden);
    }
  });

  it("names the human as the one who declares it", () => {
    // Shortened 2026-09-01 with the copy ("yours to declare — a suggestion
    // pre-fills the field" → "you declare it"). The GUARD is unchanged: this step
    // must still attribute the act to the reader, because owner Q9 makes the type
    // declared and never inferred. Only the string it looks for moved.
    const copy = text();
    expect(copy).toContain("confirm type");
    expect(copy).toContain("you declare it");
  });
});

describe("rule 12 — the last step promises traceability, not insight", () => {
  it("says findings trace back to their source", () => {
    // "each result traces back to the clause it came from" → "traced to the
    // clause". Rule 12's requirement is that the step promises provenance rather
    // than a score; the shorter phrase still does.
    expect(text()).toContain("traced to the clause");
  });

  it("does not offer insights or actionable recommendations", () => {
    const copy = text();
    for (const forbidden of ["insight", "actionable", "recommend"]) {
      expect(copy).not.toContain(forbidden);
    }
  });
});

describe("structure and accessibility", () => {
  it("is an ordered list, because the order is the content", () => {
    // A screen reader announcing "3 of 5" carries what the arrows carry visually,
    // which is why the arrows are decorative.
    const markup = html();
    expect(markup).toContain("<ol");
    expect((markup.match(/<li/g) ?? []).length).toBe(5);
  });

  it("hides every decorative mark and arrow from assistive technology", () => {
    const markup = html();
    const svgs = markup.match(/<svg[^>]*>/g) ?? [];
    expect(svgs.length).toBeGreaterThan(5);
    for (const svg of svgs) {
      expect(svg).toContain('aria-hidden="true"');
    }
  });

  it("uses no emoji — this codebase's marks are SVG", () => {
    // The reference used ▤ ◎ ▥ ◇ 🔒 →. Platform fonts render those at different
    // weights and baselines, which is visible in a row of five equal marks.
    expect(html()).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("makes no security claim at all — that is not this strip's job", () => {
    // The "documents stay on our own infrastructure" line was REMOVED on
    // 2026-09-01 (owner: essentials only). Locked 54.6 and `AM-30` t1 are
    // unchanged; the strip simply no longer speaks to them, and a security claim
    // inside a workflow diagram reads as marketing either way.
    //
    // So this became a pure absence check. It is the more useful assertion of the
    // two: it fails if anyone adds reassurance here, in any wording.
    const copy = text();
    for (const theater of ["secure", "confidential", "encrypt", "bank-grade",
                           "military", "256-bit", "guaranteed", "100%",
                           "certified", "compliant", "trusted", "safe"]) {
      expect(copy).not.toContain(theater);
    }
  });

  it("keeps every caption short enough to sit on one or two lines", () => {
    // Not cosmetic. Five captions share a row and a baseline; a long one wraps
    // further than its neighbours and drags the whole row out of alignment — the
    // defect a screenshot caught on 2026-09-01 when one label ran to two lines.
    // A character budget is the cheap structural version of that check.
    const captions = [...html().matchAll(
      /class="ws-pipe__detail"[^>]*>([^<]*)</g)].map((m) => m[1] ?? "");
    expect(captions).toHaveLength(5);
    for (const caption of captions) {
      expect(caption.length).toBeLessThanOrEqual(32);
    }
  });
});

describe("owner Q9 + `AM-34` t1 — the type is pre-filled, never recorded, from the filename", () => {
  it("recognises the filenames the owner actually uploads", async () => {
    // 2026-09-01: the owner uploaded `Leapswitch _GRP_MSA..30.07.2026.docx` and the
    // picker came up empty. Two causes, and only one was a bug here: the Gemini
    // key is invalid so the assist-lane proposal degrades to "not confident"
    // (external, reported), AND the filename hint only sat behind a link instead
    // of pre-filling the select. `AM-34` t1 authorises the filename as an input to
    // the proposal and says the proposal "pre-fills the intake select".
    const { typeHintFromFilename } = await import("@/lib/documentTypes");

    expect(typeHintFromFilename("Leapswitch _GRP_MSA..30.07.2026.docx")).toBe("MSA");
    expect(typeHintFromFilename("MSA-Feb.pdf")).toBe("MSA");
    expect(typeHintFromFilename("TOS-leapswitch.pdf")).toBe("TOS");
    expect(typeHintFromFilename("NDA.pdf")).toBe("NDA");
    expect(typeHintFromFilename("SLA-cloudpe.pdf")).toBe("SLA");
  });

  it("returns nothing rather than guessing when the filename says nothing", async () => {
    // Fail closed. A wrong pre-filled type that a hurried reader confirms is worse
    // than an empty select, because the confirmation is what the record rests on.
    const { typeHintFromFilename } = await import("@/lib/documentTypes");

    for (const name of ["scan_0001.pdf", "final version 3.docx", "document.pdf",
                        "Leapswitch-2026.pdf", "contract.docx"]) {
      expect(typeHintFromFilename(name)).toBeNull();
    }
  });

  it("does not match a type code buried inside a longer word", async () => {
    // Tokenised, not substring-matched: "msa" inside "christmas" or "damsagreed"
    // must not become a Master Services Agreement.
    const { typeHintFromFilename } = await import("@/lib/documentTypes");

    expect(typeHintFromFilename("christmas-party.pdf")).toBeNull();
    expect(typeHintFromFilename("damsafety-report.pdf")).toBeNull();
  });
});

describe("section references print one § — never two", () => {
  it("does not double a sign the document already carries", async () => {
    // Real documents supply `section_number` both ways: "17.2" from one parser,
    // "§17.2" from another. Every caller used to prepend `§` unconditionally, so
    // an MSA whose headings carry the sign rendered "§§1" on every clause row,
    // every finding card and every citation. Found by screenshot on 2026-09-01.
    const { sectionRef } = await import("@/lib/documentTypes");

    expect(sectionRef("§17.2")).toBe("§17.2");
    expect(sectionRef("17.2")).toBe("§17.2");
    expect(sectionRef(" §4 ")).toBe("§4");
    expect(sectionRef("¶9")).toBe("¶9");        // pilcrow is a section mark too
    expect(sectionRef(null)).toBeNull();
    expect(sectionRef("")).toBeNull();
    expect(sectionRef("   ")).toBeNull();
  });

  it("is the single shared implementation", async () => {
    // The first fix patched two of four callers and the other two kept printing
    // "§§". A rule copied into every caller is a rule that gets fixed in some of
    // them, so this asserts the callers import it rather than re-deriving it.
    const { readFileSync, readdirSync } = await import("node:fs");

    const dir = "src/components/workspace";
    const offenders = readdirSync(dir)
      .filter((f) => f.endsWith(".tsx"))
      .filter((f) => /`\s*§\$\{|>§\{/.test(readFileSync(`${dir}/${f}`, "utf8")));
    expect(offenders).toEqual([]);
  });
});

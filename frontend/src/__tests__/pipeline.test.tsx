/**
 * The Documents/Dashboard pipeline strip, section references, filename type
 * hinting, and the sign-out destination.
 *
 * Named after the component rather than the page: the page has been renamed twice
 * (workspace → documents → dashboard) and an earlier copy of this file, named
 * `documents-pipeline.test.tsx`, was lost in the churn.
 *
 * ⚠️ THE COPY ASSERTIONS ARE NOT STYLE CHECKS. The owner's reference design for
 * this screen described a different product, and its copy is the kind that gets
 * pasted back in:
 *
 * - `AI-01` (reaffirmed by `AM-25`): no LLM, RAG, embedding or vector database in
 *   the AUTHORITATIVE analysis path. The interface must not advertise the one
 *   architecture that is locked out of it.
 * - Owner Q9 (2026-08-19): Document Type is DECLARED by the uploader, never
 *   inferred. `AM-34` allows a suggestion; only the human's confirmation records
 *   the type.
 * - Rule 12 / DESIGN.md: a Finding reconstructs as Evidence → Fact → Standard →
 *   Rule → Result. No risk score, no confidence, no "the AI thinks".
 *
 * A screen that overpromises here tells a lawyer the engine did something it did
 * not do, which is the failure mode the whole specification is arranged against.
 */

import { readFileSync, readdirSync } from "node:fs";

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
    // DESIGN.md's prohibition, asserted on rendered copy — which the tree-wide
    // `check:terms` script cannot see.
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
    const copy = text();
    expect(copy).toContain("confirm type");
    expect(copy).toContain("you declare it");
  });
});

describe("rule 12 — the last step promises traceability, not insight", () => {
  it("says findings trace back to their source", () => {
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
    const svgs = html().match(/<svg[^>]*>/g) ?? [];
    expect(svgs.length).toBeGreaterThan(5);
    for (const svg of svgs) expect(svg).toContain('aria-hidden="true"');
  });

  it("uses no emoji — this codebase's marks are SVG", () => {
    // The reference used ▤ ◎ ▥ ◇ 🔒 →. Platform fonts render those at different
    // weights and baselines, visible in a row of five marks that must look equal.
    expect(html()).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("makes no security claim at all — that is not this strip's job", () => {
    // The "documents stay on our own infrastructure" line was removed on
    // 2026-09-01 (owner: essentials only). Locked 54.6 and `AM-30` t1 are
    // unchanged; the strip simply no longer speaks to them. A pure absence check
    // is the more useful assertion: it fails if anyone adds reassurance here.
    const copy = text();
    for (const theater of ["secure", "confidential", "encrypt", "bank-grade",
                           "military", "256-bit", "guaranteed", "100%",
                           "certified", "compliant", "trusted", "safe"]) {
      expect(copy).not.toContain(theater);
    }
  });

  it("keeps every caption short enough to sit on one or two lines", () => {
    // Not cosmetic. Five captions share a row and a baseline; a long one wraps
    // further than its neighbours and drags the row out of alignment — the defect
    // a screenshot caught when one label ran to two lines.
    const captions = [...html().matchAll(
      /class="ws-pipe__detail"[^>]*>([^<]*)</g)].map((m) => m[1] ?? "");
    expect(captions).toHaveLength(5);
    for (const caption of captions) expect(caption.length).toBeLessThanOrEqual(32);
  });
});

describe("section references print one § — never two", () => {
  it("does not double a sign the document already carries", async () => {
    // Real documents supply `section_number` both ways: "17.2" from one parser,
    // "§17.2" from another. Every caller used to prepend `§` unconditionally, so
    // an MSA whose headings carry the sign rendered "§§1" on every clause row,
    // finding card and citation. Found by screenshot.
    const { sectionRef } = await import("@/lib/documentTypes");

    expect(sectionRef("§17.2")).toBe("§17.2");
    expect(sectionRef("17.2")).toBe("§17.2");
    expect(sectionRef(" §4 ")).toBe("§4");
    expect(sectionRef("¶9")).toBe("¶9");          // pilcrow is a section mark too
    expect(sectionRef(null)).toBeNull();
    expect(sectionRef("")).toBeNull();
    expect(sectionRef("   ")).toBeNull();
  });

  it("is the single shared implementation", () => {
    // The first fix patched two of six callers and the rest kept printing "§§".
    // A rule copied into every caller is a rule that gets fixed in some of them —
    // this found the sixth (TranscriptTurn.tsx, where a parameter shadowed the
    // import).
    const dir = "src/components/workspace";
    const offenders = readdirSync(dir)
      .filter((f) => f.endsWith(".tsx"))
      .filter((f) => /`\s*§\$\{|>§\{/.test(readFileSync(`${dir}/${f}`, "utf8")));
    expect(offenders).toEqual([]);
  });
});

describe("owner Q9 + `AM-34` t1 — the type is pre-filled, never recorded", () => {
  it("recognises the filenames the owner actually uploads", async () => {
    // The owner uploaded `Leapswitch _GRP_MSA..30.07.2026.docx` and the picker
    // came up empty. Two causes: the Gemini key was a placeholder so the
    // assist-lane proposal degraded to "not confident", AND the filename hint only
    // sat behind a link instead of pre-filling. `AM-34` t1 authorises the filename
    // as an input and says the proposal "pre-fills the intake select".
    const { typeHintFromFilename } = await import("@/lib/documentTypes");

    expect(typeHintFromFilename("Leapswitch _GRP_MSA..30.07.2026.docx")).toBe("MSA");
    expect(typeHintFromFilename("MSA-Feb.pdf")).toBe("MSA");
    expect(typeHintFromFilename("TOS-leapswitch.pdf")).toBe("TOS");
    expect(typeHintFromFilename("NDA.pdf")).toBe("NDA");
    expect(typeHintFromFilename("SLA-cloudpe.pdf")).toBe("SLA");
  });

  it("returns nothing rather than guessing when the filename says nothing", async () => {
    // Fail closed. A wrong pre-filled type that a hurried reader confirms is
    // worse than an empty select, because the confirmation is what the record
    // rests on.
    const { typeHintFromFilename } = await import("@/lib/documentTypes");

    for (const name of ["scan_0001.pdf", "final version 3.docx", "document.pdf",
                        "Leapswitch-2026.pdf", "contract.docx"]) {
      expect(typeHintFromFilename(name)).toBeNull();
    }
  });

  it("does not match a type code buried inside a longer word", async () => {
    const { typeHintFromFilename } = await import("@/lib/documentTypes");
    expect(typeHintFromFilename("christmas-party.pdf")).toBeNull();
    expect(typeHintFromFilename("damsafety-report.pdf")).toBeNull();
  });
});

describe("signing out lands on /login, from every page", () => {
  it("puts the redirect in signOut, not in one shell's guard", () => {
    // Verified in a browser: /dashboard redirected (WorkspaceShell has its own
    // signed-out guard) while /reviews, /contracts, /audit, /configuration and
    // /admin stayed put and rendered "You are signed out" — which reads as a
    // broken page rather than a completed action.
    //
    // The fix belongs in `signOut` because signing out is one act with one
    // outcome; a per-shell guard is how the two diverged.
    const src = readFileSync("src/lib/session.tsx", "utf8");
    const body = src.slice(src.indexOf("const signOut ="), src.indexOf("const value ="));

    expect(body).toContain('router.replace("/login")');
    // In `finally`: a logout whose request failed has still discarded the local
    // session, so leaving the user on an authenticated-looking page is worse.
    expect(body).toContain("finally");
    // `replace`, not `push` — Back must not return to a now-signed-out page.
    expect(body).not.toContain("router.push");
  });
});

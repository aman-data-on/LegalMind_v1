/**
 * S6 (Final card note, c4) and S5 (convert to our paper, d3) — static render, house
 * idiom. The server's facts in, plain words out; nothing decided here (rule 18).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
  <a href={href} {...rest}>{children}</a> }));

import { ConvertPaper } from "@/components/workspace/ConvertPaper";
import { CONVERT_COPY, FINAL_CARD, signingNoteText } from "@/lib/labels";

const note = {
  contract_name: "Master Services Agreement — Client", doc_id: "LM-ABCD1234-v3-0123abcd", pages: 24,
  signature_page: 24, pdf_sha256: "f".repeat(64), pdf_name: "x.pdf", word_name: "x.docx",
  signers: [{ party: "Party One", name: "A Person", designation: "Director", email: "a@example.com" },
            { party: "Party Two", name: "B Person", designation: "", email: "b@example.com" }],
};

describe("the Final card's note (S6)", () => {
  it("carries only the app's facts, the PDF-not-Word line and the Leegality hint", () => {
    const text = signingNoteText(note);
    expect(text).toContain("Contract: Master Services Agreement — Client");
    expect(text).toContain("Document ID: LM-ABCD1234-v3-0123abcd");
    expect(text).toContain("Pages: 24. Signatures go on page 24 of 24.");
    expect(text).toContain("- Party One: A Person, Director, a@example.com");
    expect(text).toContain("- Party Two: B Person, b@example.com");
    expect(text).toContain("Sign the PDF, not the Word file.");
    expect(text).toContain("Leegality: place the signatures on page 24 of 24, not the default bottom-left of every page");
    expect(text).toContain(`PDF SHA-256: ${"f".repeat(64)}`);
  });
  it("leaves out what paper does not have", () => {
    const text = signingNoteText({ ...note, doc_id: null, signature_page: null, signers: [] });
    expect(text).not.toContain("Document ID");
    expect(text).not.toContain("Signers:");
    expect(text).toContain("Signatures go on the signature page.");
  });
  it("names the two files as the spec does", () => {
    expect(FINAL_CARD.pdfForSignature).toBe("PDF for signature");
    expect(FINAL_CARD.wordCopy).toBe("Word copy (not for signing)");
  });
});

describe("convert to our paper (S5)", () => {
  it("says only accepted points carry over and starts from New contract", () => {
    const html = renderToStaticMarkup(<ConvertPaper contractId="c1" draftId={null} onPick={() => {}} onConverted={() => {}} />);
    expect(html).toContain(CONVERT_COPY.carryOver);
    expect(html).toContain("Only the points you accepted carry over; the rest of their paper does not.");
    expect(html).toContain('href="/contracts/new?convert=c1"');
  });
  it("with a draft, checks first (the server's dry run)", () => {
    const html = renderToStaticMarkup(<ConvertPaper contractId="c1" draftId="d1" onPick={() => {}} onConverted={() => {}} />);
    expect(html).toContain(CONVERT_COPY.checking);
  });
});

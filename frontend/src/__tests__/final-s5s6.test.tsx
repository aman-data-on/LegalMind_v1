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

vi.mock("@/components/Toast", () => ({ toast: vi.fn(), toastFailure: () => () => undefined }));
vi.mock("@/components/workspace/findingsState", () => ({ useFindingsStateOptional: () => null }));

import { toast } from "@/components/Toast";
import { ConvertBody } from "@/components/workspace/ConvertPaper";
import { FinalCard, copyNote } from "@/components/workspace/FinalCopy";
import type { ConvertPlan } from "@/lib/package";
import type { DocumentVersion } from "@/lib/types";

describe("the Final card (S6)", () => {
  it("offers the PDF for signature and the Word copy, the PDF first", () => {
    const v = { id: "v2", version_number: 2, mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      final_copy: { of_version_id: "v1", mode: "copy", agreed: [] } } as unknown as DocumentVersion;
    const html = renderToStaticMarkup(<FinalCard version={v} versions={[v]} since="2026-11-16T10:00:00Z" />);
    expect(html).toContain("Final contract ready for signature");
    expect(html.indexOf("PDF for signature")).toBeLessThan(html.indexOf("Word copy (not for signing)"));
    const pdfOnly = renderToStaticMarkup(<FinalCard version={{ ...v, mime_type: "application/pdf" } as DocumentVersion}
                                                    versions={[v]} since="2026-11-16T10:00:00Z" />);
    expect(pdfOnly).not.toContain("Word copy");
  });
  it("Copy writes the note to the clipboard and confirms it", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    expect(await copyNote("the note")).toBe(true);
    expect(writeText).toHaveBeenCalledWith("the note");
    expect(toast).toHaveBeenCalledWith(FINAL_CARD.copied);
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
    expect(await copyNote("the note")).toBe(false);
    vi.unstubAllGlobals();
  });
});

describe("the conversion's dry run (S5)", () => {
  const plan: ConvertPlan = {
    available: false, entries: [], precedence: null, entries_sha256: "x",
    blockers: [
      { code: "ANCHOR_REQUIRED", row_key: "r1", message: "This point has no clause of our contract to go with — choose the clause it is added after." },
      { code: "UNDEFINED_TERM", row_key: "r2", message: "Their text uses “Service Provider”, a term our contract does not define — Legal writes our wording instead." }],
    choices: [{ key: "K1", number: "4.2", heading: null }, { key: "K2", number: "5", heading: "Fees" }],
  };
  it("lists every blocker and asks where an unanchored point goes", () => {
    const html = renderToStaticMarkup(<ConvertBody plan={plan} addAfter={{}} busy={false} onPick={() => {}}
                                                   setAnchor={() => {}} onConvert={() => {}} />);
    expect(html).toContain(CONVERT_COPY.blocked);
    expect(html).toContain("choose the clause it is added after");
    expect(html).toContain("Service Provider");
    expect(html).toContain(CONVERT_COPY.addAfter);
    expect(html.match(/<select/g)).toHaveLength(1);          // only the unanchored row
    expect(html).toContain('<option value="K2">Clause 5, Fees</option>');
    expect(html).not.toContain(CONVERT_COPY.convert);        // not available: no button
  });
  it("offers the conversion once nothing blocks", () => {
    const html = renderToStaticMarkup(<ConvertBody plan={{ ...plan, available: true, blockers: [], entries: [
      { n: 1, op: "replace", text: "t", target: { key: "K2", number: "5", heading: "Fees" }, answer: "accept_theirs" }] }}
      addAfter={{}} busy={false} onPick={() => {}} setAnchor={() => {}} onConvert={() => {}} />);
    expect(html).toContain("1 point carries over:");
    expect(html).toContain(CONVERT_COPY.convert);
  });
});

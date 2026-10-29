/** AM-236 (2026-10-29): one contract in Ask, as a lawyer's memo — the assumptions first
 *  with one tap to correct them, the points worst first (top seven, then "Show more"),
 *  our rule and our wording, what matches tucked away, and no confidence words.
 *  Synthetic data. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ContractMemo, MEMO_SHOWN, memoMarkdown } from "@/components/workspace/DealReview";
import type { DealFile, DealRow, DealStatus } from "@/lib/types";

const file: DealFile = { id: "f", name: "msa.docx", refused: null, signed: false, wins: true,
  changes: 2, notes: [], precedence: [], unchecked: [] };
const row = (n: number, needs: DealStatus, extra: Partial<DealRow["cells"][string]> = {}): DealRow => ({
  code: `R${n}`, topic: `Topic ${n}`, detail: null, rule: { section: "9" },
  cells: { f: { finding_id: `x${n}`, classification: needs === "FINE" ? "MATCH" : "DEVIATION",
    status: needs, action: needs === "FINE" ? null : "Send our wording", quote: `Clause words ${n}`,
    clause: `${n}.1`, page: 1, changed: n === 0, ...extra } },
  status: needs, needs, decided_by: "f", also: [] });
const rows: DealRow[] = [
  row(0, "MUST_CHANGE", { proposal: { section: "9", kind: "DRAFTING_LANGUAGE",
    label: "Constitution §9 — Drafting Notes", text: "Liability is capped at twelve months." } }),
  ...Array.from({ length: 8 }, (_, i) => row(i + 1, "ASK_CHANGE")),
  row(20, "FINE"),
];
const memo = (extra = {}) => renderToStaticMarkup(
  <ContractMemo file={file} rows={rows} answers={{ side: "provider", side_read: true }}
                onCorrect={() => {}} onDraft={() => {}} {...extra} />);

describe("ContractMemo", () => {
  it("says what it assumed and offers the corrections", () => {
    const html = memo();
    expect(html).toContain("we provide the service");
    expect(html).toContain("still being negotiated");
    expect(html).toContain("(side read from the parties clause)");
    expect(html).toContain("We&#x27;re the buyer");
    expect(html).toContain("It’s signed");
  });

  it("shows the top points worst first, the rest behind Show more", () => {
    const html = memo();
    expect(html.indexOf("Topic 0")).toBeLessThan(html.indexOf("Topic 1"));
    expect(html).toContain(`Topic ${MEMO_SHOWN - 1}`);
    expect(html).not.toContain(`Topic ${MEMO_SHOWN}<`);
    expect(html).toContain(`Show ${9 - MEMO_SHOWN} more`);
    expect(html).toContain("Must change");                 // the status in words
    expect(html).toContain("Changed by the client");
    expect(html).toContain("Our rule: Section 9");
    expect(html).toContain("Our wording — Constitution §9 — Drafting Notes");
    expect(html).toContain("1 point matches our positions");
    expect(html).not.toMatch(/confiden|probab|likely|%/i);
  });

  it("never reviews a file it could not read whole", () => {
    const html = renderToStaticMarkup(
      <ContractMemo file={{ ...file, refused: "PARTIAL_READ", unread: [9, 10] }} rows={[]}
                    answers={{}} onCorrect={() => {}} onDraft={() => {}} />);
    expect(html).toContain("Pages 9, 10 could");
    expect(html).not.toContain("Draft a reply");
  });

  it("copies as a memo with our wording", () => {
    const md = memoMarkdown(file, rows.slice(0, 2));
    expect(md).toContain("**Must change**");
    expect(md).toContain("- Topic 0 (clause 0.1): Clause words 0 — our rule: Section 9 — our wording: \"Liability is capped at twelve months.\"");
  });
});

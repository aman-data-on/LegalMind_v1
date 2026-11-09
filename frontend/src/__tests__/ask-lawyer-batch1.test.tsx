/**
 * Lawyer batch 1 (owner, 2026-11-09): a screenshot is accepted and said to be read from
 * an image (B1.1); pictures in a file are listed in the server's fixed words (B1.2); a
 * one-contract review shows the lawyer's groups in order, in our favour as its own group
 * that is never counted as a match (B1.5). Synthetic data, no client named.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialList, statusText } from "@/components/workspace/ChatMaterial";
import { ContractMemo } from "@/components/workspace/DealReview";
import type { ChatAttachment, DealFile, DealRow, DealStatus } from "@/lib/types";

const shot: ChatAttachment = { id: "a1", kind: "FILE", filename: "clause.png",
  mime_type: "image/png", byte_size: 10, status: "READY", failure_code: null,
  created_at: "2026-11-09T00:00:00Z", expires_at: "2026-12-09T00:00:00Z",
  pictures: ["Page 1: a picture covering the whole page; its text was read by OCR."] };

describe("B1.1/B1.2 chat material", () => {
  it("accepts a PNG or JPG in the chat composer", () => {
    const src = readFileSync(join(__dirname, "../components/workspace/AskWorkspace.tsx"), "utf8");
    expect(src).toContain('accept=".pdf,.docx,.md,.txt,.png,.jpg,.jpeg"');
  });

  it("says a picture was read from an image and lists the pictures", () => {
    expect(statusText(shot)).toBe("Read from an image");
    const html = renderToStaticMarkup(<MaterialList items={[shot]} />);
    expect(html).toContain("Page 1: a picture covering the whole page; its text was read by OCR.");
    expect(html).not.toMatch(/\bsigned\b|\bstamped\b/i);
  });
});

const file: DealFile = { id: "f", name: "msa.docx", refused: null, signed: false, wins: true,
  changes: 0, notes: [], precedence: [], unchecked: [] };
const row = (n: number, needs: DealStatus, extra = {}): DealRow => ({
  code: `R${n}`, topic: `Topic ${n}`, detail: null, rule: { section: "9" },
  cells: { f: { finding_id: `x${n}`, classification: needs === "FINE" ? "MATCH" : "DEVIATION",
    status: needs, action: "an action", quote: `Clause words ${n}`, clause: `${n}.1`, page: 1,
    changed: false, ...extra } },
  status: needs, needs, decided_by: "f", also: [] });
const memo = (rows: DealRow[]) => renderToStaticMarkup(
  <ContractMemo file={file} rows={rows} answers={{ side: "provider" }}
                onCorrect={() => {}} onDraft={() => {}} />);

describe("B1.5 contract memo groups", () => {
  it("shows the groups in order, favour apart from the match count", () => {
    const html = memo([row(1, "MUST_CHANGE"), row(2, "ASK_CHANGE"), row(3, "LEGAL_DECIDES"),
      row(4, "FAVOUR", { counsel: { text: "a shorter period may be read as a penalty",
        source: "standard" } }), row(5, "FINE"), row(6, "FINE")]);
    const at = (s: string) => html.indexOf(s);
    expect(at("Must change before signing")).toBeGreaterThan(-1);
    expect(at("Must change before signing")).toBeLessThan(at("To negotiate"));
    expect(at("To negotiate")).toBeLessThan(at("In our favour — keep; usable as leverage"));
    expect(at("In our favour — keep")).toBeLessThan(at("2 points match our positions"));
    expect(html).toContain("May draw push-back or not hold — a shorter period may be read");
    expect(html).not.toMatch(/confiden|probab|likely|%/i);
  });

  it("hides the favour group when nothing favours us, and adds no push-back note unsourced", () => {
    const html = memo([row(1, "MUST_CHANGE"), row(5, "FINE")]);
    expect(html).not.toContain("In our favour");
    const bare = memo([row(4, "FAVOUR")]);
    expect(bare).toContain("In our favour — keep");
    expect(bare).not.toContain("push-back");
  });
});

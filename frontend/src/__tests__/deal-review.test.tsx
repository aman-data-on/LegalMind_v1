/** AM-229/AM-230 (2026-10-28): the assistant's questions before a side-by-side review,
 *  and the review itself — status in words beside its icon, never colour alone; fine
 *  points hidden until asked for; the table copies as Markdown. Synthetic data. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { answersText, DealQuestions } from "@/components/workspace/DealQuestions";
import { asMarkdown, DealReview, STATUS } from "@/components/workspace/DealReview";
import type { DealFile, DealQuestion, DealRow } from "@/lib/types";

const questions: DealQuestion[] = [
  { id: "signed", text: "Which of these documents is already signed?", why: "What is signed is agreed.",
    multiple: true, default: ["none"],
    options: [{ value: "a", label: "MOU" }, { value: "b", label: "MSA" },
              { value: "none", label: "None is signed yet" }] },
  { id: "wins", text: "Which one should win?", why: "Clause 13: “this MOU shall prevail”.",
    multiple: false, default: "open",
    options: [{ value: "a", label: "MOU" }, { value: "open", label: "Neither" }] },
];

const file = (id: string, name: string, extra: Partial<DealFile> = {}): DealFile => ({
  id, name, refused: null, signed: false, wins: false, changes: 0, notes: [], precedence: [],
  unchecked: [], ...extra });
const files = [file("a", "MOU", { signed: true, wins: true }),
               file("b", "MSA", { changes: 3, unchecked: [{ section: "8", title: "Fees",
                 clause: "8.2", kind: "Changed", removed: "7 days", added: "30 days" }] })];
const cell = (status: DealRow["status"], plain: string, extra = {}) => ({
  finding_id: plain, classification: status === "FINE" ? "MATCH" : "DEVIATION", status,
  action: status === "MUST_CHANGE" ? "Must change before signing" : null, quote: `${plain} (quote)`,
  clause: "9", page: 1, changed: false, plain, ...extra });
const rows: DealRow[] = [
  { code: "CAP", topic: "Liability", detail: "A cap", rule: { section: "9", value: { preferred: 12, unit: "MONTHS" } },
    cells: { a: cell("AGREED", "12 months"), b: cell("MUST_CHANGE", "uncapped", { changed: true }) },
    status: "AGREED", needs: "MUST_CHANGE", decided_by: "a",
    also: [{ file: "b", status: "MUST_CHANGE", action: "Must change before signing" }] },
  { code: "LAW", topic: "Governing law", detail: null, rule: { section: "22" },
    cells: { a: cell("FINE", "Indian law"), b: cell("FINE", "Indian law") },
    status: "FINE", needs: "FINE", decided_by: "a", also: [] },
];
const counts = { MUST_CHANGE: 1, ASK_CHANGE: 0, LEGAL_DECIDES: 0, AGREED: 0, FINE: 1 };

describe("the assistant's questions", () => {
  it("are real inputs with each one's reason, the defaults chosen, and a way to skip", () => {
    const html = renderToStaticMarkup(<DealQuestions questions={questions} onSubmit={() => undefined} />);
    expect(html).toContain("<fieldset");
    expect(html).toContain('type="checkbox"');
    expect(html).toContain('type="radio"');
    expect(html).toContain("this MOU shall prevail");
    expect(html).toContain("Skip — use the defaults");
    expect(html.match(/checked=""/g)).toHaveLength(2);          // None, Neither
  });

  it("once answered show the answers, and say them in words for the chat", () => {
    const html = renderToStaticMarkup(<DealQuestions questions={questions} onSubmit={() => undefined}
                                                     settled={{ signed: ["a"], wins: "a" }} />);
    expect(html).not.toContain("<input");
    expect(html).toContain("MOU");
    expect(answersText(questions, { signed: ["a"], wins: "open" }))
      .toBe("Which of these documents is already signed? MOU.\nWhich one should win? Neither.");
  });
});

describe("the side-by-side review", () => {
  it("shows status in words, keeps another document's worse point, hides fine rows", () => {
    const html = renderToStaticMarkup(<DealReview files={files} rows={rows} counts={counts} />);
    expect(html).toContain(STATUS.AGREED.label);
    expect(html).toContain(STATUS.MUST_CHANGE.label);
    expect(html).toContain("Changed by the client");
    expect(html).toContain("Our rule: Section 9 · 12 months");
    expect(html).not.toContain("Governing law");                    // fine: hidden
    expect(html).toContain("Show the 1 points that are fine");
    expect(html).toContain("1 client changes no rule checks");
    expect(html).not.toMatch(/confiden(ce|t) score|probab/i);
  });

  it("copies as a Markdown table, every row and both documents", () => {
    const md = asMarkdown(files, rows);
    expect(md.split("\n")).toHaveLength(4);
    expect(md).toContain("| Topic | MOU | MSA | Our rule | Status → what to do |");
    expect(md).toContain("MSA: Must change");
  });
});

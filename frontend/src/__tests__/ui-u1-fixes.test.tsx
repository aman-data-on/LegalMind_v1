/**
 * Fix batch U1 (full-stack audit 2026-11-23): "UI wrong or risky". Static markup and the
 * real stylesheet only (Step 39: no DOM library); the browser pass is in the build report.
 */
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ReportDocumentView } from "@/components/workspace/ReviewReportPage";
import { TakeBackFromLegal } from "@/components/workspace/TakeBackFromLegal";
import { REPORT_COPY, REVIEWS_QUEUE_COPY, TAKE_BACK_COPY, reviewStatusLabel } from "@/lib/labels";
import type { ReportBlock } from "@/lib/types";

const css = readFileSync("src/app/dashboard/workspace.css", "utf8");
const ENGINE = /analys|resolved|requirement|evaluat|deviation|finding|§|\.docx/i;

describe("UI-02: taking a contract back from Legal asks first", () => {
  it("renders only the trigger — nothing is withdrawn on render, the dialog opens on click", () => {
    const html = renderToStaticMarkup(
      <TakeBackFromLegal reviewId="r" holder={{ user_id: "u", name: "Asha", email: "a@x" }} onDone={async () => {}} />);
    expect(html).toBe(`<button type="button" class="ws-linkbtn">${TAKE_BACK_COPY.open}</button>`);
    expect(html).not.toContain("role=\"dialog\"");
  });
  it("says only what the server does (r2: the lawyer is not told; the note goes)", () => {
    expect(TAKE_BACK_COPY.open).toBe("Take back from Legal");
    expect(TAKE_BACK_COPY.title).toBe("Take this contract back from Legal?");
    expect(TAKE_BACK_COPY.body("Asha")).toBe("It leaves Asha's queue. Answers Legal already gave are kept. Asha is not "
      + "told, so let them know. When you send it again, write a new note.");
    expect(TAKE_BACK_COPY.body("Asha")).not.toMatch(/stops working/);
    expect(TAKE_BACK_COPY.done.startsWith("Taken back")).toBe(true);
    expect(TAKE_BACK_COPY.confirm).toBe("Take back");
  });
});

describe("UI-05 and UI-10: list cells read as separate facts and whole names", () => {
  it("stacks the counts wherever CountsCell renders, not only on home", () => {
    expect(css).not.toMatch(/\.ws-home \.ws-home__counts/);
    expect(css).toMatch(/\n\.ws-home__counts \{ display: flex; flex-direction: column; gap: var\(--ws-s1\)/);
  });
  it("keeps the owner's one-line rule in desktop tables; two lines only in phone cards", () => {
    // r2: the 2026-09-22 owner rule stands, its comment restored
    expect(css).toContain("/* Single-line ellipsis truncation (owner, 2026-09-22");
    expect(css).toMatch(/\.ws-cl__docname \{[^}]*white-space: nowrap/);
    expect(css).toMatch(/a\.ws-hometable__name \{[^}]*white-space: nowrap/);
    const rule = css.slice(css.lastIndexOf("/* UI-10"));
    expect(rule).toContain("STANDS in desktop tables");
    expect(css).toMatch(/\.ws-cl__railname \{[^}]*white-space: nowrap/);   // the rail keeps one line
    expect(rule).not.toMatch(/\.ws-cl__railname \{ display: -webkit-box/);
    for (const [width, name] of [["720px", "a.ws-hometable__name"], ["760px", ".ws-cl__docname"], ["640px", "td:nth-child(1) > a"]] as const) {
      expect(rule).toMatch(new RegExp(`@media \\(max-width: ${width}\\) \\{\\s*[^}]*${name.replace(/[.()>]/g, "\\$&")}[^}]*-webkit-line-clamp: 2`));
    }
    expect(rule).not.toContain(":focus-visible");      // no row jump while tabbing
  });
});

describe("UI-09: the Reviews queue speaks the row chips' words", () => {
  it("filters with the same words the rows wear, none of them an engine word", () => {
    const texts = REVIEWS_QUEUE_COPY.filters.map((f) => f.text);
    // r2: no "Checked" filter — it named the date column too; ANALYSIS_COMPLETE lasts one call
    expect(texts).toEqual(["All", "With Legal", "Decided", "Closed"]);
    for (const f of REVIEWS_QUEUE_COPY.filters.slice(1)) expect(reviewStatusLabel(f.id)).toBe(f.text);
    for (const text of [...texts, ...Object.values(REVIEWS_QUEUE_COPY.columns), REVIEWS_QUEUE_COPY.emptyAll]) {
      expect(text).not.toMatch(ENGINE);
    }
  });
  it("never shows RESOLVED as a match (rule 14), and no review state says 'analysis'", () => {
    expect(reviewStatusLabel("RESOLVED")).toBe("Decided");
    for (const s of ["PROCESSING", "ANALYSIS_COMPLETE", "ANALYSIS_FAILED", "RESOLVED"]) {
      expect(reviewStatusLabel(s)).not.toMatch(/match|analys/i);
    }
  });
  it("tells rows apart with the Contracts facts line, never a stretched pill (r2)", () => {
    const page = readFileSync("src/app/dashboard/reviews/page.tsx", "utf8");
    expect(page).not.toContain("ws-chip--type");
    expect(page).toContain("ws-hometable__facts");
    expect(REVIEWS_QUEUE_COPY.version(2, "Client's markup")).toBe("Version 2, client's markup");
    expect(REVIEWS_QUEUE_COPY.version(3)).toBe("Version 3");
    expect(REVIEWS_QUEUE_COPY.withWhom("Asha")).toBe("With Asha");
  });
  it("never shows a raw status code as a tooltip (Reviews and the Legal queue)", () => {
    for (const f of ["src/app/dashboard/reviews/page.tsx", "src/app/dashboard/legal/page.tsx"]) {
      expect(readFileSync(f, "utf8")).not.toContain("title={review.status}");
    }
  });
});

describe("UI-12: the report's headings go h1 → h2 → h3 and its export says what it downloads", () => {
  const b = (kind: ReportBlock["kind"], text = "", label = "", rows: string[][] = []) =>
    ({ kind, text, label, rows }) as ReportBlock;
  it("uses h2 for sections and h3 under them — never h4, never a skipped level", () => {
    const html = renderToStaticMarkup(<ReportDocumentView blocks={[
      b("h1", "MSA"), b("kv", "Version 2, the client's version", "Document"),
      b("h2", "Summary"), b("p", "Three points need a decision."),
      b("h2", "Appendix — audit record"), b("h3", "Sources"), b("p", "x"),
    ]} />);
    expect(html).toContain("<h2 class=\"ws-report__h\">Summary</h2>");
    expect(html).not.toMatch(/<h[34] class="ws-report__h"/);
    expect(html).not.toContain("<h4");
  });
  it("names the export plainly: the report on the page, as PDF or Word", () => {
    expect(REPORT_COPY.exportLine).toBe("Download the report shown below:");
    expect([REPORT_COPY.pdf, REPORT_COPY.word]).toEqual(["PDF", "Word"]);
    expect(Object.values(REPORT_COPY).join(" ")).not.toMatch(ENGINE);
  });
});

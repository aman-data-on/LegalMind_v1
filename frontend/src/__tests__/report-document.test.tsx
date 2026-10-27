/**
 * AB-103 (owner, 2026-10-22): the Report page shows the report the reader downloads —
 * the server's blocks, rendered in order, tables as tables, nothing invented here.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ReportDocumentView } from "@/components/workspace/ReviewReportPage";
import type { ReportBlock } from "@/lib/types";

const b = (kind: ReportBlock["kind"], text = "", label = "", rows: string[][] = []) =>
  ({ kind, text, label, rows }) as ReportBlock;

describe("the report preview", () => {
  it("renders the server's blocks in order, with tables and grouped bullets", () => {
    const html = renderToStaticMarkup(<ReportDocumentView blocks={[
      b("h1", "UI audit MSA"),
      b("h2", "Where this review stands"),
      b("p", "Review complete: Sign after our changes"),
      b("kv", "14 of 14 decided", "Points needing a decision"),
      b("h2", "Changes to send to the client (1)"),
      b("table", "", "", [["Point", "Clause"], ["Data purge", "§7.6.6 · p.8"]]),
      b("bullet", "Arbitration — §19.2"), b("bullet", "Governing law — §19.1"),
      b("quote", "7.6.6 Leapswitch shall purge…", "§7.6.6 · p.8"),
    ]} />);
    const at = (s: string) => html.indexOf(s);
    expect(at("Where this review stands")).toBeLessThan(at("Changes to send to the client"));
    expect(html).toContain("<th scope=\"col\">Point</th>");
    expect(html).toContain("<td>§7.6.6 · p.8</td>");
    expect(html.match(/<ul/g)).toHaveLength(1);                 // consecutive bullets: one list
    expect(html).toContain("<strong>Points needing a decision:</strong> 14 of 14 decided");
    expect(html).not.toMatch(/confidence|verdict/i);
  });
});

describe("the report read in two minutes (owner, 2026-10-27)", () => {
  const blocks = [
    b("h1", "MSA"), b("kv", "v1 — MSA.pdf", "Document"),
    b("h2", "Summary"), b("kv", "do not sign as drafted — 1 point must change", "Recommendation"),
    b("h2", "Still to decide (2)"),
    b("kv", "Legal rules on it before anything is sent.", "Needs a decision"),
    b("table", "", "", [["Point", "Status", "Clause", "What the contract says"],
                        ["1. Liability", "Needs a decision", "§17.2 · p.16", "6 months and unlimited"],
                        ["2. Dispute window", "Change needed", "§8.3 · p.8", "5 days vs our 15"]]),
    b("h2", "The points that need action, in detail"),
    b("h3", "1. Liability"), b("kv", "Needs a decision", "Status"),
    b("kv", "Request revised wording — not negotiable", "Recommended"),
    b("h3", "2. Dispute window"), b("kv", "Change needed", "Status"),
    b("kv", "Seek legal review", "Recommended"),
    b("h2", "Appendix — audit record"), b("kv", "b0f9cba3", "Configuration snapshot"),
  ];
  const html = renderToStaticMarkup(<ReportDocumentView blocks={blocks} />);

  it("answers first, then explains its words", () => {
    expect(html).toContain('<p class="ws-reportdoc__lead">Do not sign as drafted');
    expect(html.indexOf("ws-reportdoc__lead")).toBeLessThan(html.indexOf("ws-reportdoc__key"));
  });

  it("lists each point once, its own step on the card and the default left to the key", () => {
    expect(html.match(/1\. Liability/g)).toHaveLength(1);
    expect(html).not.toContain("<table");                       // the table opened into cards
    expect(html).not.toContain("in detail");                    // nothing left to repeat
    expect(html).toContain('<span class="ws-reportdoc__step">Request revised wording');
    const closed = [...html.matchAll(/<summary>(.*?)<\/summary>/g)].map((m) => m[1]).join("");
    expect(closed).not.toContain("Seek legal review");        // only inside, once opened
  });

  it("folds the appendices", () => {
    expect(html).toMatch(/<details class="ws-reportdoc__more"><summary>Audit record<\/summary>/);
  });
});

describe("the client's changes as a redline (owner, 2026-10-27)", () => {
  it("strikes what was removed, underlines what was added, tags only what to read", () => {
    const html = renderToStaticMarkup(<ReportDocumentView blocks={[
      b("h2", "The client's changes (1 clause)"),
      b("h3", "§7 Term and termination"),
      b("kv", "2 changes, 1 to read.", "The difference"),
      b("change", "7.2 · Changed", "", [["7.2", "Changed", "ninety days", "thirty days", ""]]),
      b("change", "7.5 · Added", "", [["7.5", "Added", "", "No fee on exit.", "read"]]),
    ]} />);
    expect(html).toContain("<del>ninety days</del> <ins>thirty days</ins>");
    expect(html.match(/Please read/g)).toHaveLength(1);
    expect(html).toContain("2 changes, 1 to read.");          // the card's own line
  });
});

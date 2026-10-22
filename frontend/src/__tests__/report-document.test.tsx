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

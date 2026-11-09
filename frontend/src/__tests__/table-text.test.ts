/** Tables in the text view (N11 #1): pipe rows set as cells, merged rows spanning,
 *  a nested table kept inside its cell, prose around a table left as prose. */
import { describe, expect, it } from "vitest";

import { hasTable, isFigure, textBlocks } from "@/components/workspace/tableText";

describe("textBlocks", () => {
  const content = [
    "SLA / Service Credit table",
    "| Service | Commitment | Credit |",
    "| VPS | Automatic | As notified |",
    "| Grand total | ₹ 25,23,430.00 |",
    "| Payment milestones | [Milestone | Share; On signing | 50%] | — |",
    "After the table.",
  ].join("\n");
  const blocks = textBlocks(content);

  it("cuts prose and table apart, in order", () => {
    expect(blocks.map((b) => b.kind)).toEqual(["text", "table", "text"]);
    expect(hasTable(content)).toBe(true);
    expect(hasTable("A clause | with a bar in it.")).toBe(false);
  });

  it("reads cells, stretches a merged row and keeps a nested table in its cell", () => {
    const table = blocks[1]!;
    if (table.kind !== "table") throw new Error("not a table");
    expect(table.rows[0]!.map((c) => c.text)).toEqual(["Service", "Commitment", "Credit"]);
    expect(table.rows[2]!.map((c) => c.span)).toEqual([2, 1]);
    expect(table.rows[3]!).toHaveLength(3);
    expect(table.rows[3]![1]!.nested).toEqual([["Milestone", "Share"], ["On signing", "50%"]]);
    expect(isFigure("₹ 25,23,430.00")).toBe(true);
    expect(isFigure("Grand total")).toBe(false);
  });
});

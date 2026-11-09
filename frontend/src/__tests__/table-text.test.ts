/** Tables in the text view (N11 #1): pipe rows set as cells, merged rows spanning,
 *  a nested table kept inside its cell, prose around a table left as prose. */
import { describe, expect, it } from "vitest";

import { hasTable, isFigure, tableCells, textBlocks } from "@/components/workspace/tableText";

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

  it("knows where each cell and inner cell starts in the row, so a saved highlight is drawn there", () => {
    for (const block of blocks) {
      if (block.kind === "text") {
        expect(content.slice(block.start, block.start + block.text.length)).toBe(block.text);
        continue;
      }
      for (const row of block.rows) {
        for (const c of row) {
          expect(content.slice(c.start, c.start + c.text.length)).toBe(c.text);
          c.nested?.forEach((r, j) => r.forEach((t, k) => {
            const at = c.nestedStart![j]![k]!;
            expect(content.slice(at, at + t.length)).toBe(t);
          }));
        }
      }
    }
  });
});

describe("empty cells keep their column (verifier item 3)", () => {
  it("splits a signature row with empty cells into four columns", () => {
    const rows = textBlocks("| Name | Designation | Name | Designation |\n| Sign | | Sign | |\n| Asha | Director | Ravi | |");
    const table = rows[0]!;
    expect(table.kind).toBe("table");
    if (table.kind !== "table") return;
    expect(table.rows.map((r) => r.map((c) => c.text))).toEqual([
      ["Name", "Designation", "Name", "Designation"],
      ["Sign", "", "Sign", ""],
      ["Asha", "Director", "Ravi", ""]]);
    expect(table.rows[2]![3]!.text).toBe("");          // the client's Designation stays empty
  });
  it("keeps a nested table inside a cell", () => {
    expect(tableCells("| a | [x | y; z | w] | |").map((c) => c.text)).toEqual(["a", "[x | y; z | w]", ""]);
  });
});

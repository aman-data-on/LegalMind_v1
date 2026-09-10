/**
 * The Contents as a tree (owner, 2026-09-10): the document's own numbers and
 * titles, parent/child by number, no invented "§", no party-block connectives,
 * and the two headings the parser missed because their titles carry commas.
 *
 * The rows are the shape of the live distribution agreement measured that day:
 * `8. ORDERING, FORECASTING, AND DELIVERY` arrived with a number but no heading
 * flag; `8.4 …` arrived with neither (Word's U+200B numbering); `BETWEEN` and
 * `AND` arrived flagged as headings.
 */
import { describe, expect, it } from "vitest";

import {
  allOutlineNodes,
  isTitleLine,
  outlineAncestors,
  outlineTree,
  rollupBucket,
  visibleOutline,
} from "@/components/workspace/model";
import type { EvidenceRow } from "@/lib/types";

let offset = 0;
function row(content: string, opts: { number?: string | null; title?: string | null; heading?: boolean } = {}): EvidenceRow {
  offset += content.length + 1;
  return {
    id: `r${offset}`, content, page_number: null,
    section_number: opts.number ?? null, section_title: opts.title ?? null,
    is_heading: opts.heading ?? false, start_offset: offset, end_offset: offset + content.length,
    source_type: "TEXT",
  } as unknown as EvidenceRow;
}

const ROWS = [
  row("DISTRIBUTION AGREEMENT", { title: "DISTRIBUTION AGREEMENT", heading: true }),
  row("BETWEEN", { title: "BETWEEN", heading: true }),
  row("AND", { title: "AND", heading: true }),
  row("RECITALS", { title: "RECITALS", heading: true }),
  row("1. DEFINITIONS AND INTERPRETATION", { number: "1", title: "DEFINITIONS AND INTERPRETATION", heading: true }),
  row('1.1 "Affiliate" means, with respect to any Party, any entity that controls it.', { number: "1.1", title: '"Affiliate" means, with respect to any Party, any entity that controls it.' }),
  row("8. ORDERING, FORECASTING, AND DELIVERY", { number: "8", title: "ORDERING, FORECASTING, AND DELIVERY" }),
  row("8.4 ZNet shall have the right to cancel any order prior to provisioning."),
  row("9. SUB-DISTRIBUTION AND RESELLERS", { number: "9", title: "SUB-DISTRIBUTION AND RESELLERS", heading: true }),
];

describe("outlineTree", () => {
  const tree = outlineTree(ROWS);
  const titles = (nodes: ReturnType<typeof outlineTree>) => nodes.map((n) => `${n.number ?? ""} ${n.title}`.trim());

  it("keeps the document's headings and drops the party-block connectives", () => {
    expect(titles(tree)).toEqual([
      "DISTRIBUTION AGREEMENT", "RECITALS", "1 DEFINITIONS AND INTERPRETATION",
      "8 ORDERING, FORECASTING, AND DELIVERY", "9 SUB-DISTRIBUTION AND RESELLERS",
    ]);
  });

  it("recovers a numbered title the parser did not flag, as a section not a leaf", () => {
    const eight = tree.find((n) => n.number === "8")!;
    expect(eight.leaf).toBe(false);
    expect(isTitleLine("8. ORDERING, FORECASTING, AND DELIVERY")).toBe(true);
    expect(isTitleLine("8.4 ZNet shall have the right to cancel any order prior to provisioning.")).toBe(false);
    expect(isTitleLine("Limitation of Liability")).toBe(true);
  });

  it("nests clauses under their section by number, including ones only the text numbers", () => {
    const one = tree.find((n) => n.number === "1")!;
    const eight = tree.find((n) => n.number === "8")!;
    expect(one.children.map((n) => n.number)).toEqual(["1.1"]);
    expect(eight.children.map((n) => n.number)).toEqual(["8.4"]);
    expect(eight.children[0]!.leaf).toBe(true);
    expect(eight.children[0]!.depth).toBe(1);
    expect(eight.children[0]!.parentId).toBe(eight.row.id);
    expect(outlineAncestors(tree, eight.children[0]!.row.id)).toEqual([eight.row.id]);
  });

  it("never prints a § and never invents a number", () => {
    const all = allOutlineNodes(tree);
    expect(all.some((n) => `${n.number} ${n.title}`.includes("§"))).toBe(false);
    expect(all.filter((n) => n.number === null).map((n) => n.title)).toEqual(["DISTRIBUTION AGREEMENT", "RECITALS"]);
  });

  it("shows children only while their section is open", () => {
    expect(visibleOutline(tree, () => false)).toHaveLength(5);
    const eight = tree.find((n) => n.number === "8")!;
    expect(visibleOutline(tree, (id) => id === eight.row.id).map((n) => n.number)).toContain("8.4");
  });

  it("carries a hidden clause's marker up to its collapsed section", () => {
    const eight = tree.find((n) => n.number === "8")!;
    const status = new Map([[eight.children[0]!.row.id, { covered: true, attention: true, bucket: "missing" as const }]]);
    expect(rollupBucket(eight, status, true)).toBe("missing");
    expect(rollupBucket(eight, status, false)).toBeUndefined();
  });
});

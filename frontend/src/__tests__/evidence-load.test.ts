import { describe, expect, it } from "vitest";

import { EVIDENCE_PAGE_SIZE, chunkRows, loadEvidence, plainRow, type EvidencePages } from "@/components/workspace/evidenceLoad";
import type { EvidenceRow } from "@/lib/types";

const fresh = (): EvidencePages => ({ pages: [], total: null });

/** A fake `/evidence`: `total` rows, pages answered after `delay(page)` ms. */
function server(total: number, delay: (page: number) => number = () => 0) {
  const calls: number[] = [];
  let open = 0;
  let maxOpen = 0;
  const fetchPage = async (page: number) => {
    calls.push(page);
    open += 1;
    maxOpen = Math.max(maxOpen, open);
    await new Promise((resolve) => setTimeout(resolve, delay(page)));
    open -= 1;
    const start = (page - 1) * EVIDENCE_PAGE_SIZE;
    const items = Array.from({ length: Math.max(0, Math.min(EVIDENCE_PAGE_SIZE, total - start)) },
                             (_, i) => ({ id: `r${start + i}` }) as EvidenceRow);
    return { items, pagination: { total } };
  };
  return { fetchPage, calls, maxOpen: () => maxOpen };
}

describe("loadEvidence (W1-3)", () => {
  it("asks page 1 once, commits it at once, then the rest once and in page order", async () => {
    // later pages answer first: order must still be by page
    const s = server(750, (page) => (page === 1 ? 0 : 40 - page * 4));
    const commits: string[][] = [];
    await loadEvidence(s.fetchPage, fresh(), (rows) => commits.push(rows.map((r) => r.id)), () => true);
    expect(s.calls.filter((p) => p === 1)).toHaveLength(1);
    expect([...s.calls].sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(commits).toHaveLength(2);
    expect(commits[0]).toHaveLength(100);
    expect(commits[1]).toEqual(Array.from({ length: 750 }, (_, i) => `r${i}`));
  });

  it("keeps at most three later pages in flight", async () => {
    const s = server(1000, () => 5);
    await loadEvidence(s.fetchPage, fresh(), () => undefined, () => true);
    expect(s.maxOpen()).toBe(3);
  });

  it("one page: one request, one commit", async () => {
    const s = server(40);
    const commits: number[] = [];
    await loadEvidence(s.fetchPage, fresh(), (rows) => commits.push(rows.length), () => true);
    expect(s.calls).toEqual([1]);
    expect(commits).toEqual([40]);
  });

  it("a version switch stops new requests and every later commit", async () => {
    let alive = true;
    const s = server(1000, () => 5);
    const commits: number[] = [];
    const done = loadEvidence(s.fetchPage, fresh(), (rows) => {
      commits.push(rows.length);
      alive = false;   // switched away right after the first page drew
    }, () => alive);
    await done;
    expect(commits).toEqual([100]);
    expect(s.calls).toEqual([1]);
  });

  it("a switch while page 1 is out commits nothing", async () => {
    let alive = true;
    const s = server(300, () => 5);
    const commits: number[] = [];
    const done = loadEvidence(s.fetchPage, fresh(), (rows) => commits.push(rows.length), () => alive);
    alive = false;
    await done;
    expect(commits).toEqual([]);
  });

  it("a failed page keeps the pages before it, and Try again asks only for the missing ones", async () => {
    const commits: number[] = [];
    const calls: number[] = [];
    let down = true;
    const fetchPage = async (page: number) => {
      calls.push(page);
      if (page === 3 && down) throw new Error("boom");
      return { items: Array.from({ length: 100 }, (_, i) => ({ id: `${page}-${i}` }) as EvidenceRow),
               pagination: { total: 400 } };
    };
    const got = fresh();
    await expect(loadEvidence(fetchPage, got, (rows) => commits.push(rows.length), () => true)).rejects.toThrow("boom");
    expect(commits).toEqual([100, 200]);   // pages 1–2 shown; 4 may be read but waits behind the gap
    down = false;
    calls.length = 0;
    await loadEvidence(fetchPage, got, (rows) => commits.push(rows.length), () => true);
    expect(calls).not.toContain(1);
    expect(calls).toContain(3);
    expect(commits.at(-1)).toBe(400);
  });
});

describe("chunkRows (W1-2 r2, S1)", () => {
  it("cuts at about 40 rows, and only before a plain row", () => {
    const rows = Array.from({ length: 100 }, (_, i) => i);
    const plain = (i: number) => !(i >= 40 && i <= 42);   // rows 40–42 open with a heading's space
    const chunks = chunkRows(rows, plain);
    expect(chunks.map((c) => c[0])).toEqual([0, 43, 83]);
    expect(chunks.flat()).toEqual(rows);
  });
  it("plainRow: headings, titles, labels and connectors are not plain", () => {
    const row = (house_style: string | null = null) => ({ house_style }) as EvidenceRow;
    expect(plainRow(row(), "para", null)).toBe(true);
    expect(plainRow(row(), "heading", null)).toBe(false);
    expect(plainRow(row(), "para", "label")).toBe(false);
    expect(plainRow(row("LM Plain Heading"), "para", null)).toBe(false);
    expect(plainRow(row("LM Heading 2"), "para", null)).toBe(true);   // a numbered clause: no space above
  });
});

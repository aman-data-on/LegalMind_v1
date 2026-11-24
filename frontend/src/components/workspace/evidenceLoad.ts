import type { EvidenceRow, Pagination } from "@/lib/types";

/** The server's page-size cap (locked 49.6): a bigger page is not on offer. */
export const EVIDENCE_PAGE_SIZE = 100;
/** Pages 2…N in flight at once: enough to overlap round trips, few enough to leave sockets
 *  (HTTP/1.1: 6 per origin) and DB connections for the workspace's other reads. */
const IN_FLIGHT = 3;

/** What has been read of one version's text: `pages[i]` is page i + 1. */
export interface EvidencePages { pages: EvidenceRow[][]; total: number | null }

/**
 * W1-3: the document text. Page 1 is committed as soon as it lands, so the reader sees text
 * at once; its `total` names the other pages, which are fetched IN_FLIGHT at a time and
 * committed as ONE update in page order (one re-render of the document, not one per page).
 * A failed page (W1 r2, S7) still commits every page before it and then throws; calling
 * again with the same `got` asks only for the pages still missing.
 * `alive()` false (version switch, unmount) stops new requests and every commit.
 */
export async function loadEvidence(
  fetchPage: (page: number) => Promise<{ items: EvidenceRow[]; pagination: Pick<Pagination, "total"> }>,
  got: EvidencePages,
  commit: (rows: EvidenceRow[], total: number) => void,
  alive: () => boolean,
): Promise<void> {
  const shown = () => { const rows: EvidenceRow[] = []; for (let i = 0; got.pages[i]; i++) rows.push(...got.pages[i]!); return rows; };
  if (!got.pages[0]) {
    const first = await fetchPage(1);
    if (!alive()) return;
    got.pages[0] = first.items;
    got.total = first.pagination.total;
    commit(shown(), got.total);
    if (first.items.length === 0) return;
  }
  const total = got.total ?? 0;
  const missing = Array.from({ length: Math.max(0, Math.ceil(total / EVIDENCE_PAGE_SIZE) - 1) }, (_, i) => i + 2)
    .filter((page) => !got.pages[page - 1]);
  if (missing.length === 0) return;
  let next = 0;
  let failed: { cause: unknown } | null = null;
  const worker = async () => {
    while (next < missing.length && alive() && !failed) {
      const page = missing[next++]!;
      try { got.pages[page - 1] = (await fetchPage(page)).items; } catch (cause) { failed ??= { cause }; }
    }
  };
  await Promise.all(Array.from({ length: Math.min(IN_FLIGHT, missing.length) }, worker));
  if (!alive()) return;
  commit(shown(), total);
  if (failed) throw (failed as { cause: unknown }).cause;
}

/** W1-2: rows per `.ws-chunk`, the unit the browser skips while off screen. */
export const CHUNK_ROWS = 40;

/** A row that opens with no space above it (no title, heading, label or connector): only
 *  there may a chunk begin — a chunk keeps its margins to itself, so a heading opening one
 *  would sit lower than on a page drawn in one piece (W1 r2, S1). */
export function plainRow(row: EvidenceRow, kind: string | undefined, shape: string | null | undefined): boolean {
  // the house style as `data-house` names it ("LM Plain Heading" → "plain heading")
  const house = row.house_style?.slice(3).toLowerCase().replace(/\s+\d$/, "") ?? "";
  return !["title", "heading", "subheading"].includes(kind ?? "") && !["connector", "label"].includes(shape ?? "")
    && !["plain heading", "front"].includes(house);
}

/** Rows in chunks of about `size`: a chunk closes at the first plain row after it is full. */
export function chunkRows<T>(rows: T[], plain: (row: T) => boolean, size = CHUNK_ROWS): T[][] {
  const chunks: T[][] = [];
  for (const row of rows) {
    const last = chunks[chunks.length - 1];
    if (last && (last.length < size || !plain(row))) last.push(row);
    else chunks.push([row]);
  }
  return chunks;
}

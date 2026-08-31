/**
 * Pure helpers for the workspace — no fetching, no permission logic, no legal
 * derivation. Kept separate so the house static-render tests can pin them.
 */

import * as P from "@/lib/permissions";
import type { EvidenceRow } from "@/lib/types";

/**
 * Index readiness derived from counts the server returns. Deliberately NOT a
 * server-side enum (`AM-29` r1 keeps the assist lane to one state axis); the
 * client says what the counts mean for the user in plain words.
 */
export type Readiness = "ready" | "lexical-only" | "not-indexed";

export function readiness(index?: { chunks: number; embedded_chunks: number }): Readiness {
  if (!index || index.chunks === 0) return "not-indexed";
  if (index.embedded_chunks === 0) return "lexical-only";
  return "ready";
}

export const READINESS_TEXT: Record<Readiness, string> = {
  ready: "Searchable by wording and meaning",
  "lexical-only": "Searchable by exact wording",
  "not-indexed": "Not yet searchable",
};

/** Evidence grouped by page in reading order; unnumbered rows fall last. */
export interface PageGroup {
  page: number | null;
  rows: EvidenceRow[];
}

export function groupByPage(rows: EvidenceRow[]): PageGroup[] {
  const groups: PageGroup[] = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    if (last && last.page === row.page_number) last.rows.push(row);
    else groups.push({ page: row.page_number, rows: [row] });
  }
  return groups;
}

/** Rows that carry a clause reference — the document's own outline. */
export function outlineOf(rows: EvidenceRow[]): EvidenceRow[] {
  return rows.filter((row) => row.section_number || row.section_title);
}

export function locationLabel(row: EvidenceRow): string {
  const parts: string[] = [];
  if (row.section_number) parts.push(`§${row.section_number}`);
  if (row.section_title) parts.push(row.section_title);
  if (row.page_number != null) parts.push(`p.${row.page_number}`);
  return parts.length > 0 ? parts.join(" · ") : "location not recorded";
}

/**
 * Navigation derived from permissions by ABSENCE (52.3) — and, since the
 * 2026-08-30 cleanup, by EXISTENCE: an item appears only once its destination is
 * a real screen in the new application. `Reviews` / `Legal` / `Audit` / `Admin`
 * have no new-UI screen yet (roadmap slices 2, 4, 5) — until each lands, the
 * capability still works (directly, or in the legacy application for
 * verification), it is simply not offered as a click from this shell. Listing a
 * legacy route here would be exactly the "navigation path into the old
 * application" the cleanup exists to remove; do not re-add one as a shortcut
 * when building the next slice — replace this comment with the new route
 * instead, in the same change that ships the screen.
 */
export interface NavItem {
  href: string;
  label: string;
}

export function navItemsFor(can: (permission: string) => boolean): NavItem[] {
  const items: NavItem[] = [];
  if (can(P.CONTRACT_VIEW)) items.push({ href: "/workspace", label: "Documents" });
  if (can(P.REVIEW_VIEW)) items.push({ href: "/workspace/reviews", label: "Reviews" });
  if (can(P.LEGAL_REVIEW)) items.push({ href: "/workspace/legal", label: "Legal" });
  if (can(P.ASSIST_ASK)) items.push({ href: "/workspace/ask", label: "Ask history" });
  if (can(P.ASSIST_ASK)) items.push({ href: "/workspace/research", label: "Research" });
  // The control plane sits last — it is not part of the legal workflow (§H).
  if (can(P.USER_MANAGE) || can(P.AUDIT_VIEW)) items.push({ href: "/workspace/admin", label: "Admin" });
  return items;
}

/**
 * The nav item a pathname belongs to — the LONGEST matching href, so that
 * `/workspace/reviews/…` lights "Reviews" and never also "Documents" (whose
 * href is a prefix of every workspace route).
 */
export function activeNavHref(pathname: string, items: NavItem[]): string | null {
  let best: string | null = null;
  for (const item of items) {
    if (pathname === item.href || pathname.startsWith(`${item.href}/`)) {
      if (best === null || item.href.length > best.length) best = item.href;
    }
  }
  return best;
}

/**
 * Which document version the workspace opens: the one the URL asks for when it
 * exists on this contract, otherwise the latest (index 0 — the API lists
 * newest first). A stale or foreign id falls back to latest rather than
 * erroring: the workspace always opens on something real.
 */
export function pickVersion<T extends { id: string }>(
  versions: T[],
  requestedId: string | null,
): T | null {
  if (requestedId) {
    const requested = versions.find((v) => v.id === requestedId);
    if (requested) return requested;
  }
  return versions[0] ?? null;
}

/**
 * The Documents row's analysis reality, as render-ready parts (2026-08-31 UX
 * correction): the list answers "what did analysis find", never a lifecycle
 * enum. Counts render in a fixed, attention-first order; the absence states
 * are words, not blanks. Dates stay out of this cell (they live in "Added")
 * so the cell is deterministic for visual baselines.
 */
const COUNT_ORDER = [
  "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE",
  "AMBIGUOUS", "UNRESOLVED", "MATCH", "NOT_APPLICABLE",
] as const;

export type AnalysisCell =
  | { kind: "none" }        // no document uploaded yet
  | { kind: "processing" }
  | { kind: "unanalysed" }
  | { kind: "analysed"; review_id: string; review_status: string;
      counts: Array<{ classification: string; n: number }> };

export function analysisCell(row: {
  latest_version?: { processing_status: string } | null;
  latest_analysis?: {
    review_id: string; review_status: string;
    classification_counts?: Record<string, number>;
  } | null;
}): AnalysisCell {
  if (!row.latest_version) return { kind: "none" };
  if (row.latest_version.processing_status !== "COMPLETED") return { kind: "processing" };
  if (!row.latest_analysis) return { kind: "unanalysed" };
  const counts = COUNT_ORDER
    .map((classification) => ({
      classification,
      n: row.latest_analysis?.classification_counts?.[classification] ?? 0,
    }))
    .filter((entry) => entry.n > 0);
  return {
    kind: "analysed",
    review_id: row.latest_analysis.review_id,
    review_status: row.latest_analysis.review_status,
    counts,
  };
}

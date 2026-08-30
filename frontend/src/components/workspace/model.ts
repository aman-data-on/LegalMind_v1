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
 * Navigation derived from permissions by ABSENCE (52.3). The IA of
 * PRODUCT_UX_ROADMAP.md §C; targets that are not yet rebuilt point at the route
 * that does the job today and move as each slice lands.
 */
export interface NavItem {
  href: string;
  label: string;
}

export function navItemsFor(can: (permission: string) => boolean): NavItem[] {
  const items: NavItem[] = [];
  if (can(P.CONTRACT_VIEW)) items.push({ href: "/contracts", label: "Documents" });
  if (can(P.REVIEW_VIEW)) items.push({ href: "/reviews", label: "Reviews" });
  if (can(P.CONFIGURATION_VIEW)) items.push({ href: "/configuration", label: "Legal" });
  if (can(P.AUDIT_VIEW)) items.push({ href: "/audit", label: "Audit" });
  if (can(P.USER_MANAGE)) items.push({ href: "/admin", label: "Admin" });
  return items;
}

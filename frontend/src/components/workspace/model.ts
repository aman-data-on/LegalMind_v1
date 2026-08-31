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
/**
 * The seven Finding classifications (locked Step 19 vocabulary), in a fixed
 * attention-first RENDERING order. A rendering order, not a severity model:
 * the Tier-1 states are legally equivalent and all route to a human.
 * `NOT_APPLICABLE` is deliberately absent — it is a Rule Outcome, a different
 * axis, and must never appear in a classification list.
 */
export const CLASSIFICATION_ORDER = [
  "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE",
  "AMBIGUOUS", "UNRESOLVED", "MATCH",
] as const;

const COUNT_ORDER = CLASSIFICATION_ORDER;

export type AnalysisCell =
  | { kind: "none" }        // no document uploaded yet
  | { kind: "processing" }
  | { kind: "unanalysed" }
  | { kind: "analysed"; review_id: string; review_status: string;
      counts: Array<{ classification: string; n: number }> };

/**
 * Counts of the loaded findings by classification, in rendering order — pure
 * presentational grouping of values the server already returned (52.7: nothing
 * here derives or reinterprets a classification).
 */
export interface FindingsSummary {
  counts: Array<{ classification: string; n: number }>;
  needsDecision: number;
  /** True when at least one finding exists and every one is a MATCH — the
   *  designed success state, built from real fields only. */
  allMatch: boolean;
}

export function findingsSummary(
  findings: Array<{ classification: string; requires_decision: boolean }>,
): FindingsSummary {
  const byClassification = new Map<string, number>();
  let needsDecision = 0;
  for (const finding of findings) {
    byClassification.set(
      finding.classification,
      (byClassification.get(finding.classification) ?? 0) + 1,
    );
    if (finding.requires_decision) needsDecision += 1;
  }
  const known = CLASSIFICATION_ORDER
    .map((classification) => ({
      classification: classification as string,
      n: byClassification.get(classification) ?? 0,
    }))
    .filter((entry) => entry.n > 0);
  // Anything outside the known vocabulary still renders (verbatim, last) —
  // the client never drops a value the server chose to return.
  const unknown = [...byClassification.entries()]
    .filter(([classification]) =>
      !(CLASSIFICATION_ORDER as readonly string[]).includes(classification))
    .map(([classification, n]) => ({ classification, n }));
  return {
    counts: [...known, ...unknown],
    needsDecision,
    allMatch:
      findings.length > 0 &&
      findings.every((finding) => finding.classification === "MATCH"),
  };
}

/**
 * The findings that need a human decision — ONE filter shared by the findings
 * pane's default view and the AI Analysis panel's "Key risks" list, so the two
 * views can never disagree. `requires_decision` is server-derived; the client
 * never re-derives it (52.7).
 */
export function findingsNeedingDecision<T extends { requires_decision: boolean }>(
  findings: T[],
): T[] {
  return findings.filter((finding) => finding.requires_decision);
}

/**
 * The three status buckets of the 2026-09-01 reference-matched restyle —
 * owner-approved (DD-9) mapping of the seven classifications onto the
 * reference design's traffic light. PRESENTATION grouping only: the exact
 * classification value always renders beside the color, and the vocabulary
 * itself is untouched.
 *
 *   match    MATCH
 *   missing  MISSING
 *   review   everything else (DEVIATION, CONFLICT, UNABLE_TO_EVALUATE,
 *            AMBIGUOUS, UNRESOLVED, and any future value — fail toward
 *            "needs review", never toward calm)
 */
export type StatusBucket = "match" | "review" | "missing";

export function classificationBucket(classification: string): StatusBucket {
  if (classification === "MATCH") return "match";
  if (classification === "MISSING") return "missing";
  return "review";
}

const BUCKET_RANK: Record<StatusBucket, number> = { match: 0, review: 1, missing: 2 };

export function worseBucket(a: StatusBucket, b: StatusBucket): StatusBucket {
  return BUCKET_RANK[b] > BUCKET_RANK[a] ? b : a;
}

/** What the outline marker says about a clause. */
export interface ClauseStatus {
  covered: boolean;
  attention: boolean;
  bucket: StatusBucket;
}

/**
 * Evidence-row id → clause status, merged across every finding that cites the
 * row (a clause never downgrades: the marker shows the most attention-worthy
 * bucket). Presentation grouping of server fields only: `requires_decision`
 * is the server's, nothing is re-derived.
 */
export function clauseStatusByEvidenceId(
  findings: Array<{
    classification: string;
    requires_decision: boolean;
    evidence: Array<{ id: string }>;
  }>,
): Map<string, ClauseStatus> {
  const byEvidence = new Map<string, ClauseStatus>();
  for (const finding of findings) {
    const bucket = classificationBucket(finding.classification);
    const attention = finding.requires_decision || bucket !== "match";
    for (const row of finding.evidence) {
      const current = byEvidence.get(row.id) ??
        { covered: false, attention: false, bucket: "match" as StatusBucket };
      byEvidence.set(row.id, {
        covered: true,
        attention: current.attention || attention,
        bucket: worseBucket(current.bucket, bucket),
      });
    }
  }
  return byEvidence;
}

/**
 * Roll per-evidence status up to the OWNING outline row: every row from one
 * outline entry to the next belongs to that clause (reading order), so a
 * finding citing a clause's body marks the clause's heading in the outline.
 */
export function outlineStatus(
  rows: Array<{ id: string; section_number: string | null; section_title: string | null }>,
  statusByEvidenceId: Map<string, ClauseStatus>,
): Map<string, ClauseStatus> {
  const byOutlineRow = new Map<string, ClauseStatus>();
  let currentOutlineId: string | null = null;
  for (const row of rows) {
    if (row.section_number || row.section_title) currentOutlineId = row.id;
    if (!currentOutlineId) continue;
    const status = statusByEvidenceId.get(row.id);
    if (!status) continue;
    const current = byOutlineRow.get(currentOutlineId) ??
      { covered: false, attention: false, bucket: "match" as StatusBucket };
    byOutlineRow.set(currentOutlineId, {
      covered: current.covered || status.covered,
      attention: current.attention || status.attention,
      bucket: worseBucket(current.bucket, status.bucket),
    });
  }
  return byOutlineRow;
}

/**
 * Whether a Documents row belongs in the "Needs attention" group: its latest
 * analysis recorded at least one non-MATCH classification. Derived from the
 * server's own counts, never recomputed from findings.
 */
export function rowNeedsAttention(row: {
  latest_analysis?: { classification_counts?: Record<string, number> } | null;
}): boolean {
  const counts = row.latest_analysis?.classification_counts;
  if (!counts) return false;
  return Object.entries(counts).some(
    ([classification, n]) => classification !== "MATCH" && n > 0,
  );
}

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

/**
 * Pure helpers for the workspace — no fetching, no permission logic, no legal
 * derivation. Kept separate so the house static-render tests can pin them.
 */

import { scopeLabel } from "@/lib/labels";
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

/** "3 h ago", "yesterday" — a plain-language age for a timestamp. Shared so the
 *  dashboard table and the Analysis panel can't drift into two tiers. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  if (seconds < 172800) return "yesterday";
  return `${Math.round(seconds / 86400)} d ago`;
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

/**
 * The document's own outline — HEADINGS, not every row that starts with a
 * number.
 *
 * The panel used to list every row carrying a number or a title, which put
 * mid-clause body text ("10.2 Customer acknowledges and understands that the…")
 * beside real headings at the same weight and made the list unreadable. The
 * parser now records which rows begin a section, so the outline is what the
 * document says it is rather than what the text happens to start with.
 *
 * FALLBACK, deliberately: documents extracted before 2026-09-05 carry no
 * marker, and re-extracting them would rewrite evidence that Findings already
 * cite (rule 17). For those the old rule still applies — an imperfect outline
 * beats an empty one, and it improves the moment a document is re-uploaded.
 */
export function outlineOf(rows: EvidenceRow[]): EvidenceRow[] {
  const headings = rows.filter((row) => row.is_heading && isHeadingLine(row));
  if (headings.length > 0) return headings;
  // The fallback applies the SAME line test. Without it, a document whose only
  // heading marks are false ones fell through to here and the paragraphs came
  // straight back — they carry a `section_title`, which is exactly what the
  // parser promoted. A numbered row is admitted regardless: a clause reference
  // is a navigation target whether or not the row is a heading.
  return rows.filter((row) =>
    row.section_number
    || clauseFromText(row)
    || (row.section_title && isHeadingLine(row)));
}

/**
 * The clause number and title a row DECLARES in its own text, for rows the
 * parser numbered as `null`.
 *
 * THE DEFECT (owner's screenshot, 2026-09-09): the Contents of a real 20-page
 * MSA was empty. Measured on the live rows — 91 evidence rows, ONE with a
 * `section_number`. The numbers are all there in the text; they are separated
 * from their titles by U+200B:
 *
 *     "1.​\nDEFINITIONS \n1.1.​“Affiliate” shall mean…"
 *     "7.​\nTERM AND TERMINATION"
 *     "17.​\nLIMITATION OF LIABILITY"
 *
 * That is how Word exports automatic list numbering: the generated number is
 * its own run, terminated by a zero-width space, and the paragraph text follows
 * on the next line. `ingestion/parsing.py`'s number regex sees U+200B as a
 * non-space and matches nothing, so the whole document arrives unnumbered and
 * the outline has nothing to list.
 *
 * The SAME trap was fixed once already, on 2026-09-08, in `assist/chunking.py`
 * ("U+200B/NBSP are blanks") — the parser was never given the same treatment.
 *
 * The fix is HERE and not in the parser, for the reason `isHeadingLine` above
 * records: `section_number` and `is_heading` are not presentation fields.
 * `mapping/service.py` feeds them to the mapping engine and `analysis/service.py`
 * reads them to decide whether a document is too unsegmented to analyse at all,
 * so re-tuning the parser would change which provisions map and which documents
 * are refused — legal results, for a navigation defect. Re-extracting instead
 * would rewrite evidence rows that existing Findings already cite (rule 17).
 * So this reads the row's own recorded text and derives nothing else.
 *
 * Measured against every document in the live database: it fires only on rows
 * the parser left unnumbered, and every number it recovers is one the document
 * states — 31 on the MSA above, 49 on the executed GRP MSA, 74 on a partner
 * agreement, 0 on all six documents the parser already numbers completely.
 */
const CLAUSE_ALONE = /^(\d+(?:\.\d+)*)\.$/;
const CLAUSE_INLINE = /^(\d+(?:\.\d+)*)\.?\s+(\S.*)$/;

export function clauseFromText(
  row: { content: string },
): { number: string; title: string } | null {
  const lines = row.content
    // U+200B (Word's list-number terminator) and NBSP are blanks, exactly as
    // the assist chunker treats them.
    .replace(/[​ ]/g, " ")
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .filter((line) => line.length > 0);
  const first = lines[0];
  if (!first) return null;
  // The number alone on its line MUST carry its trailing dot: "3." is a clause
  // label, a bare "3" is a page-footer row and there are two of them in the
  // document above.
  const alone = CLAUSE_ALONE.exec(first);
  if (alone) return { number: alone[1]!, title: lines[1] ?? "" };
  const inline = CLAUSE_INLINE.exec(first);
  if (inline) return { number: inline[1]!, title: inline[2]! };
  return null;
}

/**
 * The number and title to SHOW for an outline row: what the parser recorded,
 * else what the row's own text states. Stored values always win — a document
 * the parser reads correctly is never reinterpreted here.
 */
export function clauseOf(row: EvidenceRow): { number: string | null; title: string } {
  if (row.section_number) {
    return { number: row.section_number, title: row.section_title ?? "" };
  }
  const derived = clauseFromText(row);
  if (derived) return derived;
  return { number: null, title: row.section_title ?? "" };
}

/**
 * Whether a heading-marked row is a heading LINE rather than a paragraph whose
 * first line merely looked like one.
 *
 * THE DEFECT (owner's screenshot, 2026-09-08): the Contents of a real NDA read
 * "AND", "Information", "The information is independently developed by
 * employees of the…", then §10, §11, §12. The first three are body text.
 * `parsing._is_unnumbered_heading` promotes an unnumbered line when the line
 * after it does not begin lowercase — which is true of a party block ("AND"
 * followed by a company name in capitals) and of a definitions paragraph.
 *
 * The fix is HERE and not in the parser on purpose. `is_heading` is not a
 * presentation flag: `mapping/service.py` feeds it to the mapping engine as
 * `Clause.is_heading`, and `analysis/service.py` reads it to decide whether a
 * document is too unsegmented to analyse at all. Re-tuning the parser could
 * therefore change which provisions map and which documents are refused — a
 * change to legal results, for a navigation defect. So the outline filters what
 * it shows and the recorded marker is left exactly as it is.
 *
 * The test is a fact about the row, not about this document: a heading is a
 * line, so its content is its own heading text and nothing more. Measured on
 * the live rows — the three real headings carry 17, 22 and 32 characters
 * against titles of 13, 18 and 28; the three false ones carry 159, 187 and 772
 * characters against titles of 72, 11 and 3. The slack covers the number, its
 * separator and stray whitespace.
 */
function isHeadingLine(row: EvidenceRow): boolean {
  const title = row.section_title?.trim() ?? "";
  // A heading the parser recorded with no title at all — an annexure label, in
  // practice — is trusted: there is no body text to have mistaken it for.
  if (!title) return true;
  const number = row.section_number?.trim() ?? "";
  return row.content.trim().length <= number.length + title.length + 6;
}

/**
 * Findings that cite a given evidence row — the reverse of the finding-to-
 * evidence link the pane already draws.
 *
 * Built from the SAME findings list the Findings pane renders, which the server
 * has already filtered by permission and redacted per LEGAL-02. So a reader who
 * cannot see a Finding cannot learn of it here either: the list they are given
 * simply does not contain it, and this function invents nothing. It also means
 * no finding data is duplicated — this is an index over state that is already
 * loaded, not a second copy of it.
 *
 * The map deliberately carries the whole Finding rather than a projection: the
 * caller needs its id to navigate and its classification to label the link, and
 * copying two fields out would be the start of the duplication this avoids.
 */
export function findingsByEvidenceId<T extends { evidence: Array<{ id: string }> }>(
  findings: T[],
): Map<string, T[]> {
  const byEvidence = new Map<string, T[]>();
  for (const finding of findings) {
    for (const row of finding.evidence) {
      const bucket = byEvidence.get(row.id);
      if (bucket) {
        if (!bucket.includes(finding)) bucket.push(finding);
      } else {
        byEvidence.set(row.id, [finding]);
      }
    }
  }
  return byEvidence;
}

/**
 * The requirement in a reader's words — the heading the Findings pane shows.
 *
 * Lives here rather than in the pane because the document pane's reverse link
 * must name a finding the SAME way the finding names itself; two spellings of
 * one requirement is how a reader stops believing they are the same thing.
 */
export function requirementHeading(
  requirement: { code?: string | null; name?: string | null },
): string {
  const name = requirement.name?.trim();
  const code = requirement.code?.trim();
  if (name && name !== code) return name;
  if (code) return scopeLabel(code);
  return "Requirement";
}

/**
 * Where the document's numbering restarts — a real MSA carries more than one
 * sequence: the body §1–§24, then an annexed AUP that begins again at §1, then
 * a schedule that begins again at §1. Flattening them into one list is why the
 * outline appeared to jump from §24.9 back to §12 and §4.
 *
 * A restart is a top-level number that DECREASES. Equal is not a restart: §1
 * followed by §1.2 is a sub-heading of the same section, and treating it as one
 * put a divider inside every section that had one.
 * That is a fact about the numbers the document states, not an interpretation
 * of what the annexure IS — naming it would be inventing a document structure
 * the file does not declare, so the divider says only that numbering restarts.
 */
export function sequenceBreaks(rows: EvidenceRow[]): Set<string> {
  const breaks = new Set<string>();
  let previous: number | null = null;
  for (const row of rows) {
    const top = Number.parseInt(clauseOf(row).number?.split(".")[0] ?? "", 10);
    if (Number.isNaN(top)) continue;
    if (previous !== null && top < previous) breaks.add(row.id);
    previous = top;
  }
  return breaks;
}

/**
 * The outline as a TREE (owner, 2026-09-10): "Preserve actual section/clause
 * numbers and titles. Proper parent/child hierarchy. DO NOT invent numbering."
 *
 * Built from the same rows `outlineOf` reads, at the presentation layer only
 * (`AM-57` r3 — the parser is not retuned, evidence is not re-extracted):
 *
 *   heading rows      `is_heading` + `isHeadingLine`, minus a connective the
 *                     party block promoted ("BETWEEN", "AND" — measured on a
 *                     live distribution agreement, 2026-09-10)
 *   numbered titles   a numbered row whose whole content is one title-like
 *                     line. The parser's `_is_heading` refuses a title with a
 *                     comma, so "8. ORDERING, FORECASTING, AND DELIVERY" and
 *                     "11. TECHNICAL SUPPORT, TRAINING, AND SERVICE LEVELS"
 *                     arrived un-flagged and the Contents jumped 7 → 9 → 10 → 12
 *   numbered clauses  every other numbered row, as a LEAF under its section —
 *                     "8.4 ZNet shall have the right to cancel…", truncated by
 *                     the CSS to one line, a navigation target the way a
 *                     finding's citation is
 *
 * Parent = the longest numeric prefix already seen ("8.4" → "8", "5.1.1" →
 * "5.1" → "5"); a sub-number with no numbered parent in sight sits under the
 * nearest preceding root. The map is overwritten in document order, so an
 * annexure that restarts at 1 attaches its 1.2 to ITS 1, not the body's.
 */
export interface OutlineNode {
  row: EvidenceRow;
  number: string | null;
  title: string;
  depth: number;
  parentId: string | null;
  /** A clause paragraph rather than a heading line — one truncated line. */
  leaf: boolean;
  children: OutlineNode[];
}

const CONNECTIVES = new Set(["AND", "OR", "BETWEEN", "BY AND BETWEEN", "WHEREAS", "NOW THEREFORE"]);

/** One short line, no sentence punctuation, set as a title: ALL CAPS or Title Case. */
export function isTitleLine(text: string): boolean {
  const line = text.replace(/[​ ]/g, " ").replace(/\s+/g, " ").trim();
  if (line.length === 0 || line.length > 90 || /[.;:,]$/.test(line)) return false;
  const letters = line.replace(/[^A-Za-z]/g, "");
  if (letters.length < 3) return false;
  if (letters.replace(/[^A-Z]/g, "").length / letters.length >= 0.6) return true;
  const words = line.replace(/^[\d.]+\s*/, "").split(" ").filter((w) => /[A-Za-z]{4,}/.test(w));
  return words.length > 0 && words.every((w) => /^[A-Z]/.test(w));
}

export function outlineTree(rows: EvidenceRow[]): OutlineNode[] {
  const headed = rows.some((row) => row.is_heading);
  const roots: OutlineNode[] = [];
  const byNumber = new Map<string, OutlineNode>();
  let lastRoot: OutlineNode | null = null;
  for (const row of rows) {
    const clause = clauseOf(row);
    const heading = row.is_heading && isHeadingLine(row);
    if (heading && !clause.number && CONNECTIVES.has(row.content.trim().toUpperCase())) continue;
    // Pre-2026-09-05 documents carry no heading marker: `outlineOf`'s fallback.
    const fallback = !headed && !!row.section_title && isHeadingLine(row);
    if (!heading && !clause.number && !fallback) continue;
    const titled = heading || fallback || (clause.number !== null && isTitleLine(row.content));
    const node: OutlineNode = {
      row, number: clause.number, depth: 0, parentId: null, children: [],
      title: clause.title || (clause.number ? "" : row.content.trim()),
      leaf: !titled,
    };
    let parent: OutlineNode | null = null;
    if (clause.number) {
      const parts = clause.number.split(".");
      for (let i = parts.length - 1; i > 0 && !parent; i -= 1) {
        parent = byNumber.get(parts.slice(0, i).join(".")) ?? null;
      }
      if (!parent && parts.length > 1) parent = lastRoot;
      byNumber.set(clause.number, node);
    }
    if (parent) {
      node.depth = parent.depth + 1;
      node.parentId = parent.row.id;
      parent.children.push(node);
    } else {
      roots.push(node);
      lastRoot = node;
    }
  }
  return roots;
}

/** Every node in document order — the search space, and the flat fallback. */
export function allOutlineNodes(nodes: OutlineNode[]): OutlineNode[] {
  const out: OutlineNode[] = [];
  const walk = (list: OutlineNode[]) => {
    for (const node of list) {
      out.push(node);
      walk(node.children);
    }
  };
  walk(nodes);
  return out;
}

/** The nodes on screen: a child shows only while every ancestor is open. */
export function visibleOutline(nodes: OutlineNode[], isOpen: (id: string) => boolean): OutlineNode[] {
  const out: OutlineNode[] = [];
  const walk = (list: OutlineNode[]) => {
    for (const node of list) {
      out.push(node);
      if (node.children.length > 0 && isOpen(node.row.id)) walk(node.children);
    }
  };
  walk(nodes);
  return out;
}

/** The ids to open so `rowId` is on screen — its ancestors, nearest last. */
export function outlineAncestors(nodes: OutlineNode[], rowId: string): string[] {
  const byId = new Map(allOutlineNodes(nodes).map((node) => [node.row.id, node]));
  const path: string[] = [];
  let parentId = byId.get(rowId)?.parentId ?? null;
  while (parentId) {
    path.unshift(parentId);
    parentId = byId.get(parentId)?.parentId ?? null;
  }
  return path;
}

/** A collapsed section carries its worst descendant's marker, so a finding on
 *  a hidden clause is still visible at the level the reader can see. */
export function rollupBucket(
  node: OutlineNode,
  status: Map<string, ClauseStatus>,
  collapsed: boolean,
): StatusBucket | undefined {
  let worst = status.get(node.row.id)?.bucket;
  if (collapsed) {
    for (const child of allOutlineNodes(node.children)) {
      const bucket = status.get(child.row.id)?.bucket;
      if (bucket) worst = worst ? worseBucket(worst, bucket) : bucket;
    }
  }
  return worst;
}

export function locationLabel(row: EvidenceRow): string {
  const parts: string[] = [];
  if (row.section_number) parts.push(row.section_number);
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
  if (can(P.CONTRACT_VIEW)) items.push({ href: "/dashboard", label: "Dashboard" });
  /*
   * Reviews is a QUEUE, and a queue is only a destination for someone who works
   * one (2026-09-04 audit). For a contract owner it listed one row per analysis
   * run of documents the Dashboard already lists, with the same states — the
   * same information twice, one click apart. It stays a full screen (a Report is
   * reached from it, and from the workspace) but leaves the top-level nav unless
   * the caller actually holds Legal work: `legal.review` widens `GET /reviews`
   * to other people's Reviews (`REC-09`), which is the point at which a queue
   * says something the Dashboard cannot.
   */
  if (can(P.REVIEW_VIEW) && can(P.LEGAL_REVIEW)) {
    items.push({ href: "/dashboard/reviews", label: "Reviews" });
  }
  if (can(P.LEGAL_REVIEW)) items.push({ href: "/dashboard/legal", label: "Legal" });
  /*
   * "Ask" — not "Ask History". Asking happens in a document (the workspace
   * dock); this screen is where the record of it lives. Naming the nav item
   * after the archive advertised the filing cabinet and hid the feature: the
   * audit found Ask had no nav presence at all while its history had a
   * top-level slot. One label for one capability; the page itself explains
   * where asking happens.
   */
  /*
   * Client Profiles — the company a deal is with, and every document filed
   * under it (owner instruction, 2026-09-10). It sits directly after the
   * Dashboard because the two are the same documents seen two ways: the
   * Dashboard is "what am I working on", this is "what do we have with X".
   *
   * `contract.view` and nothing more (AB-13 r5): the profile is the
   * counterparty row, so a caller who may see a contract may see who it is
   * with. Deliberately NOT admin-gated — the owner's instruction is explicit
   * that every normal user reaches it, and the server scopes what each one
   * sees rather than the nav hiding the section.
   */
  if (can(P.CONTRACT_VIEW)) {
    items.push({ href: "/dashboard/clients", label: "Client Profiles" });
  }
  if (can(P.ASSIST_ASK)) items.push({ href: "/dashboard/ask", label: "Ask" });
  /*
   * Legal configuration — Requirements, Company Standards and the published
   * snapshot every analysis pins (AUD-04). It has lived at the legacy
   * `/configuration` route with NO entry in this shell, so a Legal Admin could
   * only reach the one screen that makes analysis possible by typing a URL.
   * Adopted here 2026-09-04; the capability is unchanged.
   */
  if (can(P.CONFIGURATION_VIEW)) {
    // "Standards" — AB-12 §18: the Department Lead's word for it, not ours.
    items.push({ href: "/dashboard/configuration", label: "Standards" });
  }
  // The control plane sits last — it is not part of the legal workflow (§H).
  if (can(P.USER_MANAGE) || can(P.AUDIT_VIEW)) items.push({ href: "/dashboard/admin", label: "Administration" });
  /*
   * Research is deliberately ABSENT. Its screen exists and says so honestly
   * ("Statute research isn't available yet"), but statute intake is an open
   * owner decision (C-16), so the capability does not exist — and a nav slot is
   * a promise. Restore this line in the same change that ships the capability:
   *   if (can(P.ASSIST_ASK)) items.push({ href: "/dashboard/research", label: "Research" });
   */
  return items;
}

/**
 * The nav item a pathname belongs to — the LONGEST matching href, so that
 * `/dashboard/reviews/…` lights "Reviews" and never also "Documents" (whose
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
  latest_analysis?: { user_status_counts?: Record<string, number> } | null;
}): boolean {
  const counts = row.latest_analysis?.user_status_counts;
  if (!counts) return false;
  return Object.entries(counts).some(([status, n]) => status !== "ACCEPTABLE" && n > 0);
}

/** Review lifecycle states that mean "a result is still coming" (Step 30) —
 *  the same set `findingsState.tsx` polls on. */
const IN_FLIGHT_REVIEW_STATUSES = new Set(["DRAFT", "UPLOADED", "PROCESSING"]);

/**
 * The four Documents-list buckets (2026-09-01 redesign), mirroring the
 * server's own `_status_bucket` field for field: never a new lifecycle enum,
 * never a Finding Classification (REC-02's boundary) — purely a rendering
 * grouping of `latest_version`/`latest_analysis`, the exact fields
 * `analysisCell`/`rowNeedsAttention` already read. Kept in lockstep with the
 * backend intentionally; if either changes, `test_contracts_list_status_filter_
 * matches_the_same_bucket_the_row_shows` (backend) is the tripwire.
 */
export type DocumentStatusBucket = "draft" | "analyzing" | "needs_attention" | "analyzed";

export function documentStatusBucket(row: {
  latest_version?: { processing_status: string } | null;
  latest_analysis?: {
    review_status: string;
    user_status_counts?: Record<string, number>;
  } | null;
}): DocumentStatusBucket {
  if (!row.latest_version || row.latest_version.processing_status !== "COMPLETED") return "draft";
  const analysis = row.latest_analysis;
  if (!analysis) return "draft";
  if (IN_FLIGHT_REVIEW_STATUSES.has(analysis.review_status)) return "analyzing";
  const counts = analysis.user_status_counts ?? {};
  const hasIssue = Object.entries(counts).some(([status, n]) => status !== "ACCEPTABLE" && n > 0);
  return hasIssue ? "needs_attention" : "analyzed";
}

export const STATUS_BUCKET_LABEL: Record<DocumentStatusBucket, string> = {
  draft: "Draft",
  analyzing: "Analyzing",
  needs_attention: "Needs attention",
  analyzed: "Analyzed",
};

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

/* --------------------------------------------------------------------------
 * Document presentation (2026-09-02, DD-14). The extraction stores plain text
 * spans — no bold, no alignment, no font survives it — so the viewer cannot
 * REPRODUCE the source formatting, only recognise the structural shapes the
 * text itself still carries and set them the way a legal agreement sets them.
 * Every rule below re-renders the UNMODIFIED string; nothing is added,
 * dropped or reworded, and a row that matches no shape stays a paragraph.
 * Grounded against the real MSA rows, not guessed (see the DD-14 record).
 * -------------------------------------------------------------------------- */
export type RowKind = "title" | "heading" | "subheading" | "item" | "para";

/** `(a) `, `(iv) `, `(B) ` — the enumerated-item lead the source indents. */
const ITEM_LEAD = /^\((?:[a-z]{1,3}|[A-Z]{1,3}|\d{1,2})\)\s/;

export function rowPresentation(
  row: Pick<EvidenceRow, "content" | "section_number" | "section_title">,
  index: number,
): RowKind {
  const text = row.content.trim();
  // The document title: the first row, before any numbering exists, one short
  // line with no sentence punctuation ("Master Services Agreement").
  if (index === 0 && !row.section_number && text.length <= 80 && !/[.:;,]$/.test(text)) {
    return "title";
  }
  // A heading row is one whose content IS its own section label and nothing
  // else: strip the leading number ("1." / "4.3") and compare what remains to
  // the recorded section title. "1. DEFINITIONS AND INTERPRETATION" qualifies;
  // "1.1 Defined Terms: Capitalized terms used…" carries body text and stays a
  // paragraph.
  if (row.section_number && row.section_title) {
    const stripped = text
      .replace(/^[\s§]*[\d.]+[).:]?\s*/, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    const title = row.section_title.replace(/\s+/g, " ").trim().toLowerCase();
    if (stripped === title && text.length <= 120) {
      return row.section_number.includes(".") ? "subheading" : "heading";
    }
  }
  if (ITEM_LEAD.test(text)) return "item";
  return "para";
}

/**
 * Which empty state the document pane owes a reader when no evidence rows came
 * back (2026-09-03).
 *
 * A pure decision because the branch was WRONG and silently so: the pane tested
 * `processing_status !== "COMPLETED"` and therefore told a reader to "reload to
 * check" a document whose processing had definitively FAILED and would never
 * change. That state went from rare to reachable when extraction started
 * refusing text it cannot read rather than returning glyph codes as content, so
 * it now needs to be right — and pinned somewhere a static test can reach it.
 *
 *   "processing"  still running; reloading genuinely helps
 *   "unreadable"  finished and unsuccessful — a scan with no recoverable
 *                 characters, or fonts that do not map to readable text
 *   "empty"       processing succeeded and the document genuinely has no text
 *
 * The two statuses are separate axes (34.15) and either may carry the failure,
 * so both are consulted rather than one standing in for the other.
 */
export type DocumentTextState = "processing" | "unreadable" | "empty";

export function documentTextState(version: {
  processing_status: string;
  extraction_status?: string | null;
}): DocumentTextState {
  if (version.processing_status === "FAILED" || version.extraction_status === "FAILED") {
    return "unreadable";
  }
  if (version.processing_status !== "COMPLETED") return "processing";
  return "empty";
}

/**
 * Counterparty names the reader can ALREADY see on the Dashboard list — the
 * intake and edit datalists converge on these, and only these (2026-09-06).
 * Deliberately no "every counterparty" endpoint: one would disclose names
 * across owners and departments, and this list is already permission-scoped
 * by the server. Trimmed, de-duplicated, sorted; a row with nothing declared
 * contributes nothing.
 */
export function knownCounterparties(
  contracts: ReadonlyArray<{ latest_version?: { counterparty?: string } | null }> | null,
): string[] {
  const seen = new Set<string>();
  for (const contract of contracts ?? []) {
    const name = contract.latest_version?.counterparty?.trim();
    if (name) seen.add(name);
  }
  return [...seen].sort((a, b) => a.localeCompare(b));
}

/**
 * Review order for the Findings list (P-4, 2026-09-06). The API returns findings
 * in engine order — the requirement catalogue's — which scatters the eight that
 * need a decision among the fourteen that do not. Presentation only (rule 18):
 * nothing here decides an outcome; it decides what the reader meets first.
 *
 *   1. findings that need a decision, then the rest — the reader's task first;
 *   2. within each, DOCUMENT order: the earliest clause the finding cites
 *      (page, then the section number as the document numbers it);
 *   3. then the requirement's heading, then id — so two findings on one clause
 *      sit in a stable order.
 *
 * Deterministic: the same findings always yield the same order. A finding
 * citing nothing locatable sorts after those that do, never among them.
 */
export function reviewOrder<
  T extends {
    id: string;
    requires_decision: boolean;
    evidence: ReadonlyArray<{ page_number: number | null; section_number: string | null }>;
    requirement: { code?: string | null; name?: string | null };
  },
>(findings: readonly T[]): T[] {
  const position = (f: T): number[] => {
    let best: number[] | null = null;
    for (const e of f.evidence) {
      const parts = (e.section_number ?? "").split(".").map((n) => Number.parseInt(n, 10));
      const key = [e.page_number ?? Number.POSITIVE_INFINITY,
                   ...(parts.some(Number.isNaN) || parts.length === 0 ? [Number.POSITIVE_INFINITY] : parts)];
      if (best === null || compareKeys(key, best) < 0) best = key;
    }
    return best ?? [Number.POSITIVE_INFINITY];
  };
  return [...findings].sort((a, b) =>
    Number(b.requires_decision) - Number(a.requires_decision)
    || compareKeys(position(a), position(b))
    || requirementHeading(a.requirement).localeCompare(requirementHeading(b.requirement))
    || a.id.localeCompare(b.id));
}

function compareKeys(a: number[], b: number[]): number {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? -1, y = b[i] ?? -1;      // a shorter key ("3") precedes its children ("3.1")
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

/**
 * The divider word above an annexed part — the KIND the document's own title
 * uses ("Annexure", "Schedule", "Appendix", "Exhibit"), never an invented name.
 * Undefined for a row that is not one (44.4's "where detectable").
 */
export function partLabel(row: { annexure?: string }): string | undefined {
  const word = row.annexure?.match(/^[A-Za-z]+/)?.[0];
  return word ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase() : undefined;
}

/**
 * Key Obligations categories — the accordion rows (owner, 2026-09-08). The
 * server groups under the document's OWN role labels; this collapses the
 * mutual ones ("Both Parties", "Parties", "Each Party") into one row and reads
 * "Neither Party" as the prohibition it is, so a Sales or CS reader gets a
 * sentence rather than a legal role noun.
 *
 * A NAMED role keeps its own label verbatim ("Receiving Party must"). The
 * requested "Our company must" / "The other party must" split is deliberately
 * NOT synthesised: nothing in the extraction says which role is us — a mutual
 * NDA makes both sides the Receiving Party — and guessing would tell a
 * non-lawyer that an obligation is ours when it is the counterparty's.
 */
export interface ObligationCategory<T> {
  key: string;
  title: string;
  items: T[];
}

export function obligationCategories<T>(
  groups: Array<{ party_label: string; items: T[] }>,
): Array<ObligationCategory<T>> {
  const rank = { mutual: 0, role: 1, neither: 2 };
  const seen = new Map<string, ObligationCategory<T> & { order: number }>();
  for (const group of groups) {
    // Real extractions carry every casing and article the documents use —
    // "Customer"/"customer", "Receiving Party"/"The Receiving Party" — so a
    // role's identity is its bare lower-case name, which merges those.
    const label = group.party_label.trim().replace(/\s+/g, " ")
      .replace(/\s*obligations?$/i, "").replace(/^the\s+/i, "");
    const bare = label.toLowerCase();
    const kind = /^neither\b/.test(bare)
      ? "neither"
      : /^(both|each|either|all)?\s*(part(y|ies)|sides?)$/.test(bare)
        ? "mutual"
        : "role";
    const key = kind === "role" ? `role:${bare}` : kind;
    const title = kind === "neither" ? "Neither side can"
      : kind === "mutual" ? "Both sides must"
        : `${label.charAt(0).toUpperCase()}${label.slice(1)} must`;
    const existing = seen.get(key);
    if (existing) existing.items = existing.items.concat(group.items);
    else seen.set(key, { key, title, items: [...group.items], order: rank[kind] });
  }
  return [...seen.values()]
    .filter((category) => category.items.length > 0)
    .sort((a, b) => a.order - b.order)
    .map(({ key, title, items }) => ({ key, title, items }));
}

/**
 * Diff-Talk's pure helpers — no React, no I/O — so each can be tested alone.
 */
import type { ComparedClause, DocumentComparison } from "@/lib/types";

export type Row = DocumentComparison["clauses"][number];
/** A row that takes a choice: a wording difference (not a clause that only moved). */
export type Decidable = Exclude<Row["status"], "UNCHANGED">;
/** The reader's drafting choice on one difference (owner, 2026-10-13). A choice
 *  about wording, never a Legal Decision: the final contract still goes through
 *  the review, where Legal decides (AB-12 r9, RESOLVED ≠ MATCH). */
export type Choice = "ours" | "theirs";
export type Filter = "ALL" | Decidable;

/** A contract type's own website document, offered first when a contract opens
 *  Diff-Talk from its workspace. A default only — the reader can pick anything. */
export const WEBSITE_KEY_BY_TYPE: Record<string, string> = {
  TOS: "TOS-leapswitch", SLA: "SLA-leapswitch", AUP: "AUP-leapswitch",
  PRIVACY_POLICY: "PRIVACY-leapswitch",
};

/** What each choice does to the TEXT, in the words of that kind of difference. */
export const CHOICE_WORDS: Record<Decidable, Record<Choice, string>> = {
  CHANGED: { ours: "Keep ours", theirs: "Accept theirs" },
  ADDED: { ours: "Leave it out", theirs: "Add it" },
  REMOVED: { ours: "Keep ours", theirs: "Remove it" },
};

export const isDifference = (r: Row) => r.status !== "UNCHANGED" || r.moved;
export const isDecidable = (r: Row): r is Row & { status: Decidable } => r.status !== "UNCHANGED";

/** Kept against the clauses' own ids — stable across reloads and never shared by
 *  two clauses that open with the same words (a text prefix was; strict review). */
export const rowKey = (r: Row) => `${r.status}|${r.left?.id ?? ""}|${r.right?.id ?? ""}`;

/** Whitespace collapsed, one sentence per line, so the viewer pairs sentences — a
 *  PDF breaks lines wherever the page ran out. A word hyphenated across a line is
 *  one word; a list number, an initial or a company/legal abbreviation ("Pvt.
 *  Ltd.", "No.", "e.g.") never ends a sentence. */
export function sentences(text: string): string {
  return text.replace(/(\w)-[ \t]*\n\s*(?=\w)/g, "$1-").replace(/\s+/g, " ").trim()
    .split(/(?<=[^\s\d][.;!?])(?<!\b(?:[A-Z]|Pvt|Ltd|Co|No|Nos|Inc|Corp|Mr|Mrs|Ms|Dr|St|Rs|vs|viz|e\.g|i\.e|etc)\.)\s+(?=[("“'A-Z0-9])/u)
    .join("\n");
}

// No single letters here: in a legal heading "A" is a label ("Schedule A"), not "a".
const SMALL = new Set(["an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"]);
/** ALL-CAPS clause headings ("1. DEFINITIONS") read as shouting in a list —
 *  shown in title case. Display only; the documents are untouched. */
export function tidyTitle(title: string): string {
  const letters = title.replace(/[^A-Za-z]/g, "");
  if (letters.length < 4 || title !== title.toUpperCase()) return title;
  return title.toLowerCase().replace(/[a-z][a-z’']*/g, (w, i: number) =>
    i > 0 && SMALL.has(w) ? w : w[0]!.toUpperCase() + w.slice(1));
}

export function clauseName(c: ComparedClause | null): string {
  if (!c) return "";
  const title = (c.title ?? "").replace(/^\W*\d+(\.\d+)*\.?\s*/, "");
  if (c.ref && title) return tidyTitle(`${c.ref}. ${title}`);
  return c.ref ? `Clause ${c.ref}` : tidyTitle(title) || "Opening text";
}

/** "2 of 21" sentences — how much of a changed clause to read, before reading it. */
export function changedSentences(left: ComparedClause, right: ComparedClause): string {
  const ours = new Set(sentences(left.text).split("\n"));
  const theirs = sentences(right.text).split("\n");
  const n = theirs.filter((t) => !ours.has(t)).length || 1;
  return `${n} of ${theirs.length} sentence${theirs.length === 1 ? "" : "s"}`;
}

/** Fewer than half the words in common: word marks over a whole clause are noise,
 *  so the two texts are shown plainly, side by side (design plan §4.2). Measured on
 *  WORDS — a one-sentence clause with one word changed is an edit, not a rewrite. */
export function isRewritten(left: ComparedClause, right: ComparedClause): boolean {
  const words = (t: string) => new Set(t.toLowerCase().match(/\w+/g) ?? []);
  const a = words(left.text), b = words(right.text);
  const shared = [...a].filter((w) => b.has(w)).length;
  return 2 * shared < 0.5 * (a.size + b.size);
}

/** The plain-text list a reader pastes into an email to Legal. */
export function choicesForLegal(oursTitle: string, theirsTitle: string, rows: Row[],
                                choices: Record<string, Choice>): string {
  return [`Diff-Talk — ${oursTitle} (ours) vs ${theirsTitle} (client)`, "",
    ...rows.filter(isDecidable).map((row) => {
      const pick = choices[rowKey(row)];
      return `• ${clauseName(row.right ?? row.left)} — ${pick
        ? CHOICE_WORDS[row.status][pick] : "not decided yet"}`;
    })].join("\n");
}

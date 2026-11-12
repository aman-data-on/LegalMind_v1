/**
 * The reading view set as a contract is set (CLM UI pass 2, owner 2026-11-02): clause
 * numbers in a hanging gutter, nested levels one consistent step in, connectors centred,
 * lettered recitals hung, defined terms in weight, and the tracked changes marked in the
 * text itself rather than in a box under it.
 *
 * PRESENTATION ONLY (`AM-57`, rule 17). Everything is read from the evidence row as it
 * stands — its text, the parser's `section_number`, its recorded changes — and nothing is
 * re-extracted. The concatenation of a row's pieces is always exactly `row.content`, so
 * selection offsets, highlights and annotations address the same string as before.
 */

import type { Annotation } from "./annotations";
import { segmentContent } from "./annotations";

/** Where a row sits on the sheet: its gutter number (in the text, or the parser's for a
 *  heading whose text carries none), and its indent and hang in em. */
export interface ReadingLine {
  /** Characters at the start of `content` that are the clause number + its space. */
  lead: number;
  /** A heading's number from the parser's list numbering, shown in the gutter only. */
  num: string | null;
  indent: number;
  hang: number;
  shape: "connector" | "label" | null;
}

/** One gutter width per kind of number, so siblings' text lines up. The clause ladder is
 *  the generated contract's own (backend `config/templates/house/house.json`
 *  `clause_ladder_twips`, LeapSwitch's approved MSA format, 2026-11-04), in em at its 12pt
 *  (1em = 240 twips), so the preview is the document: each level's text starts 0.5in
 *  further in ("1." text at 0.5in, "1.1." at 1in, "1.1.1." at 1.5in …), its number in the
 *  0.5in before it; "(a)" hangs 0.5in under its clause's text like `list_twips`, and the
 *  lettered parties and recitals 1cm like `party_twips`. */
const EM = (twips: number) => twips / 240;
const HANG = { clause: EM(720), step: EM(720), letter: EM(720), roman: EM(720), recital: EM(567) } as const;

const NUMERIC = /^\s*(\d{1,3}(?:\.\d{1,3}){0,4})\.?\s+(?=[A-Z“"‘'(\[])/;
const LETTER = /^\s*\(([a-zA-Z]{1,2})\)\s+(?=\S)/;
const ROMAN = /^\s*\(?([ivxlc]{1,6})[.)]\s+(?=\S)/;
const RECITAL = /^\s*([A-Z])\.\s+(?=\S)/;
const CONNECTOR = /^\s*(and|between|by and between|among|versus)\s*$/i;
const LABEL = /^\s*(whereas|recitals|now,? therefore|now this agreement witnesse(?:s|th)|in witness whereof)\b[^.]{0,40}[,:]?\s*$/i;

interface Row {
  content: string;
  section_number: string | null;
  is_heading?: boolean;
  /** A generated contract's paragraph style ("LM Heading 2", "LM Recital" …). */
  house_style?: string;
}

/** A contract LegalMind generated is set on the house ladder (`house.json`
 *  `clause_ladder_twips`, one for the whole document since Round 6), in em at 12pt like
 *  `HANG`. Per level: [where the number starts, where the text starts]. */
const HOUSE_MAIN = [[0, 720], [720, 1440], [1440, 2160], [2160, 2880], [2880, 3600]];
const HOUSE_PARTY = 567;                       // `party_twips`: A. / B. hung 1cm
const LIST_GUTTER = 720;                       // `list_twips`

function houseLayout(rows: Row[]): ReadingLine[] {
  let letter = 0;                              // A., B. — parties, then recitals
  let item = 0;                                // (a), (b) — an LM List run
  const ladder = HOUSE_MAIN;
  let text = 0;                                // where the current clause's text starts
  const at = (from: number, to: number, num: string | null): ReadingLine =>
    ({ lead: 0, num, indent: EM(from), hang: EM(to - from), shape: null });
  return rows.map((row) => {
    const style = row.house_style ?? "";
    if (style !== "LM List") item = 0;
    if (style === "LM Recital") {
      if (/^(Registered office|CIN): /.test(row.content)) return at(HOUSE_PARTY, HOUSE_PARTY, null);
      letter += 1;
      return at(0, HOUSE_PARTY, `${String.fromCharCode(64 + letter)}.`);
    }
    if (style !== "LM Connector") letter = 0;
    if (style === "LM Connector") return at(HOUSE_PARTY, HOUSE_PARTY, null);
    const level = Number(/^LM (?:Heading|Body) ([1-5])$/.exec(style)?.[1] ?? 0);
    if (level && style.startsWith("LM Heading") && row.section_number) {
      const [from, to] = ladder[level - 1] as [number, number];
      text = to;
      return at(from, to, `${row.section_number}.`);
    }
    if (level) return at(ladder[level - 1]![1]!, ladder[level - 1]![1]!, null);
    if (style === "LM List") {
      item += 1;
      return at(text, text + LIST_GUTTER, `(${String.fromCharCode(96 + item)})`);
    }
    return at(0, 0, null);                     // title, front matter, plain headings
  });
}

/** One pass in reading order: each row's gutter and indent, from the numbers the text
 *  states. "(i)" after "(h)" is a letter; otherwise it is a roman sub-item. */
export function readingLayout(rows: Row[]): ReadingLine[] {
  // a generated contract carries its own structure: set it as the file prints it
  if (rows.some((row) => row.house_style)) return houseLayout(rows);
  let clauseBody = 0;          // where a numbered clause's text starts
  let letterBody: number | null = null;
  let lastLetter: string | null = null;
  let numbered = false;        // past the preamble
  return rows.map((row) => {
    const text = row.content;
    if (CONNECTOR.test(text)) return { lead: 0, num: null, indent: 0, hang: 0, shape: "connector" };
    if (LABEL.test(text)) return { lead: 0, num: null, indent: 0, hang: 0, shape: "label" };

    /** A clause numbered `n`, on the ladder by its depth. */
    const clause = (n: string, lead: number, num: string | null): ReadingLine => {
      const depth = n.split(".").length;
      numbered = true;
      letterBody = null;
      lastLetter = null;
      const indent = HANG.step * (depth - 1);
      const hang = HANG.clause;
      clauseBody = indent + hang;
      return { lead, num, indent, hang, shape: null };
    };
    const numeric = NUMERIC.exec(text);
    if (numeric) return clause(numeric[1]!, numeric[0].length, null);
    // A number that is the document's own list numbering (the parser's `section_number`),
    // not in its text — a heading, or a generated contract's 2.1.1.1: in the gutter.
    const listed = row.section_number;
    if (listed && /^\d{1,3}(\.\d{1,3}){0,4}$/.test(listed)
        && (row.is_heading || !text.trimStart().startsWith(listed))) {
      return clause(listed, 0, listed);
    }

    const letter = LETTER.exec(text);
    const roman = ROMAN.exec(text);
    const continuesLetters = letter && lastLetter !== null && letter[1]!.length === 1
      && letter[1]!.toLowerCase().charCodeAt(0) === lastLetter.charCodeAt(0) + 1;
    if (roman && !continuesLetters && !(letter && lastLetter === null && roman[1] !== "i")) {
      const indent = letterBody ?? clauseBody;
      return { lead: roman[0].length, num: null, indent, hang: HANG.roman, shape: null };
    }
    if (letter) {
      lastLetter = letter[1]!.toLowerCase();
      letterBody = clauseBody + HANG.letter;
      return { lead: letter[0].length, num: null, indent: clauseBody, hang: HANG.letter, shape: null };
    }
    const recital = RECITAL.exec(text);
    if (recital) {
      return { lead: recital[0].length, num: null, indent: numbered ? clauseBody : 0,
               hang: HANG.recital, shape: null };
    }
    // An unnumbered paragraph continues the clause it follows, aligned with its text.
    letterBody = null;
    lastLetter = null;
    return { lead: 0, num: null, indent: numbered ? clauseBody : 0, hang: 0, shape: null };
  });
}

/** A run of a row's text and what it carries. */
export interface Piece {
  text: string;
  lead?: true;
  term?: true;
  /** The file's own weight on these words (a generated contract's `emphasis`). */
  bold?: true;
  underline?: true;
  /** Inserted words (`<ins>`); `del` is what they replaced, shown struck before them. */
  ins?: { del?: string };
  annotation?: Annotation;
}

export interface Change { deleted: string; inserted: string }

/** Placed inline only when the inserted words can be found without guessing: in order,
 *  after the previous change, and either long enough or appearing once. */
function placeChanges(content: string, from: number, changes: Change[]) {
  const placed: { start: number; end: number; del?: string }[] = [];
  const rest: Change[] = [];
  let cursor = from;
  for (const change of changes) {
    const word = change.inserted;
    const at = word ? content.indexOf(word, cursor) : -1;
    const unique = at >= 0 && content.indexOf(word, at + 1) < 0;
    if (at < 0 || (word.trim().length < 3 && !unique)) {
      rest.push(change);
      continue;
    }
    const shortDel = change.deleted && change.deleted.length <= 40 ? change.deleted : undefined;
    placed.push({ start: at, end: at + word.length, ...(shortDel ? { del: shortDel } : {}) });
    if (change.deleted && !shortDel) rest.push({ deleted: change.deleted, inserted: "" });
    cursor = at + word.length;
  }
  return { placed, rest };
}

const DEFINED = /^\s*(“[^”]{1,80}”|"[^"]{1,80}")\s+(?=shall mean|means|shall have|has the meaning|includes)/;

/**
 * Split a row's text at every boundary — the gutter number, a defined term, each placed
 * change and each annotation — into pieces whose text, joined, is `content` exactly.
 * Changes the text cannot place come back as `unplaced`, for the note under the row.
 */
export function readingPieces(content: string, opts: {
  lead: number; changes?: Change[]; annotations?: Annotation[]; marks: boolean;
  emphasis?: [number, number, "b" | "u"][];
}): { pieces: Piece[]; unplaced: Change[]; lead: number } {
  const segments = segmentContent(content, opts.annotations ?? []);
  const notes: { start: number; end: number; annotation: Annotation }[] = [];
  let at = 0;
  for (const seg of segments) {
    if (seg.annotation) notes.push({ start: at, end: at + seg.text.length, annotation: seg.annotation });
    at += seg.text.length;
  }
  // One gutter element per row: a mark over the number keeps the row unhung.
  const lead = notes.some((n) => n.start < opts.lead) ? 0 : opts.lead;
  const { placed, rest } = opts.marks && opts.changes?.length
    ? placeChanges(content, lead, opts.changes)
    : { placed: [], rest: opts.changes ?? [] };
  // the file's own weight, where it states it, wins over reading a term from the text
  const defined = opts.emphasis ? null : DEFINED.exec(content.slice(lead));
  const term = defined ? [lead + defined[0].indexOf(defined[1]!), lead + defined[0].indexOf(defined[1]!) + defined[1]!.length] : null;

  const cuts = new Set<number>([0, content.length, lead]);
  for (const p of placed) { cuts.add(p.start); cuts.add(p.end); }
  for (const n of notes) { cuts.add(n.start); cuts.add(n.end); }
  if (term) { cuts.add(term[0]!); cuts.add(term[1]!); }
  const weight = opts.emphasis ?? [];
  for (const [from, to] of weight) { cuts.add(from); cuts.add(to); }
  const points = [...cuts].filter((n) => n >= 0 && n <= content.length).sort((a, b) => a - b);
  const pieces: Piece[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i]!;
    const end = points[i + 1]!;
    if (end <= start) continue;
    const piece: Piece = { text: content.slice(start, end) };
    if (start < lead) piece.lead = true;
    if (term && start >= term[0]! && end <= term[1]!) piece.term = true;
    for (const [from, to, kind] of weight) {
      if (start >= from && end <= to) piece[kind === "b" ? "bold" : "underline"] = true;
    }
    const change = placed.find((p) => start >= p.start && end <= p.end);
    if (change) piece.ins = start === change.start && change.del ? { del: change.del } : {};
    const note = notes.find((n) => start >= n.start && end <= n.end);
    if (note) piece.annotation = note.annotation;
    pieces.push(piece);
  }
  return { pieces: pieces.length ? pieces : [{ text: content }], unplaced: opts.marks ? rest : [], lead };
}

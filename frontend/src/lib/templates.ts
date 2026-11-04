/**
 * Template approval (S4, `AM-282`/`AM-283`) — the page's pure logic: the shapes the
 * templates API sends, how clauses are grouped for the lawyer, and the plain words for
 * the publish gate's problems. Presentation only: the engine classifies and the server
 * gates publishing; nothing here decides whether a clause meets a standard.
 */

import { shortDate } from "@/components/workspace/model";

export type TemplateStatus = "DRAFT" | "APPROVED" | "PUBLISHED" | "RETIRED";

export interface TemplateSummary {
  id: string;
  template_key: string;
  version: number;
  status: TemplateStatus;
  doc_type: string;
  brand: string | null;
  title: string | null;
  label: string | null;
  clauses_approved: number;
  clauses_total: number;
  progress: string;
  published_at: string | null;
  /** the file the template was imported from (tells two of one type apart) */
  source_file?: string | null;
}

export interface Block {
  kind: string;
  key?: string;
  text?: string;
  term?: string;
  body?: Block[];
  items?: string[];
  header?: string[];
  rows?: string[][];
  alt?: string;
}

export interface ClauseApproval {
  decision: "APPROVE" | "REPLACE" | "NO_POSITION" | null;
  approved_by: string;
  approved_by_name: string | null;
  approved_at: string | null;
  reason: string | null;
}

export interface TemplateClause {
  clause_key: string;
  version: number;
  title: string;
  body: Block[];
  status: "DRAFT" | "APPROVED" | "RETIRED";
  variables: string[];
  label: string | null;
  flags?: string[];
  approval?: ClauseApproval | null;
  /** the clause as a lawyer types it, numbers and markers included (approvers only) */
  wording?: string;
  /** the version the published template uses; null when it is not in it (approvers only) */
  published_version?: number | null;
}

/** One recorded version of a clause (`GET …/clauses/{key}/versions`), newest first. */
export interface ClauseVersionRow {
  version: number;
  status: "DRAFT" | "APPROVED" | "RETIRED";
  decision: ClauseApproval["decision"];
  reason: string | null;
  supplier_kind: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  created_at: string | null;
  in_this_template: boolean;
  published: boolean;
  wording: string;
}

/** One line of a clause as the renderer will number it (`…/replace` with `dry_run`). */
export interface OutlineLine { number: string | null; level: number; kind: string; text: string }

export interface TemplateVariable { key: string; type: string; group?: string; help?: string }

export interface TemplateDetail extends TemplateSummary {
  variables: TemplateVariable[];
  clauses: TemplateClause[];
  flags?: string[];
  /** the published version of this template, when this is a newer draft (approvers only) */
  published?: { id: string; version: number } | null;
  /** who approved the text outside LegalMind, as recorded with the publish (`AM-302` r6) */
  approval_reference?: string | null;
  /** `AM-307`: can a contract made from this template carry Special Conditions (Annexure A) */
  special_conditions?: SpecialConditionsReadiness;
}

export interface SpecialConditionsReadiness { ready: boolean; missing: { code: string; detail: string }[] }

/** One standard the engine finds not met by the text as it stands (`GET …/check`). */
export interface CheckStandard {
  code: string;
  name?: string;
  description: string | null;
  /** the Constitution's topic for it ("Liability") — a label, never a position */
  topic?: string | null;
  classification: "DEVIATION" | "CONFLICT" | "UNABLE_TO_EVALUATE" | "MISSING" | string;
  /** the clauses its evidence is read from; empty when nothing in the template holds it */
  clause_keys: string[];
  /** present only for `legal_position.view` (LEGAL-02: omitted, never nulled) */
  position?: string | null;
}

export interface TemplateCheck { publishable: boolean; problems: string[]; standards: CheckStandard[] }

const BRANDS: Record<string, string> = { LEAPSWITCH: "LeapSwitch", CLOUDPE: "CloudPe" };

export function brandLabel(brand: string | null): string {
  if (!brand) return "";
  return BRANDS[brand] ?? brand.charAt(0) + brand.slice(1).toLowerCase();
}

/** "LeapSwitch NDA" — the brand and the short type, the way the team says it. */
export function templateName(t: Pick<TemplateSummary, "brand" | "doc_type">): string {
  const type = t.doc_type === "OTHER" ? "agreement" : t.doc_type.replace(/_/g, " ");
  return [brandLabel(t.brand), type].filter(Boolean).join(" ");
}

/** A heading the document sets in capitals ("LIMITATION OF LIABILITY"), in sentence case
 *  where LegalMind names it — the sheet itself keeps the document's own letters. */
export function displayTitle(title: string): string {
  if (title !== title.toUpperCase() || !/[A-Z]/.test(title)) return title;
  const lower = title.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export const approved = (c: TemplateClause) => c.status === "APPROVED";

export function allApproved(t: TemplateSummary): boolean {
  return t.clauses_total > 0 && t.clauses_approved === t.clauses_total;
}

/** The gate can pass: every clause approved and the check finds nothing. */
export function canPublish(t: TemplateSummary, check: TemplateCheck | null): boolean {
  return t.status === "DRAFT" && allApproved(t) && !!check?.publishable;
}

/** A local demo copy published by hand (its label says "DEMO …"): never approved by
 *  Legal, so its clause count is not shown as progress. */
export const DEMO_WORDS = "Demo — not approved by Legal";
export const isDemo = (t: Pick<TemplateSummary, "label">) => !!t.label?.startsWith("DEMO");

export function statusWords(t: TemplateSummary, check: TemplateCheck | null): string {
  if (t.status === "PUBLISHED") return `Published, version ${t.version}`;
  if (t.status === "RETIRED") return `Version ${t.version}, replaced by a newer one`;
  // ONE status word for a draft (cross-page pass); what still stands in the way is the
  // `blockers` sentence beside it, never a second status
  return canPublish(t, check) ? "Ready to publish" : "Draft";
}

/** What stands in the way of publishing, in one sentence — or null when nothing does.
 *  The problem count is the check's (`stopCount`), the same on the list, the template's
 *  header and "Before publishing". */
export function blockers(t: TemplateSummary, check: TemplateCheck | null | undefined): string | null {
  if (t.status !== "DRAFT") return null;
  const parts: string[] = [];
  const left = t.clauses_total - t.clauses_approved;
  if (left) parts.push(`${left} ${left === 1 ? "clause" : "clauses"} to approve`);
  const n = stopCount(check);
  if (n) parts.push(`${n} ${n === 1 ? "problem stops" : "problems stop"} publishing`);
  return parts.length ? `${parts.join(". ")}.`.replace(/^./, (c) => c.toUpperCase()) : null;
}

/** The check takes seconds (the engine reads the whole text); it always finishes — with
 *  the result, or as failed after `ms`, so no screen waits on it for ever. */
export const CHECK_TIMEOUT_MS = 60_000;
export function within<T>(promise: Promise<T>, ms = CHECK_TIMEOUT_MS): Promise<T> {
  return Promise.race([promise, new Promise<T>((_, reject) => {
    setTimeout(() => reject(new Error("The check took too long.")), ms);
  })]);
}

/** How many problems stop publishing — every standard not met and every line of the
 *  file's problems, counted exactly as "Before publishing" lists them, so the list page,
 *  the header and the publish sheet say the same number. */
export function stopCount(check: TemplateCheck | null | undefined): number {
  if (!check) return 0;
  return check.standards.length + problemLines(check.problems, [], check).length;
}

/**
 * A standard the engine reads across most of the template (mutuality: its evidence sits
 * in 12 of 15 clauses) is a point about the whole template, not about each clause.
 * ponytail: a fixed count; tune it if templates of very different sizes need it.
 */
const SPREAD = 3;

export const placed = (s: CheckStandard) => s.clause_keys.length > 0 && s.clause_keys.length <= SPREAD;
/** the engine could not measure it ("Could not be checked"): a reading for the lawyer, not a difference */
export const unchecked = (s: CheckStandard) => s.classification === "UNABLE_TO_EVALUATE";

export function failingOn(clauseKey: string, check: TemplateCheck | null): CheckStandard[] {
  return (check?.standards ?? []).filter((s) => placed(s) && s.clause_keys.includes(clauseKey));
}

export interface ClauseGroup {
  id: "differs" | "unchecked" | "check" | "todo" | "approved";
  title: string;
  /** one sentence: why these clauses are together */
  why: string | null;
  clauses: TemplateClause[];
}

/** What the gate will refuse first — a clause that differs from our standard, then one
 *  the check could not measure — then the import's notes, then what is left to approve,
 *  then what is approved; each in the template's own order. */
export function groupClauses(clauses: TemplateClause[], check: TemplateCheck | null): ClauseGroup[] {
  const groups: ClauseGroup[] = [
    { id: "differs", title: "Differs from our standard", clauses: [],
      why: "The check reads these as not meeting one of our standards. Replace them with our wording." },
    { id: "unchecked", title: "Couldn\u2019t be checked, read it yourself", clauses: [],
      why: "The check found the clause but could not measure it against our standard. Read it and decide." },
    { id: "check", title: "Check this clause", clauses: [],
      why: "The import could not place something in these." },
    { id: "todo", title: "Nothing to fix", clauses: [], why: "The check finds nothing here. Approve each as it stands." },
    { id: "approved", title: "Approved", clauses: [], why: null },
  ];
  for (const clause of clauses) {
    const fails = failingOn(clause.clause_key, check);
    const at = fails.some((s) => !unchecked(s)) ? 0 : fails.length ? 1
      : approved(clause) ? 4 : clause.flags?.length ? 2 : 3;
    groups[at]!.clauses.push(clause);
  }
  return groups.filter((g) => g.clauses.length);
}

/** A standard in a few words: its Constitution topic ("Change of control"), else the
 *  first words of the standard. */
export function topicWords(s: CheckStandard): string {
  const topic = s.topic?.split(" \u2014 ").pop()?.trim();
  if (topic) return topic.charAt(0) + topic.slice(1).toLowerCase();
  const words = (s.description ?? s.code).split(/\s+/);
  return words.length > 6 ? `${words.slice(0, 6).join(" ")}\u2026` : words.join(" ");
}

/** Why a standard is not met, in a few words ("Differs: liability"). */
export function shortWhy(s: CheckStandard): string {
  const lead = s.classification === "CONFLICT" ? "Says it twice, differently"
    : unchecked(s) ? "Couldn\u2019t be checked" : s.classification === "MISSING" ? "Not in this template" : "Differs";
  return `${lead}: ${topicWords(s)}`;
}

/** The list order — what j / k walk through. */
export const listOrder = (groups: ClauseGroup[]) => groups.flatMap((g) => g.clauses);

const FLAG_TAIL = /\s*[—-]\s*check this clause.*$/i;
export const flagWords = (flag: string) => {
  const words = flag.replace(FLAG_TAIL, "").replace(/^front:\s*/, "");
  return words.charAt(0).toUpperCase() + words.slice(1);
};

export function approvedLine(a: ClauseApproval | null | undefined): string {
  if (!a) return "Approved";
  const by = a.approved_by_name ? ` by ${a.approved_by_name}` : "";
  const when = a.approved_at ? `, ${shortDate(a.approved_at)}` : "";
  const what = a.decision === "REPLACE" ? "Our wording, approved" : a.decision === "NO_POSITION"
    ? "No position, approved" : "Approved";
  return `${what}${by}${when}`;
}

/** Line 2 of a clause in the list: what it needs, or what was done (two lines, never merged). */
export function clauseLine(clause: TemplateClause, check: TemplateCheck | null): string {
  const fails = failingOn(clause.clause_key, check)
    .sort((a, b) => Number(unchecked(a)) - Number(unchecked(b)));
  const why = fails.length ? `${shortWhy(fails[0]!)}${fails.length > 1 ? `, and ${fails.length - 1} more` : ""}` : "";
  if (approved(clause)) return why ? `Approved, still ${why.charAt(0).toLowerCase()}${why.slice(1)}` : approvedLine(clause.approval);
  if (why) return why;
  if (clause.flags?.length) return `Check this clause: ${flagWords(clause.flags[0]!)}`;
  return "Not approved yet";
}

export const ENGINE_WORDS: Record<string, string> = {
  DEVIATION: "Differs from our standard",
  CONFLICT: "Says it more than once, differently",
  UNABLE_TO_EVALUATE: "Could not be checked against it",
  MISSING: "Not in this template",
};
export const engineWords = (c: string) => ENGINE_WORDS[c] ?? c;

/** A gate problem in plain words, with the clause it concerns when it names one. */
export function problemWords(problem: string, clauses: TemplateClause[],
                             check: TemplateCheck | null): { text: string; clauseKey?: string } {
  const [head = "", ...rest] = problem.split(": ");
  const tail = rest.join(": ");
  if (head === "CLAUSE_NOT_APPROVED") {
    const key = tail.split("@")[0]!;
    const clause = clauses.find((c) => c.clause_key === key);
    return { text: `${clause ? displayTitle(clause.title) : key}: not approved yet`, clauseKey: key };
  }
  if (head === "NOT_MATCH") {
    const code = tail.split(" is ")[0]!;
    const standard = check?.standards.find((s) => s.code === code);
    return { text: `${engineWords(tail.split(" is ")[1] ?? "")}: ${standard?.description ?? code}`,
             ...(standard && placed(standard) ? { clauseKey: standard.clause_keys[0] } : {}) };
  }
  if (head === "TEMPLATE_NOT_APPROVED") return { text: "Every clause must be approved first" };
  if (head.startsWith("PREFLIGHT")) {
    // a term "used in quotes and never defined": the clause that uses it is where to fix it
    const term = /\u201c([^\u201d]+)\u201d/.exec(tail)?.[1];
    const at = term ? clauses.find((c) => plainText(c.body).includes(`\u201c${term}\u201d`)) : undefined;
    return { text: tail, ...(at ? { clauseKey: at.clause_key } : {}) };
  }
  return { text: tail || head };
}

/** Why a "replace" or "no position" cannot be recorded yet, or null — the server refuses
 *  both without a reason (`library.decide`), so the page says so before sending. */
export function actionProblem(mode: "replace" | "no-position", text: string, reason: string): string | null {
  if (mode === "replace" && !text.trim()) return "Write our wording first.";
  if (!reason.trim()) return "Give a reason — it is kept with this clause\u2019s approval.";
  return null;
}

/** ``{var}`` · ``{xref:KEY}`` · ``{term:Name}`` — the same pattern the server fills. */
const SLOT = /\{(?:(xref|term):)?([A-Za-z_][\w .-]*)\}/g;

export type Run = { text: string } | { field: string } | { xref: string } | { term: string };

export function runs(text: string): Run[] {
  const out: Run[] = [];
  let last = 0;
  for (const m of text.matchAll(SLOT)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    const name = m[2]!;
    out.push(m[1] === "xref" ? { xref: name } : m[1] === "term" ? { term: name } : { field: name });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

/** "party_two_name" → "Party two name" — a fill-in field named in words. */
export function fieldLabel(key: string): string {
  const words = key.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Every clause's number and every keyed sub-clause's ("4.2"), as the renderer numbers
 *  them in pin order — what a ``{xref:KEY}`` slot will read. */
export function clauseNumbers(clauses: TemplateClause[]): Map<string, string> {
  const out = new Map<string, string>();
  const walk = (blocks: Block[], prefix: string) => {
    let n = 0;
    for (const b of blocks) {
      if (b.kind !== "sub") continue;
      n += 1;
      const number = `${prefix}.${n}`;
      if (b.key) out.set(b.key, number);
      walk(b.body ?? [], number);
    }
  };
  clauses.forEach((c, i) => { out.set(c.clause_key, String(i + 1)); walk(c.body, String(i + 1)); });
  return out;
}

/** A gate problem list in plain words: a model problem names several clauses in one
 *  string ("CLAUSE_A@2: uses …; CLAUSE_C@2: …") — one line each, the clause by its title. */
export function problemLines(problems: string[], clauses: TemplateClause[],
                             check: TemplateCheck | null): { text: string; clauseKey?: string }[] {
  return problems.flatMap((p) => {
    if (!p.startsWith("MODEL: ")) return [problemWords(p, clauses, check)];
    return p.slice(7).split("; ").map((part) => {
      const m = /^([\w.]+)@\d+: (.*)$/.exec(part);
      const clause = m ? clauses.find((c) => c.clause_key === m[1]) : undefined;
      return clause ? { text: `${displayTitle(clause.title)}: ${m![2]}`, clauseKey: clause.clause_key } : { text: part };
    });
  });
}

/** The clause as plain paragraphs, blank-line separated — what the server's "replace"
 *  splits on. Numbered sub-clauses keep their words; the numbering is the renderer's. */
export function plainText(body: Block[]): string {
  const out: string[] = [];
  const walk = (blocks: Block[]) => {
    for (const b of blocks) {
      if (b.kind === "list") out.push(...(b.items ?? []));
      else if (b.kind === "table") out.push(...[b.header ?? [], ...(b.rows ?? [])].map((r) => r.join(" | ")));
      else if (b.text) out.push(b.kind === "definition" && b.term ? `\u201c${b.term}\u201d ${b.text}` : b.text);
      if (b.body?.length) walk(b.body);
    }
  };
  walk(body);
  return out.join("\n\n");
}


/** ``{xref:KEY}`` → ``{clause 4.2}`` for the editor, so a cross-reference reads as one;
 *  `fromEditor` turns it back before the server reads it (it renumbers itself). */
export function toEditor(wording: string, numbers: Map<string, string>): string {
  return wording.replace(/\{xref:([\w.-]+)\}/g, (m, key: string) => numbers.has(key) ? `{clause ${numbers.get(key)}}` : m);
}

export function fromEditor(text: string, numbers: Map<string, string>): string {
  const keyOf = new Map<string, string>();
  for (const [key, n] of numbers) if (!keyOf.has(n)) keyOf.set(n, key);
  return text.replace(/\{clause ([\d.]+)\}/g, (m, n: string) => keyOf.has(n) ? `{xref:${keyOf.get(n)}}` : m);
}

const STRUCTURE: [kind: string, one: string, many: string][] = [
  ["sub", "numbered sub-clause", "numbered sub-clauses"], ["list", "list item", "list items"],
  ["definition", "definition", "definitions"], ["table", "table row", "table rows"],
];

/** What recording this wording would change in the clause's form, against the reference
 *  outline — "3 numbered sub-clauses will become plain paragraphs". Empty: same form. */
export function structureChanges(before: OutlineLine[], after: OutlineLine[]): string[] {
  const count = (o: OutlineLine[], kind: string) => o.filter((x) => x.kind === kind).length;
  const plainGrew = count(after, "p") > count(before, "p");
  const out: string[] = [];
  for (const [kind, one, many] of STRUCTURE) {
    const d = count(after, kind) - count(before, kind);
    const word = Math.abs(d) === 1 ? one : many;
    if (d < 0) out.push(`${-d} ${word} will ${plainGrew ? "become plain paragraphs" : "be removed"}`);
    if (d > 0) out.push(`${d} new ${word}`);
  }
  return out;
}

/** Which lines of the new outline are new or changed, and which reference lines are gone. */
export function outlineDiff(before: OutlineLine[], after: OutlineLine[]): { changed: Set<number>; removed: string[] } {
  const norm = (t: string) => t.replace(/\s+/g, " ").trim();
  const was = new Set(before.map((x) => norm(x.text)));
  const now = new Set(after.map((x) => norm(x.text)));
  return {
    changed: new Set(after.flatMap((x, i) => was.has(norm(x.text)) ? [] : [i])),
    removed: before.map((x) => x.text).filter((t) => !now.has(norm(t))),
  };
}

/** The clauses whose version differs from the published template's (`published_version`). */
export const changedSincePublished = (clauses: TemplateClause[]) =>
  clauses.filter((c) => c.published_version !== undefined && c.version !== c.published_version);

/** `AM-302`: a published template's blank, filled outside LegalMind */
export const blankPath = (t: { template_key: string }) => `/templates/${encodeURIComponent(t.template_key)}/blank`;
/** `AM-302`: a draft's full text for management to approve */
export const reviewCopyPath = (t: { id: string }) => `/templates/${t.id}/review-copy`;
export const BLANK_NOTE = "For filling outside LegalMind. Upload what you send or sign, so we can check it.";

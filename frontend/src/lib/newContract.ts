/**
 * New contract (S5, `AM-282` r4 / `AM-283` / `AM-295`) — the page's pure logic: the shapes
 * the drafts API sends, which questions are asked, the answers as the server takes them,
 * and the plain words for what is still missing. Presentation only: the server validates
 * the answers and the engine reviews the created v1; nothing here decides whether a value
 * meets our standard (rule 18).
 */

import { brandLabel } from "./templates";

export type FieldClass = "M" | "O" | "C" | "AO";

export interface Question {
  key: string;
  label: string;
  type?: "text" | "date" | "int" | "bool" | "choice";
  group?: string;
  class?: FieldClass;
  help?: string;
  allowed?: (string | number)[];
  range?: [number | null, number | null];
  when?: unknown;
  locked_value?: unknown;
  /** what the field is (`model.role`): `counterparty_cin`, `our_signatory_name`, … */
  role?: string;
  /** the Client Profile field this answer is filled from (`AM-286` r1) */
  profile_field?: string;
}

export interface PublishedTemplate {
  id: string;
  template_key: string;
  version: number;
  doc_type: string;
  brand: string | null;
  title: string | null;
  questions: Question[];
  annexures: { key: string; title: string | null; when?: unknown }[];
}

export type Answers = Record<string, unknown>;
export interface FieldProblem { field: string; problem: string }

export interface Draft {
  id: string;
  version: number;
  template_version_id: string;
  template_status: string;
  counterparty_id: string | null;
  answers: Answers;
  problems: FieldProblem[];
  updated_at: string | null;
  expires_at: string;
  prefilled?: string[];
}

/** A run of the preview: plain text, a value a person gave (`var`), or a cross-reference. */
export type ModelRun = { t: string; var?: string } | { ref: string; num: string | null };
export interface ModelBlock {
  kind: string;
  number?: string;
  level?: number;
  term?: string;
  /** A sub-clause's run-in title ("Term:"), printed before its runs. */
  title?: string;
  title_style?: "bold";
  runs?: ModelRun[] | null;
  body?: ModelBlock[];
  items?: (ModelRun[] | null)[];
  rows?: (ModelRun[] | null)[][];
  alt?: string;
}
export interface ModelClause { clause_key: string; number: string; title: string; body: ModelBlock[] }
export interface ContractModel {
  title: string;
  preamble: ModelRun[] | null;
  parties: { role: string; name: ModelRun[] | null; office: ModelRun[] | null; cin: ModelRun[] | null }[];
  recitals: (ModelRun[] | null)[];
  body: ModelClause[];
  schedules: { key: string; title: string; clauses: ModelClause[] }[];
  execution: { rows: Record<string, ModelRun[] | null>[]; seal: boolean; witness: boolean };
}
export interface DraftPreview { model: ContractModel | null; missing: string[]; problems: FieldProblem[] }

/** Before Create: the points our review will send to Legal (`GET /drafts/{id}/check`). */
export interface DraftCheck {
  ready: boolean;
  version?: number;
  points: { code: string; name: string; classification: string }[];
}

export interface Created { contract_id: string; document_version_id: string; review_id: string | null; model_hash: string }

export const DOC_TYPES = [
  { id: "NDA", name: "NDA", long: "Non-disclosure agreement" },
  { id: "MSA", name: "MSA", long: "Master services agreement" },
] as const;
export const BRANDS = ["LEAPSWITCH", "CLOUDPE"] as const;

/** The Constitution's own words for the one pair that never has a template (`AM-287` r2). */
export const NO_CLOUDPE_MSA =
  "No CloudPe MSA; CloudPe services are governed by the published CloudPe Terms of Service.";

/** Why a type and brand cannot be made here, in words — or null when a published template exists. */
export function unavailable(docType: string, brand: string, published: PublishedTemplate[]): string | null {
  if (docType === "MSA" && brand === "CLOUDPE") return NO_CLOUDPE_MSA;
  if (published.some((t) => t.doc_type === docType && t.brand === brand)) return null;
  return `Our ${brandLabel(brand)} ${docType} template is being approved by Legal.`;
}

// ---------------------------------------------------------------- conditions
const COMPARE: Record<string, (a: unknown, b: unknown) => boolean> = {
  "==": (a, b) => a === b, "!=": (a, b) => a !== b,
  "<": (a, b) => (a as number) < (b as number), ">": (a, b) => (a as number) > (b as number),
  "<=": (a, b) => (a as number) <= (b as number), ">=": (a, b) => (a as number) >= (b as number),
  in: (a, b) => (Array.isArray(b) || typeof b === "string") && (b as unknown[]).includes(a as never),
};

/** The server's condition language (`drafting/conditions.py`), read the same way: a
 *  missing variable is null, so a comparison with it is simply false. An unknown
 *  operator shows the question (the server is the one that refuses it). */
export function evaluate(expr: unknown, values: Answers): unknown {
  if (Array.isArray(expr)) return expr.map((e) => evaluate(e, values));
  if (!expr || typeof expr !== "object") return expr;
  const [op, raw] = Object.entries(expr as Record<string, unknown>)[0] ?? [];
  if (op === "var") return values[raw as string] ?? null;
  const args = Array.isArray(raw) ? raw : [raw];
  if (op === "and") return args.every((a) => Boolean(evaluate(a, values)));
  if (op === "or") return args.some((a) => Boolean(evaluate(a, values)));
  if (op === "not" || op === "!") return !evaluate(args[0], values);
  const compare = op ? COMPARE[op] : undefined;
  if (compare && args.length === 2) {
    const left = evaluate(args[0], values);
    const right = evaluate(args[1], values);
    return left !== null && right !== null && compare(left, right);
  }
  return true;
}

export const locked = (q: Question) => q.locked_value !== undefined;
export const required = (q: Question) => (q.class ?? "M") !== "O";

/** The questions asked now: a conditional one only while its condition holds. */
export function visibleQuestions(questions: Question[], answers: Answers): Question[] {
  return questions.filter((q) => q.when === undefined || Boolean(evaluate(q.when, answers)));
}

/** The client first, then the deal, our side last; any other group in the template's order. */
export const GROUP_ORDER = ["Client", "Deal", "Our company"];
export const OURS = "Our company";

export function groups(questions: Question[], answers: Answers): { name: string; questions: Question[] }[] {
  const out: { name: string; questions: Question[] }[] = [];
  for (const q of visibleQuestions(questions, answers)) {
    const name = q.group ?? "Details";
    const group = out.find((g) => g.name === name) ?? out[out.push({ name, questions: [] }) - 1]!;
    group.questions.push(q);
  }
  const rank = (n: string) => { const i = GROUP_ORDER.indexOf(n); return i < 0 ? (n === OURS ? 99 : 1.5) : i; };
  return out.sort((a, b) => rank(a.name) - rank(b.name));
}

// ---------------------------------------------------------------- dates, as India writes them
const ISO = /^\d{4}-\d{2}-\d{2}$/;
/** "10/11/2026" (day, month, year; `/`, `-` or `.`) or an ISO date → ISO, else null. */
export function parseDate(text: string): string | null {
  const t = text.trim();
  const m = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(t);
  const [y, mo, d] = m ? [m[3]!, m[2]!, m[1]!] : ISO.test(t) ? t.split("-") as [string, string, string] : [];
  if (!y) return null;
  const date = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  if (date.getUTCFullYear() !== Number(y) || date.getUTCMonth() !== Number(mo) - 1 || date.getUTCDate() !== Number(d)) return null;
  return date.toISOString().slice(0, 10);
}
/** ISO → "10/11/2026", the way the form shows it back. */
export const dateText = (iso: string) => (ISO.test(iso) ? iso.split("-").reverse().join("/") : iso);

const empty = (v: unknown) => v === undefined || v === null || (typeof v === "string" && !v.trim());
/** An answer the contract can use: a date only once it reads as one. */
export const answered = (q: Question | undefined, v: unknown) =>
  !empty(v) && !(q?.type === "date" && !(typeof v === "string" && ISO.test(v)));

/** The answers as the server takes them: only questions asked now, never a fixed one,
 *  nothing empty, a whole number as a number. */
export function toAnswers(questions: Question[], local: Answers): Answers {
  const out: Answers = {};
  for (const q of visibleQuestions(questions, local)) {
    const value = local[q.key];
    if (locked(q) || !answered(q, value)) continue;
    out[q.key] = q.type === "int" && typeof value === "string" && /^-?\d+$/.test(value.trim())
      ? Number(value) : value;
  }
  return out;
}

/** Required questions asked now and not answered — what "Still to fill in" lists first. */
export function unanswered(questions: Question[], local: Answers): Question[] {
  return visibleQuestions(questions, local).filter((q) => required(q) && !locked(q) && !answered(q, local[q.key]));
}

/** "between 1 and 12" — a number's range, said beside it. */
export function rangeWords(q: Question): string | null {
  const [lo, hi] = q.range ?? [null, null];
  if (lo != null && hi != null) return `Between ${lo} and ${hi}`;
  if (lo != null) return `${lo} or more`;
  if (hi != null) return `Up to ${hi}`;
  return null;
}

/** A number outside the template's range, said beside the field. The server refuses it
 *  (`model.validate`), so the words say what to do — never that it was accepted. */
export function outsideRange(q: Question, value: unknown): string | null {
  if (q.type !== "int" || empty(value)) return null;
  const n = Number(value);
  const [lo, hi] = q.range ?? [null, null];
  if (!Number.isInteger(n)) return "Give a whole number.";
  if ((lo != null && n < lo) || (hi != null && n > hi)) {
    return `Our template allows a number ${rangeWords(q)!.toLowerCase()}. A different number needs Legal: ask them, or upload the contract for review instead.`;
  }
  return null;
}

/** What the early check found, in the contract's terms (the engine's classification). */
const CHECK_WORDS: Record<string, string> = {
  MISSING: "not in this contract",
  DEVIATION: "differs from our standard",
  CONFLICT: "says it twice, differently",
  UNABLE_TO_EVALUATE: "could not be checked",
};
export const checkWords = (c: string) => CHECK_WORDS[c] ?? "needs a decision";

/** The value our side of the contract shows (the client's profile, by field). */
export function profileValue(client: Record<string, unknown> | null, q: Question): string | null {
  if (!client || !q.profile_field) return null;
  const v = client[q.profile_field] ?? (q.profile_field === "legal_name" ? client.name : undefined);
  return typeof v === "string" && v.trim() ? v : null;
}

/** A value as the contract prints it (`model._display`): a date in words, yes or no. */
export function display(q: Question | undefined, value: unknown): string {
  if (q?.type === "date" && typeof value === "string" && ISO.test(value)) {
    const d = new Date(`${value}T00:00:00Z`);
    return `${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "long", timeZone: "UTC" })} ${d.getUTCFullYear()}`;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

/** A server problem in plain words: the question by its label, else our own rendering's. */
export function problemWords(p: FieldProblem, questions: Question[]): { text: string; key?: string } {
  const q = questions.find((x) => x.key === p.field);
  if (q) return { text: `${q.label} ${p.problem}`, key: q.key };
  if (p.field.startsWith("preflight")) {
    return { text: `Our template could not be filled in (${p.problem}). Tell Legal — the template needs fixing.` };
  }
  return { text: `${p.field} ${p.problem}` };
}

// ---------------------------------------------------------------- the client's legal details
/** `AM-286` r1 — typed by a person, each optional except the name. */
export const CLIENT_FIELDS: { key: string; label: string; help?: string; wide?: boolean; area?: boolean; first?: boolean }[] = [
  { key: "name", label: "Company name", first: true, wide: true },
  { key: "cin_or_llpin", label: "CIN or LLPIN", first: true, wide: true,
    help: "21 characters, for example U72900MH2010PTC123456, or an LLPIN such as AAB-1234" },
  { key: "legal_name", label: "Registered name", help: "As on the certificate of incorporation, if different" },
  { key: "entity_type", label: "Entity type", help: "For example, private limited company or LLP" },
  { key: "pan", label: "PAN", help: "10 characters, for example ABCDE1234F" },
  { key: "gstin", label: "GSTIN", help: "15 characters, for example 27ABCDE1234F1Z5" },
  { key: "registered_office", label: "Registered office", wide: true, area: true },
  { key: "notice_address", label: "Address for notices", wide: true, area: true },
  { key: "notice_email", label: "Email for notices" },
  { key: "signatory_name", label: "Who signs for them" },
  { key: "signatory_designation", label: "Their designation" },
  { key: "authority_reference", label: "Their authority to sign", wide: true,
    help: "For example, a board resolution or letter of authority, with its date" },
];

/** The API names a bad identifier by field only (49.5 r4: values are never echoed) —
 *  the shape it expects, in the API's own examples (`schemas._LEGAL_ID_SHAPES`). */
const SHAPES: Record<string, string> = {
  cin_or_llpin: "This is not a CIN (for example U72900MH2010PTC123456) or an LLPIN (for example AAB-1234).",
  pan: "This is not a PAN (for example ABCDE1234F).",
  gstin: "This is not a GSTIN (for example 27ABCDE1234F1Z5).",
};
export function clientFieldError(field: string): string {
  return SHAPES[field] ?? (field === "name" ? "Give the company's name." : "Check this field.");
}

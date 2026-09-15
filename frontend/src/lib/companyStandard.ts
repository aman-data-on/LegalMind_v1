/**
 * The Company Standard edit form's whole brain, as pure functions.
 *
 * WHY THE LOGIC LIVES HERE AND NOT IN THE COMPONENT. `vitest.config.ts` sets
 * `environment: "node"` and its own comment rejects adding a DOM library, so form
 * *behaviour* cannot be unit-tested. Everything that could silently corrupt the
 * organization's legal position — which keys are written, which are dropped, what
 * a blank field means — is therefore a pure function with a test, and the
 * component is left with nothing but wiring.
 *
 * ── The safety property ──────────────────────────────────────────────────────
 *
 *     toStandard(draft, original)  ->  { ...original, ...the fields the form owns }
 *
 * `original` is spread FIRST, at every level of nesting. Any key the form does not
 * model — `extraction.units`, `extraction.bases`, `extraction.exceptions`,
 * `general_scope`, `composite_phrases`, `_note` — survives byte-identical. This is
 * what makes a partial form safe to ship: the form can never delete a legal
 * position it does not display.
 *
 * ── Rule 21, and why a form does not violate it ──────────────────────────────
 *
 * The screen's header cites rule 21: a helpful-looking placeholder would become the
 * organization's legal position by accident. That stays in force. Rule 21 forbids
 * inventing legal *content*, not *structure* — so every control here renders EMPTY
 * when the stored value is absent, with no preselected option, no example and no
 * suggested value. `draftFromStandard({}, …)` returning an all-empty draft is
 * asserted by a test, so "the empty form suggests nothing" is mechanical rather
 * than a convention someone can drift away from.
 *
 * ── Blank means absent, never "" ─────────────────────────────────────────────
 *
 * A blank field OMITS its key. `preferred: ""` would defeat the evaluator's
 * `standard.get(PREFERRED) is None` check (`evaluation/numeric.py` `standard_side`)
 * and make the standard report a value nobody set. Clearing a previously-filled
 * field therefore DELETES the key — chosen over "blank means leave alone", which
 * would make deletion impossible without dropping back to raw JSON.
 */

import { DOCUMENT_TYPES } from "@/lib/documentTypes";

/**
 * The seven values `constitution.basis` may take — a presentation copy of `BASES`
 * in `backend/legalmind/evaluation/constitution_block.py`, which validates every
 * value server-side. `backend/tests/test_frontend_vocabulary.py` asserts the two
 * lists are identical, so a drift on either side fails CI.
 */
export const CONSTITUTION_BASES: ReadonlyArray<{ code: string; label: string }> = [
  { code: "STAKEHOLDER_CONFIRMED", label: "Stakeholder confirmed / counsel validation point" },
  { code: "APPLICABLE_LAW", label: "Applicable law" },
  { code: "COMPANY_APPROVED", label: "Company-approved" },
  { code: "LEGALMIND_RULE", label: "LegalMind practice-based rule" },
  { code: "NOT_ADOPTED", label: "Not currently adopted" },
  { code: "DOCUMENT_ONLY", label: "No Constitution position — source is a LeapSwitch clause" },
  { code: "RETIRED", label: "Retired — withdrawn from active review" },
];

/** The two bases that may stand without a Constitution section. */
const SECTION_OPTIONAL_BASES = ["DOCUMENT_ONLY", "RETIRED"];

/** Mirrors `_SECTION` in `constitution_block.py` exactly. */
const SECTION_PATTERN = /^\d{1,2}(\.\d{1,2}[a-z]?)?$/;

/**
 * The ONLY unit conversions the engine will ever perform (`AM-62`,
 * `DEFINITIONAL_UNIT_FACTORS` in `backend/legalmind/evaluation/numeric.py`). Each
 * is an identity of measure, not a legal equivalence.
 *
 * DAYS<->MONTHS is deliberately absent and can never be declared into existence
 * (rule 7): a month is not thirty days by definition. Offering it in the form
 * would let someone declare a pair the engine silently refuses, so the form offers
 * exactly these four and nothing else.
 */
export const DEFINITIONAL_UNIT_PAIRS: ReadonlyArray<{ from: string; to: string }> = [
  { from: "YEARS", to: "MONTHS" },
  { from: "MONTHS", to: "YEARS" },
  { from: "WEEKS", to: "DAYS" },
  { from: "DAYS", to: "WEEKS" },
];

/** `applicability`, as the server reads it. Blank is a real, common state — 15 of
 *  the 40 ratified standards omit the key entirely. */
export const APPLICABILITY_OPTIONS: ReadonlyArray<{ code: string; label: string }> = [
  { code: "REQUIRED", label: "Required" },
  { code: "OPTIONAL", label: "Optional" },
];

export const PRESENCE_OPTIONS: ReadonlyArray<{ code: string; label: string }> = [
  { code: "PRESENT", label: "Must be present" },
  { code: "ABSENT", label: "Must be absent" },
];

/** Which controls a standard shows. Derived from the version's evaluator, never
 *  guessed from the values — an empty numeric standard is still numeric. */
export type EvaluatorKind = "NUMERIC_COMPARISON" | "PRESENCE";

/**
 * The editable shape: flat, and every value a string or a list of strings, so one
 * control maps to one key and the component holds no nested state. Same idiom as
 * `Draft` in `components/clients/ClientForm.tsx`.
 */
export interface StandardDraft {
  document_type: string;
  scope_key: string;
  applicability: string;
  constitution_version: string;
  constitution_section: string;
  constitution_topic: string;
  constitution_basis: string;
  constitution_expected_when: string[];
  /** numeric only */
  preferred: string;
  unit: string;
  basis: string;
  cap_phrases: string[];
  unlimited_phrases: string[];
  /** presence only */
  expected_presence: string;
  /** advanced */
  unit_conversions: string[];
  not_applicable_to: string[];
}

export const EMPTY_DRAFT: StandardDraft = {
  document_type: "",
  scope_key: "",
  applicability: "",
  constitution_version: "",
  constitution_section: "",
  constitution_topic: "",
  constitution_basis: "",
  constitution_expected_when: [],
  preferred: "",
  unit: "",
  basis: "",
  cap_phrases: [],
  unlimited_phrases: [],
  expected_presence: "",
  unit_conversions: [],
  not_applicable_to: [],
};

/** `{from_unit, to_unit}` as one string, for a checkbox's value. */
export function unitPairKey(pair: { from: string; to: string }): string {
  return `${pair.from}>${pair.to}`;
}

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Dict)
    : {};
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function text(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return "";
}

/** Read a stored standard into the flat draft. Anything absent reads as "" or []. */
export function draftFromStandard(standard: Dict | null | undefined): StandardDraft {
  const stored = asDict(standard);
  const constitution = asDict(stored.constitution);
  const expectedWhen = asDict(constitution.expected_when);
  const extraction = asDict(stored.extraction);
  const conversions = Array.isArray(stored.unit_conversions) ? stored.unit_conversions : [];

  return {
    document_type: text(stored.document_type),
    scope_key: text(stored.scope_key),
    applicability: text(stored.applicability),
    constitution_version: text(constitution.version),
    constitution_section: text(constitution.section),
    constitution_topic: text(constitution.topic),
    constitution_basis: text(constitution.basis),
    constitution_expected_when: asStringList(expectedWhen.confirmed_any),
    preferred: text(stored.preferred),
    unit: text(stored.unit),
    basis: text(stored.basis),
    cap_phrases: asStringList(extraction.cap_phrases),
    unlimited_phrases: asStringList(extraction.unlimited_phrases),
    expected_presence: text(stored.expected_presence),
    unit_conversions: conversions
      .map((rule) => asDict(rule))
      .filter((rule) => typeof rule.from_unit === "string" && typeof rule.to_unit === "string")
      .map((rule) => `${String(rule.from_unit)}>${String(rule.to_unit)}`),
    not_applicable_to: asStringList(stored.not_applicable_to),
  };
}

/** Write `value` under `key`, or delete the key when the value is blank. */
function put(target: Dict, key: string, value: string | string[] | number | undefined): void {
  const blank =
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "number" && Number.isNaN(value));
  if (blank) delete target[key];
  else target[key] = value;
}

/** Drop a nested object from the parent when editing emptied it completely. */
function putObject(target: Dict, key: string, value: Dict): void {
  if (Object.keys(value).length === 0) delete target[key];
  else target[key] = value;
}

/**
 * The draft, merged back onto the stored standard.
 *
 * `original` is spread first at every level, so keys the form does not model
 * survive untouched. See the safety property at the top of this file.
 */
export function toStandard(draft: StandardDraft, original: Dict | null | undefined): Dict {
  const stored = asDict(original);
  const out: Dict = { ...stored };

  put(out, "document_type", draft.document_type.trim());
  put(out, "scope_key", draft.scope_key.trim());
  put(out, "applicability", draft.applicability.trim());
  put(out, "expected_presence", draft.expected_presence.trim());
  put(out, "unit", draft.unit.trim());
  put(out, "basis", draft.basis.trim());
  put(out, "not_applicable_to", draft.not_applicable_to);

  // `preferred` is the one number on the form. A value that is not a number is
  // left out entirely rather than written as NaN or as a string — the evaluator
  // reads it arithmetically, so a string there is worse than an absent key.
  const preferred = draft.preferred.trim();
  put(out, "preferred", preferred === "" ? undefined : Number(preferred));

  const constitution = asDict(stored.constitution);
  const nextConstitution: Dict = { ...constitution };
  put(nextConstitution, "version", draft.constitution_version.trim());
  put(nextConstitution, "section", draft.constitution_section.trim());
  put(nextConstitution, "topic", draft.constitution_topic.trim());
  put(nextConstitution, "basis", draft.constitution_basis.trim());
  const expectedWhen: Dict = { ...asDict(constitution.expected_when) };
  put(expectedWhen, "confirmed_any", draft.constitution_expected_when);
  putObject(nextConstitution, "expected_when", expectedWhen);
  putObject(out, "constitution", nextConstitution);

  const nextExtraction: Dict = { ...asDict(stored.extraction) };
  put(nextExtraction, "cap_phrases", draft.cap_phrases);
  put(nextExtraction, "unlimited_phrases", draft.unlimited_phrases);
  putObject(out, "extraction", nextExtraction);

  put(
    out,
    "unit_conversions",
    draft.unit_conversions.length === 0
      ? undefined
      : (draft.unit_conversions
          .map((key) => {
            const [from, to] = key.split(">");
            return { from_unit: from, to_unit: to };
          }) as unknown as string[]),
  );

  return out;
}

/**
 * Field key -> message, empty when the draft is valid.
 *
 * This MIRRORS the server rather than inventing policy: `constitution_block_error`
 * in `backend/legalmind/evaluation/constitution_block.py` is the authority, and
 * every rule below is one of its refusals moved earlier in time. The point is to
 * make the publish refusal — which today arrives days later as
 * "configuration is incomplete: …" — unreachable by accident.
 *
 * One check has no server counterpart: the numeric `basis` and `unit` must key
 * into `extraction.bases` / `extraction.units`, because a basis the extractor
 * cannot recognise silently fails closed on every document.
 */
export function validateStandard(
  draft: StandardDraft,
  original: Dict | null | undefined,
  evaluator: EvaluatorKind,
): Record<string, string> {
  const errors: Record<string, string> = {};

  // The server refuses a standard with no document_type outright.
  if (!draft.document_type.trim()) {
    errors.document_type = "Required — the server refuses a standard that does not declare one.";
  } else if (!DOCUMENT_TYPES.some((t) => t.code === draft.document_type)) {
    errors.document_type = `${draft.document_type} is not one of the ten document types.`;
  }

  if (!draft.scope_key.trim()) {
    errors.scope_key = "Required — the scope key decides what this position is compared against.";
  }

  if (draft.applicability && !APPLICABILITY_OPTIONS.some((o) => o.code === draft.applicability)) {
    errors.applicability = "Must be Required or Optional, or left unset.";
  }

  // --- the constitution block, mirroring constitution_block_error ---
  const section = draft.constitution_section.trim();
  const basis = draft.constitution_basis.trim();
  const hasBlock =
    section || basis || draft.constitution_topic.trim() || draft.constitution_version.trim();

  if (hasBlock) {
    if (section && !SECTION_PATTERN.test(section)) {
      errors.constitution_section =
        `"${section}" is not a Constitution section reference — ` +
        "one or two digits, optionally .digits and one letter, such as 9, 17.2 or 31.6a.";
    }
    if (!draft.constitution_topic.trim()) {
      errors.constitution_topic = "Required — it names the Appendix B clause category.";
    }
    if (!basis) {
      errors.constitution_basis = "Required — it records where this position comes from.";
    } else if (!CONSTITUTION_BASES.some((b) => b.code === basis)) {
      errors.constitution_basis = `${basis} is not one of the seven recorded bases.`;
    } else if (!section && !SECTION_OPTIONAL_BASES.includes(basis)) {
      errors.constitution_section =
        "Required for this basis — only a document-only or retired standard may omit it.";
    }
  }

  // --- the numeric half ---
  if (evaluator === "NUMERIC_COMPARISON") {
    const preferred = draft.preferred.trim();
    if (preferred !== "" && !Number.isFinite(Number(preferred))) {
      errors.preferred = "Must be a number.";
    }
    const extraction = asDict(asDict(original).extraction);
    const bases = asDict(extraction.bases);
    const units = asDict(extraction.units);
    if (draft.basis.trim() && Object.keys(bases).length > 0 && !(draft.basis.trim() in bases)) {
      errors.basis =
        `"${draft.basis.trim()}" is not one of the bases this standard can recognise ` +
        `(${Object.keys(bases).join(", ")}), so every document would fail closed against it.`;
    }
    if (draft.unit.trim() && Object.keys(units).length > 0 && !(draft.unit.trim() in units)) {
      errors.unit =
        `"${draft.unit.trim()}" is not one of the units this standard can recognise ` +
        `(${Object.keys(units).join(", ")}).`;
    }
  }

  if (evaluator === "PRESENCE" && draft.expected_presence &&
      !PRESENCE_OPTIONS.some((o) => o.code === draft.expected_presence)) {
    errors.expected_presence = "Must be Present or Absent.";
  }

  // The engine refuses any pair outside the four definitional ones (AM-62), so a
  // declared pair it does not recognise would be silently inert.
  const allowed = new Set(DEFINITIONAL_UNIT_PAIRS.map(unitPairKey));
  const rejected = draft.unit_conversions.filter((key) => !allowed.has(key));
  if (rejected.length > 0) {
    errors.unit_conversions =
      `${rejected.join(", ")} is not a definitional conversion — the engine would refuse it.`;
  }

  return errors;
}

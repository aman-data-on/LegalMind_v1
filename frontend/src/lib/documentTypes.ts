/**
 * Locked Step 6's Document Type vocabulary — presentation copy of
 * `backend/legalmind/domain/document_types.py`, which is the source of truth
 * and validates every value server-side. `backend/tests/test_frontend_vocabulary.py`
 * asserts the two lists are identical, so a drift on either side fails CI.
 *
 * Owner ruling Q9 (2026-08-19): the type is DECLARED by the uploader, never
 * inferred — analysis refuses an undeclared document rather than guessing which
 * baseline to compare it against. The intake screen therefore makes this the one
 * prominent required choice.
 */
export const DOCUMENT_TYPES: ReadonlyArray<{ code: string; label: string }> = [
  { code: "MSA", label: "Master Services Agreement" },
  { code: "NDA", label: "Non-Disclosure Agreement" },
  { code: "TOS", label: "Terms of Service" },
  { code: "SLA", label: "Service Level Agreement" },
  { code: "DPA", label: "Data Processing Agreement" },
  { code: "AUP", label: "Acceptable Use Policy" },
  { code: "PRIVACY_POLICY", label: "Privacy Policy" },
  { code: "ORDER_FORM", label: "Order Form" },
  { code: "AMENDMENT", label: "Amendment / Addendum" },
  { code: "OTHER", label: "Other" },
];

export function documentTypeLabel(code: string | null | undefined): string {
  return DOCUMENT_TYPES.find((t) => t.code === code)?.label ?? code ?? "Type not declared";
}

/**
 * The type as a CHIP — short enough for a table column, and still a word.
 *
 * The raw Step 6 code is the wrong thing to render: `ORDER_FORM` and
 * `PRIVACY_POLICY` put an underscore in front of a reader, and the owner's
 * instruction is explicit that the chip should read "MSA / NDA / SLA /
 * Amendment / PO / Other". The initialisms stay initialisms because that is
 * what people call them; the multi-word codes become words.
 *
 * The full label is still available for the chip's `title` and for a select,
 * so nothing is lost — this is the short form, not a replacement vocabulary.
 * The CODE remains the only thing sent to or from the server.
 */
const TYPE_CHIP: Record<string, string> = {
  PRIVACY_POLICY: "Privacy",
  ORDER_FORM: "Order form",
  AMENDMENT: "Amendment",
};

export function documentTypeChip(code: string | null | undefined): string | null {
  if (!code) return null;
  return TYPE_CHIP[code] ?? code;
}

/**
 * A name for the contract, derived from the file the user chose — an editable
 * DEFAULT, never a demand (2026-08-31 UX correction): the filename already
 * carries the natural label, and identity/audit live on ids and the preserved
 * original_filename, not on this display name.
 */
export function nameFromFilename(filename: string): string {
  const stem = filename.replace(/\.[A-Za-z0-9]{1,5}$/, "");
  const tidied = stem.replace(/[_\-.]+/g, " ").replace(/\s+/g, " ").trim();
  return tidied || filename;
}

/** Filename tokens that plainly suggest a Step 6 type. PRESENTATION ONLY: the
 *  hint is shown beside the (empty) select and applied only by the user's own
 *  click — the declaration stays a human act (owner Q9), nothing is inferred
 *  into the record. */
const TYPE_TOKENS: ReadonlyArray<[string, string]> = [
  ["msa", "MSA"], ["nda", "NDA"], ["tos", "TOS"], ["sla", "SLA"],
  ["dpa", "DPA"], ["aup", "AUP"], ["privacy", "PRIVACY_POLICY"],
  ["order", "ORDER_FORM"], ["amendment", "AMENDMENT"], ["addendum", "AMENDMENT"],
];

export function typeHintFromFilename(filename: string): string | null {
  const tokens = filename.toLowerCase().split(/[^a-z0-9]+/);
  for (const [token, code] of TYPE_TOKENS) {
    if (tokens.includes(token)) return code;
  }
  return null;
}

/**
 * `§` in front of a section number — once, never twice.
 *
 * `Evidence.section_number` carries the document's own numbering, and real
 * documents supply it both ways: "17.2" from one parser, "§17.2" from another.
 * Prepending unconditionally rendered "§§1" on every clause of an MSA whose
 * headings already carry the sign.
 *
 * It lives here, shared, because the first fix patched two of the four callers
 * and the other two kept printing "§§" — a rule copied into every caller is a
 * rule that gets fixed in some of them.
 */
export function sectionRef(sectionNumber: string | null | undefined): string | null {
  // The number exactly as the document states it (owner, 2026-09-10: "DO NOT
  // add the § symbol… the document itself is the source of truth"). A sign the
  // document carries stays; none is ever added.
  const trimmed = (sectionNumber ?? "").trim();
  return trimmed || null;
}

/**
 * Step 6's second axis — "A document **can** be classified by source:
 * Organization / Counterparty" (all_lock.md:535). Optional, and declared by the
 * uploader, never inferred (the same reasoning as Q9 for Type). Presentation
 * copy of `DOCUMENT_SOURCES` in the backend's `document_types.py`;
 * `test_frontend_vocabulary.py` asserts the two agree. Keyed `value`, not
 * `code`, so the Step 6 TYPE sync regex never picks these up by mistake.
 */
export const DOCUMENT_SOURCES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "ORGANIZATION", label: "Organization — our document" },
  { value: "COUNTERPARTY", label: "Counterparty — their document" },
];

export function documentSourceLabel(value: string | null | undefined): string {
  return DOCUMENT_SOURCES.find((s) => s.value === value)?.label ?? value ?? "Source not declared";
}

/**
 * The source axis in a reviewer's words, for a chip (2026-09-06). The manager's
 * question is "whose paper is this?" — "Organization"/"Counterparty" answers it
 * in the vocabulary Step 6 uses, but not in the words a reviewer thinks in.
 */
export function documentSourceChip(value: string | null | undefined): string | null {
  if (value === "ORGANIZATION") return "Our document";
  if (value === "COUNTERPARTY") return "Their document";
  return null;
}

/**
 * What a version IS in the negotiation — the owner's three concepts
 * (2026-09-10). Presentation copy of `VERSION_ROLES` in the backend's
 * `domain/client_profile.py`; `test_frontend_vocabulary.py` asserts the two
 * agree, so a drift on either side fails CI.
 *
 * Keyed `role`, not `code` or `value`, so neither of the two existing Step 6
 * sync regexes can pick these up by mistake — the same care `DOCUMENT_SOURCES`
 * took for the same reason.
 *
 * ⚠️ A THIRD axis, distinct from `DOCUMENT_SOURCES`. `source` answers "whose
 * paper is this?"; this answers "where in the negotiation is this?". The owner
 * named the confusion to avoid: a client's redline is NOT the signed copy, and
 * the signed copy is not thereby the client's paper. Declared by a human, never
 * inferred from the version number, the filename or the date.
 */
export const VERSION_ROLES: ReadonlyArray<{ role: string; label: string; hint: string }> = [
  { role: "COMPANY_DRAFT", label: "Company draft", hint: "What we sent" },
  { role: "CLIENT_MODIFIED", label: "Client modified", hint: "What came back" },
  { role: "FINAL_SIGNED", label: "Final signed", hint: "What was executed" },
];

/** The reader's word for a version role, or null when nobody declared one —
 *  null so a caller renders the version number alone rather than the word
 *  "Unknown", which reads as a checked fact. */
export function versionRoleLabel(role: string | null | undefined): string | null {
  return VERSION_ROLES.find((r) => r.role === role)?.label ?? null;
}

/** Which of the three status tones a version role wears. Green for the executed
 *  copy is the one place a role carries colour, and it is earned: "is this
 *  signed?" is the question the owner named first. The other two are neutral —
 *  a draft is not a warning. */
export function versionRoleTone(role: string | null | undefined): "ok" | "neutral" {
  return role === "FINAL_SIGNED" ? "ok" : "neutral";
}

/**
 * The three client relationship states, in a non-legal reader's words
 * (2026-09-10). Presentation copy of `CLIENT_STATUSES`; the same vocabulary
 * test pins it.
 *
 * ⚠️ NOT one of the five legal state axes and never rendered in their colours.
 * A client being INACTIVE says nothing about any document's classification,
 * rule outcome or decision — it is filing, and `DECISION_STATE_MODEL.md`'s rule
 * that no two axes share a visual channel applies here too.
 */
export const CLIENT_STATUSES: ReadonlyArray<{ state: string; label: string }> = [
  { state: "ACTIVE", label: "Active" },
  { state: "PROSPECTIVE", label: "Prospective" },
  { state: "INACTIVE", label: "Inactive" },
];

export function clientStatusLabel(state: string | null | undefined): string {
  return CLIENT_STATUSES.find((s) => s.state === state)?.label ?? state ?? "Active";
}

/**
 * A company's initials for its avatar block — at most two letters, from the
 * first two meaningful words.
 *
 * Legal suffixes are skipped: "ABC Technologies Pvt. Ltd." should read "AT",
 * not "AP", and a list where four companies all show "PL" identifies nothing.
 * Purely presentational — the full name is always beside it, and the avatar
 * carries `aria-hidden` because it adds no information a screen reader needs.
 */
const NAME_NOISE = new Set([
  "pvt", "pvt.", "private", "ltd", "ltd.", "limited", "llp", "inc", "inc.",
  "llc", "plc", "gmbh", "co", "co.", "corp", "corp.", "corporation", "the",
  "and", "&",
]);

export function companyInitials(name: string): string {
  const words = name
    .split(/[\s,]+/)
    .map((word) => word.trim())
    .filter((word) => word.length > 0 && !NAME_NOISE.has(word.toLowerCase()));
  // A purely numeric word is not an initial anyone recognises — a registration
  // number or a year would give "A1" where "AT" was wanted. Dropped only when
  // a letter-bearing word survives, so a name that is genuinely all digits
  // still produces something rather than "?".
  const lettered = words.filter((word) => /[A-Za-z]/.test(word));
  const source = lettered.length > 0 ? lettered
    : words.length > 0 ? words : [name.trim()];
  const letters = source
    .slice(0, 2)
    .map((word) => word.replace(/[^A-Za-z0-9]/g, "").charAt(0).toUpperCase())
    .filter(Boolean)
    .join("");
  return letters || "?";
}

/**
 * "Mumbai, Maharashtra, India" from whichever parts exist — and null when none
 * do, so the caller renders nothing rather than a row of stray commas.
 */
export function clientLocation(client: {
  city?: string; state_region?: string; country?: string;
}): string | null {
  const parts = [client.city, client.state_region, client.country].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

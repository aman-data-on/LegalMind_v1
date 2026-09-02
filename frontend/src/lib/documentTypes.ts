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
  const trimmed = (sectionNumber ?? "").trim();
  if (!trimmed) return null;
  return /^[§¶]/.test(trimmed) ? trimmed : `§${trimmed}`;
}

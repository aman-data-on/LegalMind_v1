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

/**
 * The execution record (CLM flow 5, `AM-292`): what the person recorded about stamp duty,
 * who signed and the signed copy. Every gate is the server's (`blockers`); nothing here
 * decides whether a contract may be marked signed, and no duty, article or rate is ever
 * worked out — the duty is text as typed (rules 7, 21).
 */

export type StampMethod = "E_STAMP" | "STAMP_PAPER" | "NOT_STAMPED";
export type Party = "OURS" | "CLIENT";

export interface Signatory {
  party: Party;
  name?: string | null;
  designation?: string | null;
  authority_kind?: "BOARD_RESOLUTION" | "AUTHORITY_LETTER" | null;
  authority_reference?: string | null;
  authority_date?: string | null;
  signed_on?: string | null;
  method?: "WET_INK" | "E_SIGN" | null;
}

export interface ExecutionFields {
  stamp_method?: StampMethod | null;
  stamp_reference?: string | null;
  stamp_state?: string | null;
  duty_paid?: string | null;
  stamped_on?: string | null;
  not_stamped_acknowledged?: boolean;
  signatories?: Signatory[];
  seal_used?: boolean | null;
  witnesses?: string[];
  signed_document_version_id?: string | null;
}

export interface ExecutionRecord extends Required<Pick<ExecutionFields, "signatories">> {
  version: number;
  /** `AM-298`: SIGNED_OUTSIDE when the contract was filed as already signed. */
  origin?: "IN_LEGALMIND" | "SIGNED_OUTSIDE";
  stamp_method: StampMethod | null;
  stamp_reference: string | null;
  stamp_state: string | null;
  duty_paid: string | null;
  stamped_on: string | null;
  not_stamped_acknowledged: boolean;
  seal_used: boolean | null;
  witnesses: string[];
  signed_document_version_id: string | null;
  differences_accepted: boolean;
  differences_reason: string | null;
  signed_at: string | null;
  recorded_at: string;
}

export interface SignedDifference {
  kind: "MODIFIED" | "ADDED" | "DELETED" | "MOVED" | "NEW_ANNEXURE";
  clause: { number: string | null; heading: string | null };
  page: number | null;
  agreed_text?: string | null;
  signed_text?: string | null;
}

export interface SignedComparison {
  status: "MATCHES" | "DIFFERS" | "NOT_COMPARED";
  reason: string | null;
  agreed: { document_version_id: string; version_number: number };
  signed: { document_version_id: string; version_number: number; file_hash?: string };
  differences: SignedDifference[];
}

export interface Blocker { code: string; message: string }

export interface ExecutionState {
  execution: ExecutionRecord | null;
  agreed?: { document_version_id: string; version_number: number } | null;
  decision?: string | null;
  open_points?: number;
  comparison: SignedComparison | null;
  blockers: Blocker[];
  signed: boolean;
  /** Filed as signed: false until the owner confirms the record (then it is final). */
  confirmed?: boolean;
  /** Declared Final signed before the signing step, with no signing record. */
  legacy?: boolean;
  can_accept_differences?: boolean;
  prefill?: { signatories: Signatory[] };
}

export const STAMP_METHODS: { value: StampMethod; label: string; hint: string }[] = [
  { value: "E_STAMP", label: "E-stamp certificate", hint: "Bought online, for example through SHCIL or the state's portal" },
  { value: "STAMP_PAPER", label: "Stamp paper", hint: "Printed on non-judicial stamp paper" },
  { value: "NOT_STAMPED", label: "Not stamped yet", hint: "It will be stamped later" },
];

export const AUTHORITY_KINDS = [
  { value: "BOARD_RESOLUTION", label: "Board resolution" },
  { value: "AUTHORITY_LETTER", label: "Authority letter" },
] as const;

export const SIGN_METHODS = [
  { value: "WET_INK", label: "Signed on paper" },
  { value: "E_SIGN", label: "E-signed" },
] as const;

export const PARTY_LABEL: Record<Party, string> = { OURS: "For us", CLIENT: "For the client" };

export const KIND_LABEL: Record<SignedDifference["kind"], string> = {
  MODIFIED: "Worded differently", ADDED: "Only in the signed copy", DELETED: "Missing from the signed copy",
  MOVED: "In another place", NEW_ANNEXURE: "An annexure only in the signed copy",
};

/** The two parties' rows, filled from what was recorded or the server's pre-fill. */
export function partyRows(rows: Signatory[] | undefined): Signatory[] {
  return (["OURS", "CLIENT"] as const).map((party) => ({ party, ...(rows ?? []).find((r) => r.party === party) }));
}

/** The stamp section is complete enough to show "Recorded" (the server decides for real). */
export function stampRecorded(f: ExecutionFields): boolean {
  if (f.stamp_method === "NOT_STAMPED") return !!f.not_stamped_acknowledged;
  return !!(f.stamp_method && f.stamp_reference && f.stamp_state && f.duty_paid);
}

export function signatoriesRecorded(rows: Signatory[] | undefined): boolean {
  return partyRows(rows).every((r) => !!(r.name && r.designation && r.authority_reference));
}

/** Which face the signing sheet shows (`AM-298`): a contract signed before the signing
 *  step with no record, one filed as signed and not yet confirmed (editable, optional),
 *  a final record, or the Mark signed form. */
export function signingView(state: ExecutionState): "legacy" | "filed" | "summary" | "form" {
  if (state.legacy) return "legacy";
  if (state.execution?.origin === "SIGNED_OUTSIDE" && state.confirmed === false) return "filed";
  return state.signed && state.execution ? "summary" : "form";
}

/** The record as the form's starting values. */
export function toFields(state: ExecutionState): ExecutionFields {
  const r = state.execution;
  if (!r) return { signatories: partyRows(state.prefill?.signatories), witnesses: [] };
  return {
    stamp_method: r.stamp_method, stamp_reference: r.stamp_reference, stamp_state: r.stamp_state,
    duty_paid: r.duty_paid, stamped_on: r.stamped_on, not_stamped_acknowledged: r.not_stamped_acknowledged,
    signatories: partyRows(r.signatories), seal_used: r.seal_used, witnesses: r.witnesses,
    signed_document_version_id: r.signed_document_version_id,
  };
}

/** Empty strings are not values: sent as null, so the server never stores "". */
export function cleaned(f: ExecutionFields): ExecutionFields {
  const blank = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
  return {
    ...f,
    stamp_reference: blank(f.stamp_reference), stamp_state: blank(f.stamp_state),
    duty_paid: blank(f.duty_paid), stamped_on: blank(f.stamped_on),
    witnesses: (f.witnesses ?? []).map((w) => w.trim()).filter(Boolean),
    signatories: partyRows(f.signatories).map((s) => ({
      ...s, name: blank(s.name), designation: blank(s.designation),
      authority_reference: blank(s.authority_reference), authority_date: blank(s.authority_date),
      signed_on: blank(s.signed_on),
    })),
  };
}

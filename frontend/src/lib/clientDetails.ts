/**
 * Batch 7 (AB-220): the shapes of `GET /drafts/{id}/client-details` — Legal's ten items
 * for an MSA/NDA, each the server's own state. Presentation only: nothing here decides
 * whether an item is present, a check passes or the contract may be created (rule 18).
 */

export type ItemStatus = "done" | "missing" | "not_needed" | "fix";

export interface ChecklistItem {
  n: number;
  key: string;
  status: ItemStatus;
  source: "deal" | "profile";
  /** a deal item: the question's key; a client item: the record's field */
  question?: string;
  profile_field?: string;
  value?: string;
  problem?: string;
}

export interface ReadValue { field: string; value: string; state: "fill" | "differs" | "same" }

export type Warning =
  | { code: "state_differs"; item: number; gstin_state: string; office_state: string }
  | { code: "state_unreadable"; item: number }
  | { code: "act_wording"; item: number; year: number }
  | { code: "name_differs"; certificate_name: string; profile_name: string };

export interface ClientChecklist {
  applies: boolean;
  ready: boolean;
  items: ChecklistItem[];
  warnings: Warning[];
  india?: boolean;
  /** the template's questions the card owns (read from the client record) */
  questions?: string[];
  reads?: ReadValue[];
  trade_name?: string | null;
  verify_needed?: boolean;
  /** R2-5: whether the client record holds a legal name (the tick needs one) */
  legal_name_recorded?: boolean;
  verified?: { at: string; by: string | null } | null;
  counts?: { done: number; needed: number };
  client_ready?: boolean;
  /** round 2 (D8): an older draft's typed answer, offered where the record is empty */
  draft_values?: Record<string, string>;
  /** round 2 (D2): the country the Country field names when clearly not India, else null */
  country_abroad?: string | null;
  /** the items the tick attests are present: "Mark as checked" may be pressed */
  tick_ready?: boolean;
  can_edit?: boolean;
}

/** The card's fields, in Legal's order and grouped as the certificate gives them. */
export const CARD_GROUPS = [
  { key: "certificate", fields: ["gstin", "legal_name", "registered_office"] },
  { key: "more", fields: ["country", "registered_email", "cin_or_llpin", "line_of_business"] },
  { key: "signs", fields: ["signatory_name", "signatory_designation", "signatory_email", "authority_reference"] },
] as const;

/** A record field's checklist item (legal name has none: it is printed, not one of the ten). */
export const itemOf = (c: ClientChecklist | null, field: string): ChecklistItem | undefined =>
  field === "legal_name" && c?.legal_name_recorded !== undefined
    ? { n: 0, key: "legal_name", status: c.legal_name_recorded ? "done" : "missing", source: "profile", profile_field: "legal_name" }
    : c?.items.find((i) => i.profile_field === field);

/** Benchmark 2: a card group is complete when the server says each of its items is added or not
 *  needed; the legal name (printed, not one of the ten) when it is on the record. Optional fields
 *  (country, authority to sign) do not count. Presentation of the server's states only. */
export const groupDone = (c: ClientChecklist, client: Record<string, unknown>, fields: readonly string[]) =>
  fields.every((f) => {
    const i = itemOf(c, f);
    return i ? i.status === "done" || i.status === "not_needed" : f !== "legal_name" || !!String(client[f] ?? "").trim();
  });

export const EMAIL_FIELDS = new Set(["registered_email", "signatory_email"]);

/** The public lookups Legal names (no paid service): the GST portal's taxpayer search and
 *  the MCA company master data. */
export const GST_PORTAL = "https://services.gst.gov.in/services/searchtp";
export const MCA_MASTER_DATA = "https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html";

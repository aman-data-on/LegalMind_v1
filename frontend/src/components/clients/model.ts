/**
 * Pure helpers for Client Profiles — no fetching, no permission logic, no legal
 * derivation. Kept separate so the house static tests can pin them, exactly as
 * `components/workspace/model.ts` is.
 *
 * ⚠️ Nothing here derives a legal conclusion. A client's documents carry the
 * server's own status bucket and the server's own reader statuses; this file
 * only counts, formats and orders. Rule 18 and 52.7: no classification, rule
 * outcome or `requires_decision` is ever computed on this side.
 */

import type { ClientContract, Counterparty, DocumentVersion } from "@/lib/types";

/** The one role that means executed. Named once on this side too, so the badge,
 *  the row's "Signed" reading and any filter cannot drift apart. */
export const FINAL_SIGNED = "FINAL_SIGNED";

/**
 * "3 clients" / "1 client" — the count in the page header.
 *
 * It says "you work with", not "the organisation has", and that wording is
 * load-bearing rather than modest: the number is scoped to the contracts this
 * caller can open (AB-13 r6), so two colleagues legitimately see two different
 * totals. A bare "18 total clients" would quietly claim to be organisation-wide.
 */
export function clientCountLabel(total: number): string {
  return total === 1 ? "1 client" : `${total} clients`;
}

export function documentCountLabel(n: number): string {
  return n === 1 ? "1 document" : `${n} documents`;
}

export function versionCountLabel(n: number): string {
  return n === 1 ? "1 version" : `${n} versions`;
}

/**
 * Whether a client profile has anything beyond its name worth putting in the
 * header's information row.
 *
 * Used to decide between the row and a single quiet invitation to fill it in —
 * an information row of five "Not available" cells is worse than no row, and
 * "absence is information" (DESIGN.md) does not mean absence needs five cells.
 */
export function hasProfileDetail(client: Counterparty): boolean {
  return Boolean(
    client.website
    || client.primary_contact_name || client.primary_contact_email
    || client.legal_contact_name || client.legal_contact_email
    || client.primary_contact_phone || client.account_owner_name,
  );
}

/**
 * The version a reader means by "the current one": the highest version number.
 *
 * Deliberately NOT "the signed one" and not "the newest by date". Version
 * number is the sequence the database guarantees unique per contract (locked
 * 42.4), and a document whose latest version is the client's redline is
 * genuinely at that version — saying otherwise would hide where the
 * negotiation actually stands.
 */
export function currentVersion(versions: readonly DocumentVersion[] | undefined):
  DocumentVersion | null {
  if (!versions || versions.length === 0) return null;
  return versions.reduce((best, v) =>
    v.version_number > best.version_number ? v : best, versions[0]!);
}

/** The executed version, if a human declared one. Never inferred from recency:
 *  the owner named "the client modified version is not always the final signed
 *  version" as the distinction to preserve. */
export function signedVersion(versions: readonly DocumentVersion[] | undefined):
  DocumentVersion | null {
  return versions?.find((v) => v.version_role === FINAL_SIGNED) ?? null;
}

/**
 * The document types actually present in one client's list — for the type
 * FILTER, and for nothing else.
 *
 * ⚠️ This must never be used to GROUP the list. The owner's instruction is
 * explicit that document type is metadata and not a folder hierarchy, and the
 * server deliberately returns one flat array with no grouping key. This returns
 * codes for a `<select>`; a caller that maps over it to render sections is
 * doing the thing the feature exists to prevent.
 */
export function typesPresent(contracts: readonly ClientContract[]): string[] {
  const seen = new Set<string>();
  for (const contract of contracts) {
    if (contract.contract_type) seen.add(contract.contract_type);
  }
  return [...seen].sort();
}

/**
 * The plain-language sentence for one activity row.
 *
 * Every action the client feed can show, in a non-legal reader's words — the
 * owner's requirement that "a normal employee who is not from the Legal team
 * should understand the page immediately". An action with no entry here falls
 * back to the raw name rather than being hidden: the trail is append-only
 * (AUD-01) and a row nobody named is still a row that happened, so dropping it
 * would misrepresent the history.
 */
const ACTIVITY_WORDS: Record<string, string> = {
  "counterparty.created": "Client profile created",
  "counterparty.updated": "Client details updated",
  "contract.counterparty_linked": "Document linked to this client",
  "contract.type_declared": "Document type recorded",
  "contract.status_changed": "Document status changed",
  "contract.archived": "Document archived",
  "contract.restored": "Document restored",
  "contract.deleted": "Document deleted",
  "contract.ownership_transferred": "Document reassigned",
  "document.reprocessed": "Document re-read",
  "analysis.run_recorded": "Document analyzed",
  "analysis.run_failed": "Analysis could not complete",
  "review.status_changed": "Review status changed",
  "legal.decision_recorded": "Legal decision recorded",
  "legal.finding_escalated": "Finding escalated for review",
  "legal.escalation_withdrawn": "Escalation withdrawn",
  "report.exported": "Report exported",
};

export function activityWords(action: string): string {
  return ACTIVITY_WORDS[action] ?? action;
}

/** A date a non-technical reader reads at a glance. Absent stays absent. */
export function shortDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return null;
  return at.toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
}

/**
 * The profile a PATCH returned, re-joined to the parts only the DETAIL endpoint
 * carries — the document list and the derived counts.
 *
 * `saved` is the base and not the overlay, which is the whole point. Spreading
 * `saved` OVER the old profile looks equivalent and is wrong: the API omits a
 * field that has been cleared rather than nulling it, so `{...old, ...saved}`
 * would quietly keep the old city after someone deleted it. Taking `saved`
 * whole and re-attaching only what it never had is the merge that respects
 * that contract.
 *
 * Why merge at all rather than refetch: an edit that blanked the document list
 * for a frame would make the table flicker away and back. The refetch still
 * happens; this is what the reader sees until it lands.
 */
export function mergeProfile(
  current: Counterparty, saved: Counterparty,
): Counterparty {
  const merged: Counterparty = { ...saved };
  if (current.contracts !== undefined) merged.contracts = current.contracts;
  if (current.documents !== undefined) merged.documents = current.documents;
  if (current.signed_documents !== undefined) {
    merged.signed_documents = current.signed_documents;
  }
  if (current.last_activity !== undefined) {
    merged.last_activity = current.last_activity;
  }
  return merged;
}

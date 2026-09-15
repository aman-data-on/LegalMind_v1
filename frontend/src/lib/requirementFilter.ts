/**
 * Finding one Requirement among forty.
 *
 * The Standards screen rendered every Requirement as its own stacked card, with no
 * search and no filter. At 40 ratified standards that is a scroll, not a screen —
 * and it was the one place in the product that did not use the list shape every
 * other screen uses (Administration, Audit, Dashboard, Client Profiles all have a
 * filter bar above a table).
 *
 * The logic is here rather than in the component because `vitest.config.ts` is
 * `environment: "node"`: a filter that silently drops a row is a legal-configuration
 * bug, and it can only be caught by a test at this layer.
 *
 * WHAT CANNOT BE FILTERED, AND WHY IT IS NOT OFFERED. Document type is the obvious
 * fourth filter and it is deliberately absent: `GET /requirements` returns code,
 * status and versions, while `document_type` lives inside the Company Standard on
 * the DETAIL response, which is separately gated. The code usually carries a type
 * by convention (`LIABILITY-MSA-001`), but reading a legal filter out of a naming
 * convention is a guess — `STRUCTURAL-E2E-001` alone disproves it — and a filter
 * that silently hides a standard is worse than one that does not exist. Offering it
 * needs the list response to carry the field, which is an API decision, not a
 * presentation one.
 */

import { ACTIVE, DEPRECATED, DRAFT } from "@/lib/publishPlan";
import type { Requirement } from "@/lib/types";

/** Every filter's "no constraint" value, so an empty select means unfiltered. */
export const ANY = "";

export interface RequirementFilters {
  /** Matches the Requirement code and any version name. */
  search: string;
  /** One of the Step 29 lifecycle values, or ANY. */
  status: string;
  /** One of the two locked evaluator types (`AM-16`), or ANY. */
  evaluator: string;
}

export const NO_FILTERS: RequirementFilters = { search: ANY, status: ANY, evaluator: ANY };

/**
 * The reader's word for each lifecycle state. "Retired" rather than "Deprecated"
 * because that is what the publish screen and `AM-65` call it, and one vocabulary
 * across the screen is the whole point.
 */
export const STATUS_LABELS: ReadonlyArray<{ code: string; label: string }> = [
  { code: DRAFT, label: "Draft" },
  { code: ACTIVE, label: "Active" },
  { code: DEPRECATED, label: "Retired" },
];

/**
 * The two locked evaluator types (`AM-16`) as words. The raw enum reads as a
 * database column, not as what the standard does, and the screen already has to
 * name them in the filter — one vocabulary, one place.
 */
export const EVALUATOR_LABELS: ReadonlyArray<{ code: string; label: string }> = [
  { code: "NUMERIC_COMPARISON", label: "Numeric comparison" },
  { code: "PRESENCE", label: "Presence" },
];

export function evaluatorLabel(evaluator: string | null | undefined): string {
  if (!evaluator) return "\u2014";
  return EVALUATOR_LABELS.find((e) => e.code === evaluator)?.label ?? evaluator;
}

export function statusLabel(status: string): string {
  return STATUS_LABELS.find((s) => s.code === status)?.label ?? status;
}

/** The evaluator of the newest version — what the row shows and the filter matches. */
export function latestVersion(requirement: Requirement) {
  return requirement.versions.length > 0
    ? requirement.versions[requirement.versions.length - 1]
    : null;
}

/** Orders the list. Code is the default because it is how every other record —
 *  a fixture, a snapshot item, an explanation — refers to a standard. */
export const SORTS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "code", label: "Code" },
  { value: "recent", label: "Recently changed" },
];

export function sortRequirements(rows: Requirement[], sort: string): Requirement[] {
  if (sort !== "recent") return [...rows].sort((a, b) => a.code.localeCompare(b.code));
  const changed = (r: Requirement) => latestVersion(r)?.created_at ?? "";
  // Newest first; a standard with no version sorts last rather than first, because
  // "never changed" is not "changed just now".
  return [...rows].sort((a, b) => changed(b).localeCompare(changed(a)) || a.code.localeCompare(b.code));
}

export function filterRequirements(
  requirements: readonly Requirement[] | null,
  filters: RequirementFilters,
): Requirement[] {
  const needle = filters.search.trim().toLowerCase();
  return (requirements ?? []).filter((requirement) => {
    if (filters.status !== ANY && requirement.status !== filters.status) return false;
    if (filters.evaluator !== ANY) {
      // Match ANY version's evaluator, not just the newest: a Requirement whose
      // evaluator changed is still legitimately found by either.
      const evaluators = requirement.versions.map((v) => v.evaluator_type);
      if (!evaluators.includes(filters.evaluator)) return false;
    }
    if (needle === "") return true;
    const haystack = [
      requirement.code,
      ...requirement.versions.map((v) => v.name),
    ].join(" ").toLowerCase();
    return haystack.includes(needle);
  });
}

/** Whether any constraint is set — so an empty result can say which kind of empty. */
export function isFiltered(filters: RequirementFilters): boolean {
  return filters.search.trim() !== ANY || filters.status !== ANY || filters.evaluator !== ANY;
}

/**
 * Permission names — locked Step 47 §47.4 catalogue.
 *
 * These are used **only to decide what to render** (52.1 r3, 52.3, 43.31). Hiding
 * a control is a usability affordance, never a security control: the server
 * authorizes every operation regardless, and a control this file failed to hide
 * would still be refused with a 403.
 *
 * The names duplicate the backend catalogue, which is unavoidable — the UI has to
 * name a permission to gate on it. The duplication is safe in one direction only:
 * a name that drifts out of date can cause a control to be hidden that should be
 * shown (annoying), never shown that should be hidden (a real problem), because
 * the array comes from the server and an unknown name simply never matches.
 */

export const CONTRACT_VIEW = "contract.view";
export const CONTRACT_CREATE = "contract.create";
export const CONTRACT_UPDATE = "contract.update";
/** Granted to ROLE_USER and scoped by ownership (owner approval 2026-09-01):
 *  a user may delete what they uploaded and nothing else. Presentation gating
 *  only, as always — the server re-resolves `owner_id` on every request. */
export const CONTRACT_DELETE = "contract.delete";
export const DOCUMENT_UPLOAD = "document.upload";
export const DOCUMENT_VIEW = "document.view";
export const DOCUMENT_DOWNLOAD = "document.download";

export const REVIEW_CREATE = "review.create";
export const REVIEW_VIEW = "review.view";
export const FINDING_VIEW = "finding.view";
export const EVALUATION_VIEW = "evaluation.view";

/** Locked Step 23 names, carried verbatim. */
export const LEGAL_REVIEW = "legal.review";
export const LEGAL_DECISION = "legal.decision";
export const LEGAL_APPROVE_CUSTOMIZATION = "legal.approve_customization";

/** LEGAL-02 — gates rule outcomes, thresholds and explanations (49.7 r4). */
export const LEGAL_POSITION_VIEW = "legal_position.view";

export const CONFIGURATION_VIEW = "configuration.view";
export const CONFIGURATION_DRAFT = "configuration.draft";
export const CONFIGURATION_PUBLISH = "configuration.publish";

export const REPORT_VIEW = "report.view";
/** 49.3's export row; formats per the owner's 2026-08-31 directive. */
export const EXPORT_GENERATE = "export.generate";
export const ASSIST_ASK = "assist.ask";
export const AUDIT_VIEW = "audit.view";
export const USER_MANAGE = "user.manage";
export const ROLE_MANAGE = "role.manage";

/**
 * The decision types the API accepts — locked Step 31, `DecisionType`.
 *
 * `REQUEST_CLARIFICATION` is included and is deliberately not treated as a
 * disposition anywhere in the UI: locked Step 31 r10 makes it leave the workflow
 * unresolved, and the server reports that as `is_effective: false`.
 */
export const DECISION_TYPES = [
  "ACCEPT_DEVIATION",
  "REQUIRE_COMPANY_STANDARD",
  "APPROVE_CUSTOMIZATION",
  "REJECT",
  "REQUEST_CLARIFICATION",
] as const;

export type DecisionType = (typeof DECISION_TYPES)[number];

/**
 * Which decision types this caller may submit.
 *
 * Presentation only. `APPROVE_CUSTOMIZATION` additionally requires
 * `legal.approve_customization` (Step 23, 47.5, 49.3) — the server enforces that
 * whether or not the option was rendered.
 */
export function submittableDecisionTypes(permissions: readonly string[]): DecisionType[] {
  if (!permissions.includes(LEGAL_DECISION)) return [];
  return DECISION_TYPES.filter(
    (type) =>
      type !== "APPROVE_CUSTOMIZATION" ||
      permissions.includes(LEGAL_APPROVE_CUSTOMIZATION),
  );
}

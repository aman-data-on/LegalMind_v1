/**
 * Response shapes from `/api/v1/` — locked Step 49.
 *
 * The most important thing in this file is which properties are **optional**.
 *
 * Locked 49.7 r4 requires internal legal position to be *omitted, not nulled*,
 * for callers without `legal_position.view`, and Step 52.4 requires the UI to
 * render an omitted field as simply absent. Declaring those properties optional
 * rather than `T | null` makes the compiler enforce the distinction: code cannot
 * read `evaluation.rule_outcome` and render a dash for it, because the property
 * may not exist at all. `exactOptionalPropertyTypes` is on for the same reason.
 *
 * Nothing here is derived. Every classification, rule outcome and
 * `requires_decision` flag arrives from the server (38.23, 52.7).
 */

/** Locked 43.21 / 49.4 — the three envelope shapes and no others. */
export interface DataEnvelope<T> {
  data: T;
}
export interface PaginatedEnvelope<T> {
  data: T[];
  pagination: Pagination;
}
export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
    fields?: { field: string; code: string }[];
  };
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
}

// --------------------------------------------------------------- identity
export interface SessionIdentity {
  user_id: string;
  email: string;
  name: string;
  status: string;
  /**
   * 49.2 / 43.31 / 47.6 r3 — a convenience projection for **presentation
   * gating only**. Every operation is authorized server-side regardless, so a
   * stale array can only over-hide, never over-permit (52.3).
   */
  permissions: string[];
  /** AB-12 r3 — presentation only, like `permissions`: names the department the
   *  "Department deals" view is about, or `null` if the account is in none. */
  department: Department | null;
  /** The sign-in provider's profile photo (a Google-hosted https URL), or null. */
  picture?: string | null;
  authenticated_at?: string;
}

// -------------------------------------------------- contracts & documents
/** One evidence row as `GET /document-versions/{id}/evidence` returns it — the
 * document as the pipeline read it, in reading order (page, offset). */
export interface EvidenceRow {
  id: string;
  document_version_id: string;
  page_number: number | null;
  section_number: string | null;
  section_title: string | null;
  /** Whether this row BEGINS a section — recorded by the parser at extraction,
   *  never derived here. Rows written before 2026-09-05 carry `false`, so the
   *  outline falls back to numbered rows for them rather than rendering empty. */
  is_heading?: boolean;
  /** The document's OWN annexure/schedule/appendix title when this row is one
   *  ("Annexure-1", "Schedule 2 – Fees") — locked 44.4's "where detectable",
   *  recorded by the parser (2026-09-06). Present only on such rows. */
  annexure?: string;
  /** What the client's lawyer marked on this row (tracked changes), in order. */
  changes?: { deleted: string; inserted: string }[];
  /** The reviewer's comments made on this row — notes, never the row's text. */
  comments?: { author: string; text: string }[];
  content: string;
  source_type: string;
  start_offset: number | null;
  end_offset: number | null;
}

/** One list row's analysis reality (2026-08-31 UX correction). `classification_counts`
 *  needs `finding.view` and arrives OMITTED without it — presence-test, never null-test. */
export interface LatestAnalysis {
  review_id: string;
  review_status: string;
  created_at: string | null;
  completed_at: string | null;
  classification_counts?: Record<string, number>;
  /** ACCEPTABLE / REQUIRES_MODIFICATION / NEEDS_DECISION per finding — the Dashboard's counts. */
  user_status_counts?: Record<string, number>;
}

/** Step 6's source axis — declared by the uploader, never inferred. */
export type DocumentSource = "ORGANIZATION" | "COUNTERPARTY";

export interface LatestVersionSummary {
  id: string;
  version_number: number;
  processing_status: string;
  /** When this version was uploaded (ISO); what Diff-Talk dates and orders by. */
  created_at?: string | null;
  /** Declared (2026-09-06): present only when someone said so — never null. */
  source?: DocumentSource;
  counterparty?: string;
  /** ISO date, as declared. Never read out of the document. */
  effective_date?: string;
}

/** The company on the other side of a deal — AB-13 r1. `industry` and
 *  `relationship_notes` are OMITTED when nobody typed them: an unknown industry
 *  is a fact, and a null would invite the UI to render "Industry: —" as though
 *  it had been checked. */
export interface Counterparty {
  id: string;
  name: string;
  /** ACTIVE / PROSPECTIVE / INACTIVE. Always present — the column is NOT NULL.
   *  A filing state, never one of the five legal state axes. */
  status: string;
  industry?: string;
  relationship_notes?: string;
  created_at: string | null;
  updated_at: string | null;
  /** Present only on the detail endpoint: every contract for this company that
   *  the caller may already see. AB-13 r3 — derived from the link, not a graph. */
  contracts?: ClientContract[];

  /* ---- Client Profile (2026-09-10) -------------------------------------
   * Every one of these is OMITTED when nobody typed it, exactly as
   * `industry` always was. The screen renders "Not available" against an
   * absent key — never a dash that reads as "checked and empty".            */
  legal_name?: string;
  website?: string;
  city?: string;
  state_region?: string;
  country?: string;
  primary_contact_name?: string;
  primary_contact_email?: string;
  primary_contact_phone?: string;
  legal_contact_name?: string;
  legal_contact_email?: string;
  account_owner_id?: string;
  account_owner_name?: string | null;
  /** Counts, per caller (`?stats=true` on the list, always on the detail).
   *  Derived server-side from the contracts THIS caller may open, so two
   *  people legitimately see different numbers for the same company. */
  documents?: number;
  signed_documents?: number;
  last_activity?: string | null;
}

/** A contract as the Client Profile's ONE unified document list needs it: the
 *  Dashboard's row projection plus its version history.
 *
 *  There is deliberately no per-type grouping field. Document type is metadata
 *  on the row (`contract_type`), and the owner's instruction makes that
 *  structural — a client's documents are one list, never MSA/NDA/SLA folders. */
export interface ClientContract extends Contract {
  /** Newest first. Present when the caller holds `document.view`. */
  versions?: DocumentVersion[];
  version_count?: number;
  /** Whether ANY version was declared FINAL_SIGNED. Never inferred from
   *  recency: a client's redline is not the executed copy. */
  signed?: boolean;
}

/** One row of a client's history — the existing `audit_events` trail, scoped to
 *  this client and its documents. Deliberately carries no before/after payload:
 *  those can hold an internal legal position (`LEGAL-02`). */
export interface ClientActivity {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  /** The document's name, where the event was about one. */
  subject?: string | null;
  actor_name?: string | null;
  timestamp: string | null;
}

export interface Contract {
  /** Newest first. Present on the detail endpoint (2026-08-30 addition). */
  document_versions?: DocumentVersion[];
  /** List rows only (2026-08-31): the newest version and its newest Review. */
  latest_version?: LatestVersionSummary | null;
  latest_analysis?: LatestAnalysis | null;
  id: string;
  owner_id: string;
  /** Whose deal this is — present on list rows and the detail (AB-12): the
   *  Department deals view holds more than the caller's own. */
  owner_name?: string | null;
  name: string;
  contract_type: string | null;
  status: string;
  /** AB-12 r6 — set means read-only and off the working list. Never a sixth
   *  `status` value. */
  archived_at: string | null;
  /** AB-13 r2 — who this deal is with; null when unlinked, which is the honest
   *  state for every contract predating the record. */
  counterparty_id?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** The Documents list's stat tiles — real counts across EVERY contract the
 *  caller owns (`GET /contracts/summary`), computed server-side by the exact
 *  same bucket rule `?status=` filters the list on, so a tile and a row can
 *  never disagree. Four states, all derived from data already on the row —
 *  never a new lifecycle enum, never a Finding Classification. */
export interface ContractsSummary {
  total: number;
  draft: number;
  analyzing: number;
  needs_attention: number;
  analyzed: number;
}

export interface DocumentVersion {
  id: string;
  contract_id: string;
  version_number: number;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  file_hash: string;
  /** 34.15 / Step 30 r13 — a document concern, distinct from Review lifecycle. */
  processing_status: string;
  extraction_status: string | null;
  /** QA-037: why a FAILED version could not be read (present only then) */
  unreadable_reason?: string;
  uploaded_by: string;
  created_at: string | null;
  /** Declared (2026-09-06), from locked 42.4's `metadata` JSONB: present only
   * when someone said so — never null. Fixed once the version has a Review. */
  source?: DocumentSource;
  counterparty?: string;
  effective_date?: string;
  /** COMPANY_DRAFT / CLIENT_MODIFIED / FINAL_SIGNED (2026-09-10) — what this
   *  version IS in the negotiation. A THIRD axis, not a synonym for `source`:
   *  `source` says whose paper it is, this says where in the negotiation it
   *  sits. Absent on every version nobody classified, and never inferred from
   *  the version number, the filename or the date. */
  version_role?: string;
  /** Counts, deliberately not a state vocabulary (`AM-29` r1): the client derives
   * ready / lexical-only / not-indexed. Present on the detail endpoint. */
  assist_index?: { chunks: number; embedded_chunks: number; refused?: string[] };
  /** The latest completed reading's page accounting (R3), detail endpoint only:
   *  pages that could not be read, and pages whose OCR text should be checked
   *  against the original (run_metadata's low-OCR list, named here without the
   *  word the rule-12 terms gate forbids in frontend source). */
  pages_failed?: number[];
  pages_to_check?: number[];
}

export interface UploadResult {
  document_version: DocumentVersion;
  processing_run: {
    id: string;
    run_type: string;
    status: string;
    processor_version: string | null;
    error_code: string | null;
  };
  evidence_count: number;
  /** 34.5 — reported, never silently suppressed. */
  duplicate_of: string | null;
  diagnostics: string[];
}

/** Key Obligations — the assist lane's descriptive extraction. Facts about the
 *  document's text under its OWN role labels; never a judgment, never a Finding. */
export interface ObligationItem {
  id: string;
  obligation_text: string;
  evidence_id: string | null;
  section_ref: string | null;
  page_number: number | null;
}

export interface ObligationGroup {
  /** The document's own verbatim role label (e.g. "Customer"). */
  party_label: string;
  items: ObligationItem[];
}

export interface ObligationsResult {
  /** False while no extraction has completed for this version. */
  extracted: boolean;
  groups: ObligationGroup[];
}

/** Assist-lane type suggestion — advice for the intake pre-fill, never a record.
 *  `confident: false` collapses to today's empty select. */
export interface TypeSuggestion {
  suggested_type: string | null;
  confident: boolean;
  reason: string;
}

// ------------------------------------------------------------- reviews
export interface Review {
  id: string;
  contract_id: string;
  document_version_id: string;
  /** Step 30 / AUD-04 — what makes the Review reproducible. */
  configuration_snapshot_id: string;
  status: string;
  created_by: string;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  /** The document's own name, served WITH the Review (2026-09-04). Every list
   *  screen used to fetch this per row from `GET /contracts/{id}`, which is
   *  ownership-scoped — so a Legal-scope viewer got a 404 and the row fell back
   *  to a raw UUID. `null` only when the contract row is genuinely gone. */
  document_name: string | null;
  document_type: string | null;
  /** Whether `/dashboard?id={contract_id}` will actually open for THIS caller
   *  (owned, not soft-deleted). Presentation only — the server still refuses. */
  document_accessible: boolean;
  /** AB-100 — the owner sent this Review to the caller (their queue first). */
  sent_to_you?: boolean;
  /** AM-174 — the current decision on the whole contract, if one was recorded */
  contract_outcome?: ContractOutcome | null;
}

/** AM-174 (owner, 2026-10-22) — what to do with the contract, after every point. */
export type ContractOutcome = "SIGN_AS_IS" | "SIGN_WITH_CHANGES" | "DO_NOT_SIGN" | "ON_HOLD";

export interface ContractOutcomeVersion {
  outcome: ContractOutcome;
  suggested: ContractOutcome;
  justification: string;
  decided_by_name: string | null;
  decided_at: string | null;
  version_number: number;
}

export interface ContractOutcomeState {
  /** the code's suggestion from the point decisions — a person chooses */
  suggested: ContractOutcome;
  /** every required point is decided, so the contract can be */
  ready: boolean;
  /** why no decision can be recorded here (archived, or a newer version analysed) */
  read_only?: string | null;
  /** oldest first; the last is current */
  history: ContractOutcomeVersion[];
  review_status?: string;
}

export interface Evidence {
  id: string;
  relationship_type: string;
  page_number: number | null;
  section_number: string | null;
  section_title: string | null;
  content: string;
  source_type: string;
}

export interface Decision {
  id: string;
  evaluation_id: string;
  finding_id: string;
  decision_type: string;
  justification: string;
  decided_by: string;
  /** Who decided, by name (owner, 2026-10-21) — the id stays the record. */
  decided_by_name?: string | null;
  version_number: number;
  /** Step 31 r20 — the current version is the highest; the rest are superseded. */
  is_current: boolean;
  created_at: string | null;
}

export type UserStatusWord = "ACCEPTABLE" | "NEEDS_DECISION" | "REQUIRES_MODIFICATION" | "MISSING";

export interface Evaluation {
  id: string;
  finding_id: string;
  scope_key: string;
  scope_label: string | null;
  evaluation_kind: string;
  /** Always present — the authoritative per-scope result (AB-1, 45B re-lock). */
  classification: string;
  actual_value: unknown;
  evaluated_facts: unknown;
  /** 49.7 r3 — always an array; may legitimately be empty, never null. */
  evidence_refs: string[];
  diagnostics: string[];
  evaluator_type: string;
  evaluator_version: string;
  /** Derived server-side (D-3.5). Never computed here. */
  requires_decision: boolean;
  /** The reader's three words (owner's final decision, 2026-09-09) — derived
   *  server-side from classification, the approved rule's outcome and the
   *  Constitution citation. The UI renders it and never re-derives it. */
  user_status?: UserStatusWord;
  current_decision: Decision | null;
  created_at: string | null;

  // --- internal legal position: OMITTED without `legal_position.view` -------
  // Optional on purpose. See the file header.
  rule_outcome?: string;
  expected_value?: unknown;
  operator?: string | null;
  comparison?: unknown;
  explanation?: string[];
  legal_rule_version_id?: string | null;
  /**
   * Present ONLY when the approved Legal Constitution explicitly establishes
   * that the contract's position is not acceptable (owner, 2026-09-08). The
   * server states it with its citation; the UI never derives it from a
   * DEVIATION, a MISSING or an UNACCEPTABLE rule outcome. Omitted (never
   * null) whenever it does not apply — see `redact_legal_position`, which
   * omits it identically for a caller without `legal_position.view`.
   *
   * Wired for two Company Standards only (2026-09-08, sixth pass):
   * `LIABILITY-MSA-001`/`LIABILITY-TOS-001` on an unlimited cap (Constitution
   * §9) and `DATA-RETRIEVAL-TOS-001` on a retrieval window under 30 days
   * (§13) — see `backend/legalmind/evaluation/constitution_boundaries.py`
   * for why the other four reconciled standards are not (their Unacceptable
   * Position text is qualitative, not a checkable threshold).
   */
  constitution_prohibition?: { section: string; quote: string } | null;
}

/** `POST /findings/{id}/explain` — the grounded one-sentence explanation
 *  (owner, 2026-09-09; AM-49). Language only: it never carries or changes the
 *  classification or the status. `text` is null unless `status` is ACCEPTED. */
export interface FindingExplanation {
  status: "ACCEPTED" | "FALLBACK" | "FAILED";
  text: string | null;
  reason: string | null;
  prompt_version: string;
  passages: number;
  cached: boolean;
}

export interface Finding {
  id: string;
  review_id: string;
  /** AM-179 — the point this finding belongs to; findings that share it are one card,
   *  decided together. Server-built (the one fold every screen uses). */
  group_id?: string;
  requirement: {
    code: string | null;
    name: string | null;
    /** What this requirement checks, in plain words — from the ratified
     *  standard's `description` (owner, 2026-09-09). Explanatory only: it
     *  never determines the classification or the user-facing status. */
    description?: string | null;
    version_id: string;
    version_number: number | null;
    /** AM-59 — the Constitution section that states the measured position, its
     *  Appendix B category and the basis in the Constitution's own vocabulary.
     *  A citation, never a value; `section` null when the Constitution states no
     *  position (basis `DOCUMENT_ONLY`); absent on pre-AM-59 snapshots. */
    constitution?: {
      section: string | null;
      topic: string | null;
      basis: string | null;
    } | null;
    /** AM-65 — the standard behind this finding has been withdrawn because the
     *  current Constitution does not define it. Read from the requirement's
     *  CURRENT status, so a finding written before the retirement says so too.
     *  The finding itself is untouched and stays on the record (rule 17). */
    retired?: boolean;
  };
  /**
   * 49.7 r1 — a **derived, non-authoritative summary**. The API never returns it
   * without `evaluations`, and the UI never shows it without them (52.5).
   */
  classification: string;
  status: string;
  requires_decision: boolean;
  escalated: boolean;
  /** The worst of its evaluations' `user_status`, server-derived. */
  user_status?: UserStatusWord;
  evaluations: Evaluation[];
  evidence: Evidence[];
  created_at: string | null;
  updated_at: string | null;
  // There is deliberately no Finding-level `rule_outcome`: none is persisted
  // (J-2, 49.7 r2).
}

export interface Escalation {
  id: string;
  finding_id: string;
  raised_by: string;
  reason: string;
  created_at: string;
}

export type ApplicabilityOutcome = "APPLIED" | "NOT_APPLICABLE" | "SAME_POSITION"
  /** AM-147 — another family's copy of a topic measured once for this document. */
  | "SAME_TOPIC";

export interface ApplicabilityRecord {
  code: string;
  section: string | null;
  outcome: ApplicabilityOutcome;
  reason: string;
}

/** Who decided what, when and why (owner, 2026-10-21) — each Evaluation's current one. */
export interface ReportDecision {
  finding_id: string;
  requirement_code: string;
  requirement_name: string | null;
  decision_type: string;
  decided_by_name: string | null;
  decided_at: string | null;
  justification: string;
  version_number: number;
}

export interface ReviewReport {
  review_id: string;
  review_status: string;
  decisions?: ReportDecision[];
  contract_outcome?: ContractOutcomeState;
  progress?: ReviewProgress;
  coverage: {
    requirements_in_snapshot: number;
    requirements_with_findings: number;
    /** AM-61 — every pinned requirement's applicability outcome and reason,
     *  from the analysis run's audit record. What was NOT measured is shown,
     *  with why — never inferred from a count. Empty on pre-AM-61 runs. */
    applicability?: ApplicabilityRecord[];
  };
  classification_counts: Record<string, number>;
  user_status_counts?: Record<string, number>;
  status_counts: Record<string, number>;
  /** F-9 — a ratio over evaluated Requirements. Carries no legal meaning. */
  alignment: {
    requirements_evaluated: number;
    matched: number;
    ratio: number | null;
  };
  unmatched_provisions: number;
  /** REC-02 / D-4 (owner, 2026-09-01) — WHICH provisions, so a human can look
   *  at each one. Never a Finding, never a classification, never presumed
   *  negative (REC-02 rule 1) — routed to a human only because the system
   *  has no Requirement to compare it against. */
  unmatched_provisions_detail: Array<{
    evidence_id: string;
    page_number: number | null;
    section_number: string | null;
    section_title: string | null;
    excerpt: string;
  }>;
  findings_requiring_decision: number;
  // There is deliberately no risk score and no overall verdict (36.10, F-8).
}

// ----------------------------------------------------------- configuration
export interface RequirementVersion {
  id: string;
  version_number: number;
  name: string;
  description: string | null;
  evaluator_type: string;
  created_at: string | null;
  /**
   * Present only on the DETAIL response (`GET /requirements/{id}`), which the API
   * gates on `configuration.view`. The list response carries no values at all, so
   * these are optional rather than nullable — a field the caller did not receive is
   * absent, never a placeholder (52.4).
   */
  created_by?: string;
  company_standard?: Record<string, unknown> | null;
  /**
   * The Legal Rule is the confidential Internal Legal Position (LEGAL-02) and is
   * genuinely optional (Step 20 r4). Omitted, not nulled, when absent.
   */
  legal_rule?: { rule_type: string; configuration: Record<string, unknown> };
}

export interface Requirement {
  id: string;
  code: string;
  status: string;
  versions: RequirementVersion[];
  created_at: string | null;
}

/** `GET /configuration/snapshots` rows — metadata only, never items or values. */
export interface SnapshotSummary {
  id: string;
  snapshot_hash: string;
  created_at: string;
  requirement_count: number;
}

export interface ConfigurationSnapshot {
  id: string;
  snapshot_hash: string;
  created_at: string;
  requirement_count: number;
  reused_existing: boolean;
}

// ------------------------------------------------------------------ audit
export interface AuditEvent {
  id: string;
  actor_id: string | null;
  /** Resolved account. `null` for a pre-authentication event (42.18 makes
   *  `actor_id` nullable so a failed login can be recorded) — not "unknown". */
  actor: { id: string; name: string; email: string } | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  /** Resolved only for user/department/role/session. A contract is deliberately
   *  never labelled here — naming it would hand a Platform Admin the one thing
   *  the scope model withholds. */
  entity_label: string | null;
  /** Identity-and-access event: its payload is legible to an `audit.view` holder. */
  administrative: boolean;
  timestamp: string | null;
  request_id: string | null;
  /** Present for administrative events, and otherwise gated behind
   *  `legal_position.view` — omitted, never nulled (Step 24 r8). */
  before_state?: unknown;
  after_state?: unknown;
}

// ---------------------------------------------------------- administration
/** AB-12 r3 — the boundary a Department Lead's oversight is scoped to. */
export interface Department {
  id: string;
  code: string;
  name: string;
  created_at?: string | null;
  /** Rollup, present on the administration list and detail. `leads` is DERIVED
   *  from who holds `DEPARTMENT_LEAD` in the department — there is no
   *  `lead_id` column, because the role assignment is what grants the scope. */
  members?: number;
  active_members?: number;
  leads?: { name: string; email: string }[];
  /** Detail only. */
  member_accounts?: User[];
}

export interface DepartmentMembers {
  department: Department | null;
  members: { id: string; name: string; email: string }[];
}

export interface User {
  id: string;
  email: string;
  name: string;
  status: string;
  roles: string[];
  department: Department | null;
  /** How this account can sign in — names only, never a subject or a hash (S-4).
   *  Empty means no credential is provisioned: the account exists and cannot yet
   *  authenticate by any route. */
  auth_providers: string[];
  /** Last successful authentication. `null` means never — not "unknown". */
  last_login_at: string | null;
  /** From the `admin.user_created` audit row (AUD-01). `null` for an account the
   *  seed made or an SSO identity linked to (47.1.3 r2) — not a gap to fill in. */
  provisioned_by: { id: string; name: string; email: string } | null;
  created_at: string | null;
  updated_at: string | null;
}

/** The SEC-04 catalogue, grouped as an administrator reads it. */
export interface PermissionCatalogue {
  groups: {
    group: string;
    permissions: {
      name: string;
      description: string | null;
      /** SEC-02/ROLE-05 — no bypass may ever reach these two. */
      confers_legal_authority: boolean;
    }[];
  }[];
}

/** What KIND of role a row is (AB-12 r10) — the screen speaks in these, never
 *  in codes. `future_legal` roles exist for a workflow nobody runs yet and stay
 *  out of the everyday picker. */
export type RoleTier = "department" | "platform" | "break_glass" | "future_legal" | "custom";

export interface Role {
  id: string;
  code: string;
  name: string;
  tier: RoleTier;
  permissions: string[];
  /** SEC-02 / ROLE-05 made visible without knowing which names are special. */
  confers_legal_authority: string[];
}

// ------------------------------------------------------------- analysis
/**
 * The outcome of an analysis run — locked 44.2/44.40, 49.8.
 *
 * `review_status` is the Step 30 lifecycle state and is the **single source of
 * progress** (52.7). There is no separate job-state field, because a second
 * progress value could disagree with the lifecycle.
 *
 * Nothing here is derived client-side: classification, mapping state and the
 * skipped-as-optional count all arrive as the server computed them (38.23).
 */
export interface AnalysisSubmission {
  review_id: string;
  review_status: string;
  /**
   * How the submission was handled — locked 55.1.
   *
   * `"queued"` (HTTP 202) means a worker will run it and **no Finding exists yet**,
   * so the count fields below are absent rather than zero: reporting zero Findings
   * would be a legal statement about the contract rather than a statement about the
   * job. `"inline"` (201) means it already ran and they are present.
   */
  mode?: "queued" | "inline";
  /** Correlation only. Not a progress resource — 52.7 keeps that on the Review. */
  task_id?: string | null;
  /** Present and true when the Review had already been analysed (49.8). */
  already_analysed?: boolean;
  detail?: string;
  requirements_in_snapshot?: number;
  findings_created?: number;
  /** Locked F-1 — coverage, not a gap: nothing required, nothing found. */
  skipped_as_optional?: number;
  requirements?: {
    requirement_code: string;
    mapping_state: string | null;
    finding_id: string | null;
    classification: string | null;
    evaluation_count: number;
    skipped_as_optional: boolean;
    /** A configuration failure. Never a legal conclusion. */
    failure: string | null;
    /** REC-07 — diagnostic metadata only; cannot alter a Finding. */
    diagnostics: string[];
  }[];
  idempotency_key?: string | null;
}

// ---- assist lane (AB-3/AB-4) ---------------------------------------------
// The answer state is the SIXTH axis (AM-29): it never shares a value with any
// legal axis, and there is deliberately no "confidence" field anywhere here —
// retrieval_score is a retrieval score and the UI labels it as exactly that
// (AI-03 item 16, rule 12).
export type AssistAnswerState =
  | "ANSWERED"
  | "NO_EVIDENCE_RETRIEVED"
  | "EVIDENCE_INSUFFICIENT"
  | "CLAIM_UNSUPPORTED";

export interface AssistCitation {
  chunk_id: string;
  /** The evidence row the chunk was cut from — drives the document highlight. */
  evidence_id: string;
  page_number: number | null;
  section_ref: string | null;
  excerpt: string;
  /** Null only on a replayed answer whose retrieval-run row is missing. */
  retrieval_score: number | null;
}

/** One verbatim quote from a ratified Company Standard — Domain A (`AM-32` r4).
 *  Never paraphrased, never sent to the model; cited by standard code and clause. */
export interface AssistPosition {
  position_chunk_id: string;
  standard_code: string;
  document_type: string;
  source_clause: string | null;
  content: string;
  /** `AM-32` r4's citation is "standard code, version, source clause". Null only for
   *  a record written before the join existed. */
  standard_version: number | null;
  /** The configuration lifecycle state of the standard this position came from —
   *  ACTIVE / DRAFT / DEPRECATED. A reader quoting a position is entitled to know
   *  whether it is still the current one. */
  ratification_status: string | null;
  retrieval_score: number | null;
  /** The deterministic engine's existing Finding for this standard on the asked
   *  version — READ, never produced, by Ask (the `AM-45` r4 precedent). Absent
   *  when no Review holds one or the caller may not view findings. */
  finding?: AssistPositionFinding | null;
}

export interface AssistPositionFinding {
  finding_id: string;
  classification: string;
  user_status: "ACCEPTABLE" | "REQUIRES_MODIFICATION" | "MISSING" | "NEEDS_DECISION";
}

/** The evaluator handoff on a comparison question (`AM-25` r4): the latest Review
 *  of the asked version and its Finding counts — read, never produced, by Ask. */
export interface AssistComparison {
  /** Null for a chat file's TEMPORARY review (`AM-143`): nothing was saved to fetch. */
  review_id: string | null;
  review_status: string;
  findings_by_classification: Record<string, number>;
  /** `AM-143` — a chat file reviewed by the Dashboard's own engine, never a Contract:
   *  its Findings travel on the live answer only. */
  temporary?: boolean;
  filename?: string | null;
  findings?: Finding[];
  /** `AM-149` — the open document's own clause the question quotes, found by its
   *  words: the table is that clause's Findings, and its tracked changes are listed. */
  clause?: AssistClauseScope | null;
}

/** `AM-149` — one clause of the open document, as the routed question quoted it. */
export interface AssistClauseScope {
  evidence_ids: string[];
  /** "§13 · Service Termination · page 2" — the parser's own location. */
  location: string;
  /** The document's tracked changes in this clause (AM-146), deleted → inserted. */
  changes: { deleted: string; inserted: string }[];
}

/** One statute citation — Domain C (`AM-32` r7): Act + section, never a page alone. */
export interface AssistStatuteCitation {
  statute_chunk_id: string;
  citation: string;
  official_title: string;
  section_number: string;
  sub_section: string | null;
  marginal_note: string | null;
  excerpt: string;
  retrieval_score: number | null;
}

/** The statute half of an answer, generated over statute evidence only and kept in
 *  its own section (`AM-45` r2). `text` is null on replay (the turn's content holds it). */
export interface AssistStatuteAnswer {
  answer_state: AssistAnswerState;
  text: string | null;
  citations: AssistStatuteCitation[];
}

/** `AM-230`: one question the assistant asks before reviewing several documents. */
export interface DealQuestion {
  id: string;
  text: string;
  /** What in the advice depends on the answer — said beside the question. */
  why: string;
  options: { value: string; label: string }[];
  default: string | string[];
  multiple: boolean;
  /** Written by the model from these documents (the others are always asked). */
  proposed?: boolean;
}

/** `AM-229`: a row's status — the engine's action and the reader's answers, never the AI's. */
export type DealStatus = "MUST_CHANGE" | "ASK_CHANGE" | "LEGAL_DECIDES" | "AGREED" | "FINE";

export interface DealCell {
  finding_id: string;
  classification: string;
  status: DealStatus;
  action: string | null;
  quote: string;
  clause: string | null;
  page: number | null;
  /** The client changed this clause (a tracked change). */
  changed: boolean;
  /** `AM-232`: the clause in plain words; absent when it did not pass the figure check. */
  plain?: string;
  proposal?: CounterProposal;
}

export interface DealRow {
  code: string;
  topic: string | null;
  detail: string | null;
  /** Our rule: the Constitution section, topic, and value (omitted without the permission). */
  rule: { section?: string; topic?: string; value?: unknown };
  cells: Record<string, DealCell>;
  status: DealStatus;
  /** What the row asks of the reader: its status or a worse one another file has. */
  needs: DealStatus;
  decided_by: string | null;
  also: { file: string; status: DealStatus; action: string | null }[];
  note?: string | null;
}

export interface DealFile {
  id: string;
  name: string;
  refused: string | null;
  /** `AM-236`: the pages a partial read could not recover (never reviewed). */
  unread?: number[];
  signed: boolean;
  wins: boolean;
  changes: number;
  notes: { clause: string; author?: string; text: string }[];
  precedence: string[];
  unchecked: { section: string; title: string; clause: string; kind: string;
               removed: string; added: string }[];
}

/** `AM-231`: a turn's stored payload — the assistant's questions, or the review. */
export type DealPayload =
  | { kind: "questions"; questions: DealQuestion[] }
  | { kind: "deal_review"; files: DealFile[]; rows: DealRow[]; wins: string | null;
      counts: Record<DealStatus, number>; answers: Record<string, unknown>;
      /** `AM-236`: one contract, shown as a lawyer's memo. */
      single?: boolean;
      /** `AM-236`: the reader asked for a shape (bullets, short, table) — it leads and
       *  the memo waits behind "Show the full review". */
      collapsed?: boolean };

export interface AskResult {
  /** `AM-231`: the assistant's questions or a side-by-side review (several files). */
  payload?: DealPayload;
  conversation_id: string;
  message_id: string;
  /** The question this answers, by its own id — what an edit names (`AM-134`). */
  question_message_id?: string | null;
  answer_state: AssistAnswerState;
  text: string;
  routed_to_evaluator: boolean;
  /** `AM-76` r2 — the reader asked for the source's own words ("the exact wording",
   *  "quote the clause"), so the quote below is the answer and opens by default
   *  instead of sitting collapsed. Decided server-side, deterministically. */
  exact_text_requested?: boolean;
  /** `AM-76` r2/r4 — the quote IS the answer: asked for, or fallen back to because
   *  no paraphrase verified. `text` then only points at the quote, so it must be
   *  rendered open. Wider than `exact_text_requested` — never substitute one. */
  quote_is_the_answer?: boolean;
  /** Which authorized sources were candidates for this question (2026-09-08). */
  domains?: string[];
  comparison?: AssistComparison | null;
  positions?: AssistPosition[];
  statutes?: AssistStatuteAnswer | null;
  /** The document version this answer was read from — STATED by the server, never
   *  inferred here. A conversation is contract-scoped, so it can hold turns from
   *  more than one version, and an answer's `evidence_id`s only highlight on the
   *  version they came from. Null on a document-less (statute) conversation. */
  document_version_id: string | null;
  version_number: number | null;
  citations: AssistCitation[];
  /** The agent path's cited records, one per Sources-legend key. */
  sources?: AskSource[];
  /** The asked topic's standards (`AM-156`): findings under the answer stay on it. */
  topic_requirements?: string[];
  /** Who answered and how long it took, from the answer row (null: a fixed reply). */
  answered_by?: AnsweredBy | null;
  latency_ms?: number | null;
}

/** A cited record behind one key of the answer's Sources legend ("D58", "P4") — what
 *  the reader opens to see where a sentence came from (owner's manager, 2026-10-07).
 *  Only records the reader may read are ever sent; the others are absent (SEC-07). */
export interface AskSource {
  key: string;
  kind: "document" | "position" | "constitution" | "statute" | "material";
  location: string | null;
  /** "the selected document", "MSA agreements only" — live only. */
  scope?: string;
  /** The record's own words, as the answer cited them. */
  text: string;
  /** On reload: the source has changed since the answer; its current text is shown. */
  state?: "stale";
  /** A clause of a contract: where to open it in the document. */
  evidence_id?: string;
  document_version_id?: string;
  /** A document clause's page, and how its text was recovered when not native
   *  ("OCR" | "TABLE") — absent otherwise (F8, LOC-1). */
  page?: number;
  read_by?: string;
}

/** The model that wrote an answer, as the reader names it and as the provider does. */
export interface AnsweredBy {
  label: string;
  model: string;
}

/** One piece of material in a chat (Ask plan 1.2) — what `GET
 *  /conversations/{id}/attachments` returns. Read-only here; never a Contract. */
export interface ChatAttachment {
  id: string;
  kind: "PASTE" | "FILE";
  filename: string | null;
  mime_type: string;
  byte_size: number;
  status: "PROCESSING" | "READY" | "FAILED" | "UNAVAILABLE";
  failure_code: string | null;
  created_at: string;
  expires_at: string;
  /** A READY file read in part: the pages that could not be read (F7). */
  pages_unread?: number[];
}

export interface Conversation {
  id: string;
  contract_id: string | null;
  /** The chat's own model (`AM-122`); null until one is chosen. */
  model?: string | null;
}

/** One row of `GET /ask/models` (`AM-116`): what the composer may offer, and whether
 *  the server can actually serve it. */
export interface AskModel {
  id: string;
  label: string;
  default: boolean;
  configured: boolean;
  /** The provider stopped serving us — credit or quota (`AM-222`). */
  paused?: boolean;
  /** Why and since when — sent to a platform administrator only. */
  paused_reason?: { kind: "payment" | "quota" | "not_configured"; since: string | null };
}

/** One row of `GET /conversations` — the caller's own history, newest first. */
export interface ConversationSummary {
  id: string;
  contract_id: string | null;
  /** The chat's own model (`AM-122`); null until one is chosen. */
  model?: string | null;
  created_at: string | null;
  message_count: number;
  first_question: string | null;
  /** The reader's own name for the chat (`AM-116`); null until renamed. */
  title?: string | null;
  /** Served with the conversation since 2026-09-04 — see the Reviews payload's
   *  note; the per-row `GET /contracts/{id}` this replaces 404'd for any
   *  soft-deleted document and rendered a raw UUID. */
  document_name?: string | null;
  document_accessible?: boolean;
}

/** One turn of a replayed conversation (`GET /conversations/{id}`). */
export interface ConversationTurn {
  id: string;
  ordinal: number;
  role: "USER" | "ASSISTANT";
  content: string;
  answer_state: AssistAnswerState | null;
  routed_to_evaluator: boolean;
  /** `AM-226` r7 — on a question, the files saved with it (omitted when none). */
  attachments?: ChatAttachment[];
  /** `AM-231` — the turn's questions or review, or the reader's answers. */
  payload?: DealPayload | { answers: Record<string, string | string[]> };
  /** `AM-149` — on a routed turn, the clause its question quoted (recomputed). */
  clause?: AssistClauseScope | null;
  /** Which version this turn was answered from. Null on a question turn, and on
   *  an answer that never retrieved (a compliance-shaped question routed to the
   *  evaluator) — reporting a version there would be a fabrication. */
  document_version_id: string | null;
  version_number: number | null;
  /** `AM-25` r5 — the SAME citations the live answer carried. `[]` on refusals. */
  citations: AssistCitation[];
  positions?: AssistPosition[];
  /** `AM-76` r2/r4 on replay — the turn's content points at the quote instead of
   *  being an answer, so the quote must render open here as it did live. */
  quote_is_the_answer?: boolean;
  statutes?: AssistStatuteAnswer | null;
  /** A live turn only: the reader asked for the exact wording, so the quoted text
   *  opens rather than sitting behind "Show exact wording" (as in the dock). */
  exact_text_requested?: boolean;
  /** A live turn only: the evaluator's Findings a routed comparison hands off to. */
  comparison?: AssistComparison | null;
  sources?: AskSource[];
  /** The asked topic's standards (`AM-156`): findings under the answer stay on it. */
  topic_requirements?: string[];
  answered_by?: AnsweredBy | null;
  latency_ms?: number | null;
}

export interface ConversationDetail {
  id: string;
  contract_id: string | null;
  /** The chat's own model (`AM-122`): what the composer shows on reopening. */
  model?: string | null;
  messages: ConversationTurn[];
}

/** One version's text for a clause, as the comparison reports it.
 *
 *  The excerpt is a WINDOW, centred by the server on the point the two versions
 *  diverge rather than taken from the top of the clause — a prefix would hide a
 *  change that sits 900 characters in and present two identical-looking
 *  excerpts under a heading saying the wording changed. The truncation flags
 *  say when text was cut, because an excerpt that hides its own truncation
 *  makes a claim about completeness it cannot support. */
export interface ClauseSide {
  evidence_id: string;
  page_number: number | null;
  excerpt: string;
  truncated_start: boolean;
  truncated_end: boolean;
}

/** One clause as `GET /contracts/{id}/version-comparison` reports it.
 *
 *  33.16 is visible in the SHAPE: there is no verdict, acceptability or
 *  approval field, and `status` describes what happened to the TEXT, never what
 *  Legal should do about it. `findings` quotes Findings the evaluator already
 *  produced against a pinned snapshot; a comparison never creates one. */
export interface ClauseChange {
  status: "ADDED" | "REMOVED" | "CHANGED" | "UNCHANGED";
  section_number: string | null;
  section_title: string | null;
  before: ClauseSide | null;
  after: ClauseSide | null;
  findings: { finding_id: string; classification: string; user_status?: UserStatusWord; requirement_code: string | null }[];
}

export interface VersionComparison {
  before: { document_version_id: string; version_number: number };
  after: { document_version_id: string; version_number: number };
  summary: { ADDED: number; REMOVED: number; CHANGED: number; UNCHANGED: number };
  /** Text with no clause number of its own — counted, never paired by guesswork. */
  unnumbered: { unchanged: number; added: number; removed: number };
  /** Stated by the server so the reader knows how the two sides were aligned. */
  matched_on: string;
  clauses: ClauseChange[];
}

/** One side of a Diff-Talk row: a clause as that document numbers and words it. */
export interface ComparedClause {
  /** Stable across reloads — a choice is kept against it. */
  id: string;
  ref: string | null;
  title: string | null;
  text: string;
  /** Stored documents only: the evidence rows the clause was read from. */
  evidence_ids?: string[];
  page?: number | null;
}

/** A website document Diff-Talk can compare (a CURRENT published copy). */
/** Diff-Talk's choices for one compared pair, kept by LegalMind (AB-81 / AM-136):
 *  shared by everyone who can read both documents, last writer wins. */
export interface ComparisonChoice {
  choice: "ours" | "theirs";
  /** Who made it — shown when it was not the reader. */
  decided_by: string;
  decided_by_me: boolean;
  updated_at: string;
}
export interface ComparisonChoices {
  /** Whether THIS reader may change them (the owner of every stored side). */
  can_choose: boolean;
  /** By difference (`rowKey`). */
  choices: Record<string, ComparisonChoice>;
}

export interface WebsiteDocument {
  key: string;
  title: string;
  url: string;
  version: string;
  effective_from: string;
}

export type ComparedDocument =
  | ({ kind: "WEBSITE" } & WebsiteDocument)
  | { kind: "DOCUMENT"; title: string; contract_id: string; document_version_id: string;
      version_number: number; filename: string;
      /** Pages with no readable text — often blank, sometimes a scan. */
      unread_pages: number[] };

/** Diff-Talk (owner, 2026-10-12): two documents side by side. Statuses describe the
 *  WORDING only — never acceptability. */
export interface DocumentComparison {
  left: ComparedDocument;
  right: ComparedDocument;
  summary: { UNCHANGED: number; CHANGED: number; ADDED: number; REMOVED: number;
             MOVED: number };
  clauses: {
    /** ADDED = right only, REMOVED = left only. */
    status: "UNCHANGED" | "CHANGED" | "ADDED" | "REMOVED";
    /** Paired, but out of the left document's order. */
    moved: boolean;
    left: ComparedClause | null;
    right: ComparedClause | null;
  }[];
}

/** `AM-152` — one business consequence of an actionable Finding, in fixed words from the
 *  document's own figures; `money` absent when the document states no figure for it. */
export interface BusinessPoint {
  finding_id: string;
  decided?: boolean;
  requirement_code: string;
  headline: string;
  body: string | null;
  money: string | null;
  rupees: number | null;
  /** A risk to weigh (ranked), or information only — never ranked by ₹ (`AM-156` R7). */
  risk?: boolean;
  where: string | null;
  evidence_ids?: string[];
  /** The Constitution's own words on enforcing this term, or "Counsel to confirm
   *  enforceability" (`AM-159`); never an assertion that it is enforceable. */
  enforceability?: EnforceabilityNote | null;
}

/** `AM-159` — a verbatim Constitution sentence and its section (null: no text). */
export interface EnforceabilityNote {
  section: string | null;
  text: string;
}

/** One finding a person must act on, with the clauses it read (`AM-152`). */
export interface LegalItem {
  finding_id: string;
  /** AM-179 — the point, and whether a person has decided it (server-built). */
  group_id?: string;
  decided?: boolean;
  requirement_code: string;
  title: string;
  classification: string;
  waived: boolean;
  /** What to do, in the Constitution's terms (`AM-156`) — built by the server. */
  action?: string;
  where: string | null;
  evidence_ids: string[];
  enforceability?: EnforceabilityNote | null;
  /** The other clauses of this finding's group, verbatim (Step 2, 2026-10-21). */
  related?: RelatedClause[];
  /** The finding as a careful reviewer states it — built by the server (Step 3). */
  case?: FindingCase;
}

/** A clause read together with a finding: leaving and what it costs; a cap and what it
 *  excludes. Context for a person, never a verdict. */
export interface RelatedClause {
  evidence_id: string;
  clause: string | null;
  page: number | null;
  text: string;
  relation: string;
}

/** One finding's case (owner, 2026-10-21): the contract's words, our standard and its
 *  source (value and source only with `legal_position.view` — omitted, never nulled),
 *  the gap in one line, the impact the figures support, the related clauses, and the
 *  RECOMMENDED action — a recommendation, never a decision, and never "Reject". */
export interface FindingCase {
  contract: { quote: string; clause: string | null; page: number | null } | null;
  standard: {
    section: string | null;
    topic: string | null;
    value?: string | null;
    source?: { label: string; quote: string };
  };
  gap: string;
  business: { headline: string; body: string | null; money: string | null } | null;
  related: RelatedClause[];
  recommendation: string;
}

/** Who a Review was sent to (AB-100), and — for its owner — who it may be sent to. */
export interface ReviewerPerson {
  user_id: string;
  name: string | null;
  email: string;
}

export interface ReviewAssignments {
  assigned: Array<ReviewerPerson & { assigned_by: string; assigned_at: string }>;
  /** The owner, on a contract not archived — the one who sends and withdraws. */
  can_send: boolean;
  eligible: ReviewerPerson[];
}

/** `AM-152` — the Constitution's own drafting language (or its company position where it
 *  has none) for a deviating finding's section, quoted verbatim, labelled as it is. */
export interface CounterProposal {
  section: string;
  kind: "DRAFTING_LANGUAGE" | "COMPANY_POSITION";
  label: string;
  text: string;
}

/** `GET /reviews/{id}/angles` — the ⚖️ Legal and 💼 Business angles (`AM-152`). */
export interface ReadingItem {
  category: string;
  text: string;
  quote: string;
  evidence_id: string;
  clause: string | null;
  /** A Finding already reads this clause. */
  with_finding: boolean;
}

export interface ReviewAngles {
  commercial: {
    fee_per_month: number | null;
    fee_text: string | null;
    term_months: number | null;
    term_text: string | null;
    committed_value: number | null;
    committed_value_text: string | null;
    excludes_gst?: boolean;
    /** Why no contract value is shown, in the reader's words (`AM-156` R1). */
    missing?: string | null;
  };
  business: BusinessPoint[];
  top_risks: BusinessPoint[];
  legal: { actionable: number; matching: number; items?: LegalItem[] };
  /** The lawyer's second read (`AM-162`): each item verified in code — a verbatim quote
   *  from a real clause — and shown in the checklist's fixed words, never a Finding.
   *  Absent when the document was never read. */
  reading?: { label: string; items: ReadingItem[] };
  counter_proposals: Record<string, CounterProposal>;
  /** What a careful reader notices across the document — never a Finding (`AM-159`). */
  observations?: { structural: Observation[]; additional: Observation[] };
  /** One line computed from the actions: a recommendation a person decides on (`AM-160`). */
  recommendation?: string | null;
  /** A marked-up contract's tracked changes, counted (owner, 2026-10-27); absent when
   *  the document carries none. The full list is the report's. */
  client_changes?: { changes: number; clauses: number; measured: number;
                     unmeasured: number; notes: number;
                     /** `AM-224` — changed clauses that move risk onto LeapSwitch */
                     onto?: number };
}

/** `AM-159` — a document-level observation: its clauses, fixed words, the Constitution's
 *  basis quoted verbatim (null where it states none), and what a person does with it. */
export interface Observation {
  kind: string;
  clauses: string[];
  evidence_ids: string[];
  text: string;
  /** Omitted for a reader without the positions permission (SEC-07). */
  basis?: { section: string; quote: string } | null;
  action?: string | null;
}

/** AM-179 (owner, 2026-10-22) — where a review stands, derived by the server from what
 *  is recorded; every screen shows this, never its own count. Not one of the five axes. */
export type ReviewStage =
  | "SUPERSEDED" | "ANALYSING" | "ANALYSIS_FAILED" | "WAITING_FOR_CLARIFICATION"
  | "REOPENED" | "WITH_LEGAL" | "NOT_SENT" | "CONTRACT_DECISION_PENDING" | "COMPLETE"
  | "NO_ISSUES";

export interface ReviewProgress {
  stage: ReviewStage;
  outcome: ContractOutcome | null;
  superseded_by: number | null;
  reopened_at: string | null;
  /** points (cards), never raw findings */
  total: number;
  required: number;
  to_decide: number;
  clarification: number;
  decided: number;
  no_action: number;
  matches: number;
  decided_by_type: Record<string, number>;
  next: { who: "owner" | "reviewer" | "legal" | null; name: string | null };
  assignee: { name: string; email: string } | null;
}

/** One block of the review report (AB-103) — the same model the PDF/DOCX download
 *  renders, so what a reader previews is what they download. */
export interface ReportBlock {
  /** "change": one tracked change — rows[0] = clause, kind, removed, added, "read" | "". */
  kind: "h1" | "h2" | "h3" | "p" | "kv" | "quote" | "note" | "bullet" | "table" | "change"
    | "risk";
  text: string;
  label: string;
  rows: string[][];
}

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
  session_id?: string;
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
}

export interface LatestVersionSummary {
  id: string;
  version_number: number;
  processing_status: string;
}

export interface Contract {
  /** Newest first. Present on the detail endpoint (2026-08-30 addition). */
  document_versions?: DocumentVersion[];
  /** List rows only (2026-08-31): the newest version and its newest Review. */
  latest_version?: LatestVersionSummary | null;
  latest_analysis?: LatestAnalysis | null;
  id: string;
  owner_id: string;
  name: string;
  contract_type: string | null;
  status: string;
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
  uploaded_by: string;
  created_at: string | null;
  /** Counts, deliberately not a state vocabulary (`AM-29` r1): the client derives
   * ready / lexical-only / not-indexed. Present on the detail endpoint. */
  assist_index?: { chunks: number; embedded_chunks: number };
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
  version_number: number;
  /** Step 31 r20 — the current version is the highest; the rest are superseded. */
  is_current: boolean;
  created_at: string | null;
}

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
}

export interface Finding {
  id: string;
  review_id: string;
  requirement: {
    code: string | null;
    name: string | null;
    version_id: string;
    version_number: number | null;
  };
  /**
   * 49.7 r1 — a **derived, non-authoritative summary**. The API never returns it
   * without `evaluations`, and the UI never shows it without them (52.5).
   */
  classification: string;
  status: string;
  requires_decision: boolean;
  escalated: boolean;
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

export interface ReviewReport {
  review_id: string;
  review_status: string;
  coverage: {
    requirements_in_snapshot: number;
    requirements_with_findings: number;
  };
  classification_counts: Record<string, number>;
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
  action: string;
  entity_type: string;
  entity_id: string | null;
  timestamp: string | null;
  request_id: string | null;
  /** Gated behind `legal_position.view` — omitted, not nulled (Step 24 r8). */
  before_state?: unknown;
  after_state?: unknown;
}

// ---------------------------------------------------------- administration
export interface User {
  id: string;
  email: string;
  name: string;
  status: string;
  roles: string[];
  created_at: string | null;
}

export interface Role {
  id: string;
  code: string;
  name: string;
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

export interface AskResult {
  conversation_id: string;
  message_id: string;
  answer_state: AssistAnswerState;
  text: string;
  routed_to_evaluator: boolean;
  /** The document version this answer was read from — STATED by the server, never
   *  inferred here. A conversation is contract-scoped, so it can hold turns from
   *  more than one version, and an answer's `evidence_id`s only highlight on the
   *  version they came from. */
  document_version_id: string;
  version_number: number;
  citations: AssistCitation[];
}

export interface Conversation {
  id: string;
  contract_id: string | null;
}

/** One row of `GET /conversations` — the caller's own history, newest first. */
export interface ConversationSummary {
  id: string;
  contract_id: string | null;
  created_at: string | null;
  message_count: number;
  first_question: string | null;
}

/** One turn of a replayed conversation (`GET /conversations/{id}`). */
export interface ConversationTurn {
  id: string;
  ordinal: number;
  role: "USER" | "ASSISTANT";
  content: string;
  answer_state: AssistAnswerState | null;
  routed_to_evaluator: boolean;
  /** Which version this turn was answered from. Null on a question turn, and on
   *  an answer that never retrieved (a compliance-shaped question routed to the
   *  evaluator) — reporting a version there would be a fabrication. */
  document_version_id: string | null;
  version_number: number | null;
  /** `AM-25` r5 — the SAME citations the live answer carried. `[]` on refusals. */
  citations: AssistCitation[];
}

export interface ConversationDetail {
  id: string;
  contract_id: string | null;
  messages: ConversationTurn[];
}

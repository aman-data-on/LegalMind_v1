/**
 * The API client — the **only** data path in this application.
 *
 * Locked 38.22 / 52.1 r1: the frontend never touches the database. All data
 * comes from `/api/v1/`. The external reference's pattern of pages calling
 * data-access functions directly was rejected as C-EXT-1, so there is
 * deliberately no database client, no ORM and no connection string anywhere in
 * `frontend/` — this module is the whole surface, and every screen goes through
 * it.
 *
 * Locked 43.23: authorization happens on the server. Nothing here decides
 * whether a caller may do something; a 401/403/404 is a *result*, not a
 * pre-check.
 */

import type {
  AnalysisSubmission,
  AskResult,
  AuditEvent,
  Conversation,
  ConversationDetail,
  ConversationSummary,
  ConfigurationSnapshot,
  Contract,
  ContractsSummary,
  DataEnvelope,
  Decision,
  DocumentVersion,
  Escalation,
  Evaluation,
  Finding,
  Pagination,
  PaginatedEnvelope,
  Requirement,
  Review,
  ReviewReport,
  Role,
  SessionIdentity,
  ObligationsResult,
  SnapshotSummary,
  TypeSuggestion,
  UploadResult,
  User,
} from "./types";

import type { EvidenceRow } from "./types";

export const API_BASE = "/api/v1";

const CSRF_COOKIE = "legalmind_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const UNSAFE = new Set(["POST", "PATCH", "DELETE"]);

/**
 * A failed request, carrying the locked 49.5 error taxonomy.
 *
 * `requestId` is surfaced to the user because 49.9 makes it the correlation
 * anchor: quoting it is what lets an operator find the request in the audit
 * trail without the user having to describe what happened.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string,
    readonly fields?: { field: string; code: string }[],
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** 401 — no valid session (47.7). */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** 403 — the object is visible; the operation permission is absent (47.7). */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /**
   * 404 — out of scope **or** nonexistent, indistinguishably (49.5 r1).
   * Step 52.4: the UI must render both identically. Never phrase this as
   * "you do not have access to X" — that would restore the disclosure the
   * byte-identical response exists to prevent.
   */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /**
   * 409 — a decision version collision (49.7). Step 52.7 forbids optimistic UI
   * for Legal Decisions precisely because this is a real and meaningful outcome.
   */
  get isConflict(): boolean {
    return this.status === 409;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${CSRF_COOKIE}=`));
  return match ? decodeURIComponent(match.slice(CSRF_COOKIE.length + 1)) : null;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Raw bytes for the upload endpoint, which takes the file as the body. */
  raw?: { data: BodyInit; contentType: string; filename: string };
  query?: Record<string, string | number | undefined>;
  /** 49.8 — echoed as `Idempotency-Key`; a repeat must not duplicate the effect. */
  idempotencyKey?: string;
  signal?: AbortSignal;
}

function url(path: string, query?: RequestOptions["query"]): string {
  const target = `${API_BASE}${path}`;
  if (!query) return target;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${target}?${qs}` : target;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (UNSAFE.has(method)) {
    // S-3 — double-submit CSRF. The session cookie is HttpOnly and travels
    // automatically; this header is the half a cross-origin caller cannot forge.
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
  }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let body: BodyInit | undefined;
  if (options.raw) {
    body = options.raw.data;
    headers["Content-Type"] = options.raw.contentType;
    // HTTP header values are restricted to ISO-8859-1 bytes (0-255) — `fetch`
    // enforces this by throwing synchronously, before any request is sent, the
    // moment a header value contains a character outside that range. Found
    // 2026-09-03: a real filename containing an en dash ("NON – DISCLOSURE")
    // threw here, so the upload never reached the network at all — no request
    // ever logged server-side, and the caller saw only the generic fallback
    // error from `describeError`'s catch-all, because the thrown TypeError
    // isn't an ApiError. Any non-ASCII filename (not just this one character)
    // carries the same risk. `encodeURIComponent` keeps the value pure ASCII
    // (so it can never fail this way) while staying reversible; the server
    // decodes it back to the real filename (see `upload_document_version`).
    headers["X-Filename"] = encodeURIComponent(options.raw.filename);
  } else if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url(path, options.query), {
    method,
    headers,
    // Same-origin in production and behind the dev rewrite, so the Secure /
    // SameSite=Strict session cookie is sent without weakening any attribute.
    credentials: "same-origin",
    ...(body !== undefined ? { body } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });

  if (response.status === 204) return undefined as T;

  const requestId = response.headers.get("X-Request-Id") ?? "-";

  if (!response.ok) throw await toApiError(response, requestId);

  if (response.headers.get("Content-Type")?.includes("application/json")) {
    const parsed = (await response.json()) as DataEnvelope<T>;
    return parsed.data;
  }
  return undefined as T;
}

interface ErrorBody {
  code: string;
  message: string;
  request_id: string;
  fields?: { field: string; code: string }[];
}

async function toApiError(response: Response, requestId: string): Promise<ApiError> {
  let code = "ERROR";
  let message = "The request failed.";
  let fields: { field: string; code: string }[] | undefined;
  try {
    const parsed = (await response.json()) as { error?: ErrorBody };
    if (parsed.error) {
      code = parsed.error.code;
      message = parsed.error.message;
      fields = parsed.error.fields;
    }
  } catch {
    // A non-JSON body means something outside the API answered — a proxy or a
    // network failure. The locked envelope still governs what the user sees.
  }
  return new ApiError(response.status, code, message, requestId || "-", fields);
}

async function requestPage<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ items: T[]; pagination: Pagination }> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (UNSAFE.has(method)) {
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
  }
  const response = await fetch(url(path, options.query), {
    method,
    headers,
    credentials: "same-origin",
    ...(options.signal ? { signal: options.signal } : {}),
  });
  const requestId = response.headers.get("X-Request-Id") ?? "-";
  if (!response.ok) throw await toApiError(response, requestId);
  const parsed = (await response.json()) as PaginatedEnvelope<T>;
  return { items: parsed.data, pagination: parsed.pagination };
}

// =========================================================================
// Endpoints. One function per locked 49.3 row; nothing else exists.
// =========================================================================
export const api = {
  // ---- 49.2 authentication ---------------------------------------------
  login: (email: string, password: string) =>
    request<SessionIdentity>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  session: () => request<SessionIdentity>("/auth/session"),
  logout: () => request<{ revoked: boolean }>("/auth/logout", { method: "POST" }),

  // ---- assist lane (AB-3/AB-4) -------------------------------------------
  createConversation: (contractId: string) =>
    request<Conversation>("/conversations", {
      method: "POST",
      body: { contract_id: contractId },
    }),
  /** Ask about ONE document version — the one the reader has open.
   *
   *  `documentVersionId` is not a convenience: an answer's citations carry
   *  `evidence_id`s belonging to exactly one version's reading order, so asking
   *  without naming the open version is how an answer ends up pointing at a
   *  passage that is not on the page. The server still defaults to the newest
   *  version when it is omitted. */
  ask: (conversationId: string, question: string, documentVersionId?: string) =>
    request<AskResult>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: documentVersionId
        ? { question, document_version_id: documentVersionId }
        : { question },
    }),
  /** The caller's own conversations — the server scopes to `user_id`, so this can
   *  never list someone else's questions (`AM-25` r7). */
  conversations: (query: { page?: number; page_size?: number; contract_id?: string } = {}) =>
    requestPage<ConversationSummary>("/conversations", { query }),
  conversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),

  // ---- contracts & documents -------------------------------------------
  contracts: (
    page = 1,
    pageSize = 25,
    filters: {
      q?: string | undefined;
      contract_type?: string | undefined;
      status?: string | undefined;
      sort?: string | undefined;
    } = {},
  ) =>
    requestPage<Contract>("/contracts", {
      query: { page, page_size: pageSize, ...filters },
    }),
  /** Real counts across EVERY contract the caller owns, not just the current
   *  page — the same bucket the list's own `?status=` filters on (server:
   *  `_status_bucket`), so a tile and a row can never disagree. */
  contractsSummary: () => request<ContractsSummary>("/contracts/summary"),
  contract: (id: string) => request<Contract>(`/contracts/${id}`),
  createContract: (name: string, contractType?: string) =>
    request<Contract>("/contracts", {
      method: "POST",
      body: contractType ? { name, contract_type: contractType } : { name },
    }),
  updateContract: (id: string, patch: Record<string, unknown>) =>
    request<Contract>(`/contracts/${id}`, { method: "PATCH", body: patch }),

  /**
   * Delete one contract — owner approval 2026-09-01, closing the gap `AM-31`
   * left open.
   *
   * `mode` reports what the server actually did, and the caller must say so
   * rather than assuming: a contract that was never analyzed is destroyed
   * (`"hard"`), while one carrying a Review is withdrawn from every view with
   * its findings and audit trail preserved (`"soft"`) — rule 17 keeps history
   * reproducible. Telling a user "permanently deleted" when the server soft-
   * deleted would be a lie about legal records.
   */
  deleteContract: (id: string) =>
    request<{ deleted: boolean; mode: "hard" | "soft" }>(
      `/contracts/${id}`, { method: "DELETE" }),

  /**
   * The body **is** the file. Locked 34.16 treats the declared content type as a
   * claim; the server sniffs the magic bytes and rejects a mismatch, so nothing
   * here needs to (or may) decide whether a file is acceptable.
   */
  uploadDocument: (contractId: string, file: File) =>
    request<UploadResult>(`/contracts/${contractId}/document-versions`, {
      method: "POST",
      raw: {
        data: file,
        contentType: file.type || "application/octet-stream",
        filename: file.name,
      },
    }),
  documentVersion: (id: string) => request<DocumentVersion>(`/document-versions/${id}`),
  /**
   * Assist-lane type suggestion (owner, 2026-08-31) — a proposal for the intake
   * screen's pre-fill, never a write: the type is recorded only by the user's
   * own confirm (PATCH). `confident: false` means "behave as before this
   * feature existed" — an empty select the user fills in.
   */
  suggestType: (documentVersionId: string) =>
    request<TypeSuggestion>(`/document-versions/${documentVersionId}/suggest-type`, {
      method: "POST",
    }),
  /** Key Obligations (assist lane): descriptive facts about the document's own
   *  text, grouped by its own role labels — never a Finding or a judgment. */
  obligations: (documentVersionId: string) =>
    request<ObligationsResult>(`/document-versions/${documentVersionId}/obligations`),
  extractObligations: (documentVersionId: string) =>
    request<{ extracted: boolean; error_code: string | null }>(
      `/document-versions/${documentVersionId}/extract-obligations`,
      { method: "POST" },
    ),
  /** Evidence rows in reading order — the document pane and every citation target. */
  documentEvidence: (id: string, page = 1, pageSize = 100) =>
    requestPage<EvidenceRow>(`/document-versions/${id}/evidence`, {
      query: { page, page_size: pageSize },
    }),
  documentContentUrl: (id: string) => `${API_BASE}/document-versions/${id}/content`,
  /**
   * The preserved original bytes (34.5), as a Blob for in-app rendering. The
   * endpoint serves `Content-Disposition: attachment`, which is right for a
   * navigation but irrelevant to a fetch — the caller turns the Blob into an
   * object URL and hands it to the browser's own PDF renderer. Requires
   * `document.download` server-side, exactly like the download it is.
   */
  documentContentBlob: async (id: string): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/document-versions/${id}/content`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new ApiError(response.status, "download_failed",
        "The original document could not be loaded.",
        response.headers.get("X-Request-Id") ?? "-");
    }
    return response.blob();
  },

  // ---- reviews ----------------------------------------------------------
  reviews: (query: { page?: number; page_size?: number; status?: string; contract_id?: string } = {}) =>
    requestPage<Review>("/reviews", { query }),
  review: (id: string) => request<Review>(`/reviews/${id}`),
  createReview: (documentVersionId: string, configurationSnapshotId: string) =>
    request<Review>("/reviews", {
      method: "POST",
      body: {
        document_version_id: documentVersionId,
        configuration_snapshot_id: configurationSnapshotId,
      },
    }),
  /**
   * Submit the Review for analysis. Progress afterwards is read from the Review's
   * lifecycle status and nothing else (52.7) — there is deliberately no separate
   * job-state resource that could disagree with Step 30.
   *
   * Two outcomes, distinguished by `mode` (locked 55.1): `queued` when a worker will
   * run it, `inline` when it already ran. The caller reloads the Review either way,
   * so the difference is in what the response can report, not in what it means.
   *
   * A repeat returns `already_analysed` rather than duplicating Findings (49.8).
   */
  analyzeReview: (reviewId: string, idempotencyKey?: string) =>
    request<AnalysisSubmission>(`/reviews/${reviewId}/analyze`, {
      method: "POST",
      ...(idempotencyKey ? { idempotencyKey } : {}),
    }),
  findings: (
    reviewId: string,
    query: { page?: number; page_size?: number; classification?: string; status?: string } = {},
  ) => requestPage<Finding>(`/reviews/${reviewId}/findings`, { query }),
  report: (reviewId: string) => request<ReviewReport>(`/reviews/${reviewId}/report`),

  /** 49.3's export row (formats per the owner's 2026-08-31 directive). Returns
   *  the rendered file; the caller hands it to the browser as a download. */
  exportReview: async (reviewId: string, format: "pdf" | "docx") => {
    const headers: Record<string, string> = {};
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
    headers["Content-Type"] = "application/json";
    const response = await fetch(url(`/reviews/${reviewId}/export`), {
      method: "POST",
      headers,
      credentials: "same-origin",
      body: JSON.stringify({ format }),
    });
    if (!response.ok) {
      throw await toApiError(response, response.headers.get("X-Request-Id") ?? "-");
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename =
      /filename="([^"]+)"/.exec(disposition)?.[1] ?? `analysis.${format}`;
    return { blob: await response.blob(), filename };
  },

  // ---- findings & escalation -------------------------------------------
  finding: (id: string) => request<Finding>(`/findings/${id}`),
  evaluations: (findingId: string) =>
    request<Evaluation[]>(`/findings/${findingId}/evaluations`),
  escalate: (findingId: string, reason: string) =>
    request<{ escalation: Escalation; finding: Finding }>(
      `/findings/${findingId}/escalate`,
      { method: "POST", body: { reason } },
    ),
  withdrawEscalation: (findingId: string) =>
    request<Finding>(`/findings/${findingId}/escalate`, { method: "DELETE" }),

  // ---- decisions -------------------------------------------------------
  /**
   * Targets an **Evaluation**. There is no Finding-level equivalent, because a
   * decision resolves exactly one Evaluation and must never implicitly dispose
   * of another under the same Finding (AB-1.1, 49.7).
   *
   * There is no update function either: supersession is a create (Step 31 r14).
   */
  recordDecision: (
    evaluationId: string,
    payload: {
      decision_type: string;
      justification: string;
      expected_version?: number;
      requires_second_person?: boolean;
    },
  ) =>
    request<{
      decision: Decision;
      finding_status: string;
      is_effective: boolean;
      review_status: string;
    }>(`/evaluations/${evaluationId}/decisions`, { method: "POST", body: payload }),
  decisions: (evaluationId: string) =>
    request<Decision[]>(`/evaluations/${evaluationId}/decisions`),

  // ---- configuration ---------------------------------------------------
  requirements: (query: { page?: number; page_size?: number; status?: string } = {}) =>
    requestPage<Requirement>("/requirements", { query }),
  requirement: (id: string) => request<Requirement>(`/requirements/${id}`),
  createRequirement: (code: string) =>
    request<Requirement>("/requirements", { method: "POST", body: { code } }),
  createRequirementVersion: (requirementId: string, body: Record<string, unknown>) =>
    request<Requirement>(`/requirements/${requirementId}/versions`, {
      method: "POST",
      body,
    }),
  /**
   * Change a Company Standard's values. APPEND-ONLY (locked rule 16): the server
   * creates a new Requirement version carrying the previous mapping, evaluation and
   * Legal Rule artifacts forward unchanged. `reason` is mandatory — a standard
   * change is a change of legal position, and the audit trail records the reason
   * (never the values, 53.3). Rollback is this same call with an older version's
   * values, read back from the detail response.
   */
  updateCompanyStandard: (
    requirementId: string,
    payload: { company_standard: Record<string, unknown>; reason: string },
  ) =>
    request<Requirement>(`/requirements/${requirementId}/standard`, {
      method: "POST",
      body: payload,
    }),
  /** Published snapshots, newest first — metadata only. What "analyze against
   *  the current standards" resolves to (2026-08-31 UX correction). */
  snapshots: (query: { page?: number; page_size?: number } = {}) =>
    requestPage<SnapshotSummary>("/configuration/snapshots", { query }),
  publishConfiguration: (requirementCodes?: string[]) =>
    request<ConfigurationSnapshot>("/configuration/publish", {
      method: "POST",
      body: requirementCodes ? { requirement_codes: requirementCodes } : {},
    }),

  // ---- audit -----------------------------------------------------------
  auditEvents: (
    query: {
      page?: number;
      page_size?: number;
      action?: string;
      entity_type?: string;
      actor_id?: string;
    } = {},
  ) => requestPage<AuditEvent>("/audit-events", { query }),

  // ---- administration --------------------------------------------------
  users: (query: { page?: number; page_size?: number; status?: string; search?: string } = {}) =>
    requestPage<User>("/users", { query }),
  createUser: (email: string, name: string) =>
    request<User>("/users", { method: "POST", body: { email, name } }),
  updateUser: (id: string, patch: Record<string, unknown>) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: patch }),
  deleteUser: (id: string) =>
    request<{ deleted: boolean }>(`/users/${id}`, { method: "DELETE" }),
  grantRole: (userId: string, roleCode: string) =>
    request<User>(`/users/${userId}/roles`, {
      method: "POST",
      body: { role_code: roleCode },
    }),
  revokeRole: (userId: string, roleCode: string) =>
    request<User>(`/users/${userId}/roles/${roleCode}`, { method: "DELETE" }),
  roles: (query: { page?: number; page_size?: number } = {}) =>
    requestPage<Role>("/roles", { query }),
};

/**
 * Human-readable text for a failure, obeying 49.5 and 52.4.
 *
 * A 404 is phrased so it cannot be read as "this exists but is not yours". The
 * server already made the two byte-identical; wording that distinguished them
 * would give back the disclosure at the last step.
 */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.isUnauthenticated) return "Your session has ended. Please sign in again.";
    if (error.isNotFound) return "Not found.";
    if (error.isRateLimited) return "Too many requests. Please try again shortly.";
    return error.message;
  }
  return "The request could not be completed.";
}

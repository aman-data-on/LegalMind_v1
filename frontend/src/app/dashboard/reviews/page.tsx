"use client";

/**
 * Reviews — the queue (P1, PRODUCT_UX_ROADMAP §E screen 7). Scope is entirely
 * server-side: `GET /reviews` returns what REC-09 grants — a user's own and
 * assigned Reviews, plus (for `legal.review` holders) everything escalated or
 * in LEGAL_REVIEW. The page adds no scope logic of its own (rule 18: UI
 * permission gating is presentation only).
 *
 * Queue bias, not urgency theater: rows whose status asks for legal attention
 * carry a filled chip (UI-09: no row stripe without a legend); nothing blinks, nothing counts
 * down. Filters are the API's own allow-list (49.6), one status at a time.
 *
 * Starting a Review is deliberately absent — the snapshot-choice UX is
 * unscoped (slice 2's honest state), so this screen reads the queue and says
 * where Reviews come from rather than faking a creation path.
 *
 * The queue and one Review's report both live at the fixed pathname
 * `/dashboard/reviews`; which one renders is decided by `?id=` rather than a
 * path segment, so no Review id appears in the URL path itself.
 */

import Link from "@/components/AppLink";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { TodoViews } from "@/components/workspace/TodoViews";
import { REVIEWS_QUEUE_COPY as COPY, reviewStatusLabel } from "@/lib/labels";
import { SegmentedFilter } from "@/components/SegmentedFilter";
import { ROLE_WORDS, contractHref } from "@/components/workspace/model";
import { documentTypeChip } from "@/lib/documentTypes";
import type { Pagination, Review } from "@/lib/types";

import { ReviewReportPage } from "@/components/workspace/ReviewReportPage";
import { formatDate } from "@/lib/dates";
import { ErrorState } from "@/components/Feedback";
import { LegalOnly } from "@/components/RetiredFor";
import { PageHeader } from "@/components/page/PageHeader";
import { StackTable } from "@/components/StackTable";

const PAGE_SIZE = 25;

const ATTENTION_STATUSES = new Set(["LEGAL_REVIEW"]);

function ReviewsQueueView() {
  const { can } = useSession();
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // The document name and its reachability arrive WITH each Review
      // (2026-09-04). This used to fetch `GET /contracts/{id}` per row, which is
      // ownership-scoped while this list is Review-scoped — so every row from
      // Legal scope 404'd and rendered a raw UUID.
      const result = await api.reviews({ page, page_size: PAGE_SIZE, ...(status ? { status } : {}) });
      setReviews(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, status]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.REVIEW_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include Review access.</p>
      </div>
    );
  }

  return (
    <div className="lm-page ws-docs--queue">
      {/* the same header and edge as the To-do and Legal tabs beside it (B3 page 2) */}
      <PageHeader title="Reviews" meta={pagination?.total ? <span>{pagination.total} total</span> : null} />
      {/* `--queue` scopes the fixed column widths in workspace.css to this
          four-column table. Without them the columns size to content, and the
          two the visual baseline masks (Document, Created) still drive that
          sizing — so a longer document name in one run moved every column and
          failed job 15 on 7% of pixels with no visible change. */}
      <TodoViews />
        {/* UI-09: the one filter control, in the row chips' own words (Step 30 states) */}
        <SegmentedFilter label={COPY.filter} value={status}
                         onChange={(next) => { setPage(1); setStatus(next); setReviews(null); }}
                         segments={COPY.filters.map((f) => ({ id: f.id, label: f.text, text: f.text }))} />

        {error ? (
          <ErrorState title="Reviews could not be loaded" error={error} onRetry={() => void load()} />
        ) : null}

        {reviews === null && !error ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading reviews…
            </p>
            {[0, 1, 2].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "40%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "14%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "10%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {reviews !== null && reviews.length === 0 ? (
          <div className="ws-state">
            <h2>{COPY.emptyTitle}</h2>
            <p>{status ? COPY.emptyFiltered : COPY.emptyAll}</p>
          </div>
        ) : null}

        {reviews !== null && reviews.length > 0 ? (
          <StackTable columns={[{ label: COPY.columns.document }, { label: COPY.columns.status }, { label: COPY.columns.checked }]}>
                {reviews.map((review) => {
                  const attention = ATTENTION_STATUSES.has(review.status);
                  return (
                    // UI-09: no unexplained row stripe — the status chip says "With Legal"
                    <tr key={review.id} data-review-id={review.id}>
                      {/* The document's name, always — and a link to its
                          workspace only when this caller can actually open it.
                          A Review reachable through Legal scope (`REC-09`)
                          belongs to a Contract that stays ownership-scoped, so
                          linking there unconditionally sent the reader to
                          "Not found." while the Report beside it worked. */}
                      <td>
                        {review.document_accessible ? (
                          <Link href={contractHref(review.contract_id)}>
                            {review.document_name ?? review.contract_id.slice(0, 8)}
                          </Link>
                        ) : (
                          // B3: one link per row — the report, when the document is not open to you
                          <Link href={`/dashboard/reviews?id=${review.id}`} title="Opens the report">
                            {review.document_name ?? review.contract_id.slice(0, 8)}
                          </Link>
                        )}
                        {/* U1 r2: the facts line Contracts uses — what tells one template's rows apart */}
                        <span className="ws-hometable__facts">
                          {[review.client_name, documentTypeChip(review.document_type),
                            review.version_number ? COPY.version(review.version_number, ROLE_WORDS[review.version_role ?? ""]) : null,
                            // who holds it, only while it is with Legal (a closed review keeps no holder)
                            review.status === "LEGAL_REVIEW" && review.assigned_to?.[0] ? COPY.withWhom(review.assigned_to[0]) : null,
                          ].filter(Boolean).map((part) => <span key={part}>{part}</span>)}
                        </span>
                      </td>
                      <td>
                        <span className={`ws-chip${attention ? " lm-lozenge" : ""}`}>
                          {reviewStatusLabel(review.status)}
                        </span>
                      </td>
                      <td className="ws-num">{formatDate(review.created_at) || "—"}</td>
                    </tr>
                  );
                })}
          </StackTable>
        ) : null}

        {pagination && pagination.total > pagination.page_size ? (
          <nav className="ws-pager" aria-label="Pagination">
            <button type="button" className="ws-btn" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="ws-num">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)}
            </span>
            <button
              type="button"
              className="ws-btn"
              disabled={pagination.page * pagination.page_size >= pagination.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        ) : null}
    </div>
  );
}

function ReviewsRouteInner() {
  const reviewId = useSearchParams().get("id");
  return reviewId ? (
    <ReviewReportPage key={reviewId} reviewId={reviewId} />
  ) : (
    // the queue is Legal's (UX Batch 2); a report still opens by its own link
    <LegalOnly><ReviewsQueueView /></LegalOnly>
  );
}

export default function ReviewsRoute() {
  return (
    <Suspense fallback={null}>
      <ReviewsRouteInner />
    </Suspense>
  );
}

"use client";

/**
 * Reviews — the queue (P1, PRODUCT_UX_ROADMAP §E screen 7). Scope is entirely
 * server-side: `GET /reviews` returns what REC-09 grants — a user's own and
 * assigned Reviews, plus (for `legal.review` holders) everything escalated or
 * in LEGAL_REVIEW. The page adds no scope logic of its own (rule 18: UI
 * permission gating is presentation only).
 *
 * Queue bias, not urgency theater: rows whose status asks for legal attention
 * carry the attention stripe and a filled chip; nothing blinks, nothing counts
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

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Pagination, Review } from "@/lib/types";

import { ReviewReportPage } from "@/components/workspace/ReviewReportPage";

const PAGE_SIZE = 25;

/** Step 30 states worth queueing on; "" leaves the filter off. */
const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "LEGAL_REVIEW", label: "Needs legal review" },
  { value: "ANALYSIS_COMPLETE", label: "Analysis complete" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "CLOSED", label: "Closed" },
] as const;

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
    <>
      <div className="ws-context">
        <h1>Reviews</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total</span>
        ) : null}
      </div>
      {/* `--queue` scopes the fixed column widths in workspace.css to this
          four-column table. Without them the columns size to content, and the
          two the visual baseline masks (Document, Created) still drive that
          sizing — so a longer document name in one run moved every column and
          failed job 15 on 7% of pixels with no visible change. */}
      <div className="ws-docs ws-docs--queue">
        <div className="ws-filter" role="group" aria-label="Filter by status">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              aria-pressed={status === filter.value}
              onClick={() => {
                setPage(1);
                setStatus(filter.value);
                setReviews(null);
              }}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>Reviews could not be loaded.</h2>
            <p>{describeError(error)}</p>
          </div>
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
            <h2>No Reviews here.</h2>
            <p>
              {status
                ? "Nothing visible to your account has this status."
                : "Reviews appear once a document is analysed. Upload a contract on the Documents page and analysis starts in the flow."}
            </p>
          </div>
        ) : null}

        {reviews !== null && reviews.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Status</th>
                  <th scope="col">Created</th>
                  <th scope="col">Report</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => {
                  const attention = ATTENTION_STATUSES.has(review.status);
                  return (
                    <tr key={review.id} data-review-id={review.id} className={attention ? "ws-tr--attention" : undefined}>
                      {/* The document's name, always — and a link to its
                          workspace only when this caller can actually open it.
                          A Review reachable through Legal scope (`REC-09`)
                          belongs to a Contract that stays ownership-scoped, so
                          linking there unconditionally sent the reader to
                          "Not found." while the Report beside it worked. */}
                      <td>
                        {review.document_accessible ? (
                          <Link href={`/dashboard?id=${review.contract_id}`}>
                            {review.document_name ?? review.contract_id.slice(0, 8)}
                          </Link>
                        ) : (
                          <span className="ws-docs__name" title="The document itself is not open to your account — the Report is">
                            {review.document_name ?? review.contract_id.slice(0, 8)}
                          </span>
                        )}
                        {review.document_type ? (
                          <span className="ws-chip ws-chip--type ws-docs__type">{review.document_type}</span>
                        ) : null}
                      </td>
                      <td>
                        <span className={`ws-chip${attention ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}>
                          {review.status}
                        </span>
                      </td>
                      <td className="ws-mono">{review.created_at ? review.created_at.slice(0, 10) : "—"}</td>
                      <td>
                        <Link href={`/dashboard/reviews?id=${review.id}`}>Report</Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {pagination && pagination.total > pagination.page_size ? (
          <nav className="ws-pager" aria-label="Pagination">
            <button type="button" className="ws-btn" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="ws-mono">
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
    </>
  );
}

function ReviewsRouteInner() {
  const reviewId = useSearchParams().get("id");
  return reviewId ? (
    <ReviewReportPage key={reviewId} reviewId={reviewId} />
  ) : (
    <ReviewsQueueView />
  );
}

export default function ReviewsRoute() {
  return (
    <Suspense fallback={null}>
      <ReviewsRouteInner />
    </Suspense>
  );
}

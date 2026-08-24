"use client";

/**
 * Review list — locked 52.6 (Steps 9, 30), 49.6.
 *
 * Scope comes entirely from the API: a Review is visible if the caller created it
 * or holds an active Legal assignment (Step 24 r2/r6). The list never contains
 * something a `GET` would 404 on (49.6), and there is nothing here that could widen
 * that.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AccessRestricted } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading, Pager } from "@/components/Feedback";
import { Field, StatePill, TableCard } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Pagination, Review } from "@/lib/types";

/** Locked Step 30's nine states. Nothing invented, nothing collapsed. */
const REVIEW_STATUSES = [
  "DRAFT",
  "UPLOADED",
  "PROCESSING",
  "ANALYSIS_COMPLETE",
  "LEGAL_REVIEW",
  "RESOLVED",
  "CLOSED",
  "ANALYSIS_FAILED",
  "CANCELLED",
];

export default function ReviewsPage() {
  const { can } = useSession();
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.reviews({ page, ...(status ? { status } : {}) });
      setReviews(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, status]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.REVIEW_VIEW)) return <AccessRestricted what="reviews" />;

  return (
    <>
      <h1>Reviews</h1>
      <p className="hint">
        Reviews you created, plus any assigned to you for Legal review. An assignment
        gives access for Legal work; it does not transfer ownership.
      </p>
      <ErrorBanner error={error} />

      <form className="card form-row" onSubmit={(event) => event.preventDefault()}>
        <Field id="review-status-filter" label="Lifecycle status">
          <select
            id="review-status-filter"
            value={status}
            onChange={(event) => {
              setPage(1);
              setStatus(event.target.value);
            }}
          >
            <option value="">All</option>
            {REVIEW_STATUSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>
      </form>

      {reviews === null ? (
        <Loading what="reviews" />
      ) : reviews.length === 0 ? (
        /* Distinguish "nothing matches this filter" from "nothing at all" —
           presentation of the active client-side filter state only. */
        <EmptyState>
          {status ? `No reviews with status ${status}.` : "No reviews."}
        </EmptyState>
      ) : (
        <>
          <TableCard>
            <table>
              <thead>
                <tr>
                  <th>Review</th>
                  <th>Status</th>
                  <th>Contract</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => (
                  <tr key={review.id}>
                    <td>
                      <Link href={`/reviews/${review.id}`}>{review.id.slice(0, 8)}</Link>
                    </td>
                    <td>
                      <StatePill axis="status" value={review.status} />
                    </td>
                    <td>
                      <Link href={`/contracts/${review.contract_id}`}>
                        {review.contract_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td>{review.created_at ? review.created_at.slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
          {pagination ? (
            <Pager
              page={pagination.page}
              pageSize={pagination.page_size}
              total={pagination.total}
              onPage={setPage}
            />
          ) : null}
        </>
      )}
    </>
  );
}

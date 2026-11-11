"use client";

/**
 * Legal — the ruling queue (slice 6; PRODUCT_UX_ROADMAP §G step 7). Every
 * Finding whose Evaluations await a Legal Decision, across the Reviews this
 * account can see, in one flat list.
 *
 * The ruling itself does NOT happen here: a Legal Decision is made beside the
 * evidence (UI master prompt), so each row deep-links into the document
 * workspace (`?finding=`), where slice 2's decision flow — justification,
 * conflict freeze, escalation — already lives. This screen triages; it never
 * disposes.
 *
 * Composition, not a new endpoint: there is no cross-review findings API
 * (49.3's surface is per-review), so the queue reads the two ACTIVE review
 * statuses through `GET /reviews` (REC-09 scope server-side — a legal reviewer
 * automatically sees what is escalated or in LEGAL_REVIEW) and fans out to
 * `GET /reviews/{id}/findings?status=DECISION_REQUIRED`, one page-bounded call
 * per review (the #210 idiom). When either review list has further pages the
 * page says so plainly rather than implying completeness.
 *
 * Gate: `legal.review`. Holding it does NOT confer decision authority
 * (SEC-01) — the workspace's decision form enforces `legal.decision`
 * server-side; this screen only decides who sees the queue at all.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  requirementTitle, userStatus,
} from "@/components/workspace/findingLanguage";

import { api, describeError } from "@/lib/api";
import { classificationLabel, contractOutcomeLabel, pointCount, reviewStatusLabel } from "@/lib/labels";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { TodoViews } from "@/components/workspace/TodoViews";
import type { Finding, Review } from "@/lib/types";
import { StatusChip, chipStatus } from "@/components/StatusChip";
import { ErrorState } from "@/components/Feedback";
import { SegmentedFilter } from "@/components/SegmentedFilter";

/** Step 30 statuses under which undecided Findings can still exist. LEGAL_REVIEW
 *  first: it is the explicitly-escalated lane. RESOLVED/CLOSED reviews cannot
 *  carry a DECISION_REQUIRED Finding, so they are not fetched. */
const ACTIVE_STATUSES = ["LEGAL_REVIEW", "ANALYSIS_COMPLETE"] as const;
const REVIEW_WINDOW = 25;

/** What waits on THIS reader, from the To-do's "decide" items — the same count, so the
 *  queue and the To-do never disagree (`AM-318` r10). */
interface Mine { points: number; changes: number }

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

interface QueueRow {
  finding: Finding;
  review: Review;
}

type Load =
  | { kind: "loading" }
  | { kind: "ready"; rows: QueueRow[]; truncated: boolean; failed: number; mine: Mine | null }
  | { kind: "error"; error: unknown };

export default function LegalQueuePage() {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  /** Batch 1 (e): the reader's own reviews, or the whole team view (`with_me`, unchanged) */
  const [pick, setPick] = useState<"yours" | "all" | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [pages, todo] = await Promise.all([
        Promise.all(ACTIVE_STATUSES.map((status) =>
          api.reviews({ page: 1, page_size: REVIEW_WINDOW, status, with_me: "true" }))),
        api.todo().catch(() => null),
      ]);
      const decide = todo?.items.filter((item) => item.kind === "decide") ?? [];
      const mine = todo ? {
        points: decide.reduce((n, item) => n + (item.count ?? 0), 0),
        changes: decide.reduce((n, item) => n + (item.changes ?? 0), 0),
      } : null;
      const reviews = pages.flatMap((page) => page.items);
      const truncated = pages.some((page) => page.pagination.total > page.pagination.page_size);

      const perReview = await Promise.allSettled(
        reviews.map((review) => api.allFindings(review.id, { status: "DECISION_REQUIRED" })),
      );
      const rows: QueueRow[] = [];
      reviews.forEach((review, index) => {
        const outcome = perReview[index];
        if (outcome?.status === "fulfilled") {
          for (const finding of outcome.value.items) rows.push({ finding, review });
        }
      });

      // Document names come WITH each Review (2026-09-04) — the per-row
      // `GET /contracts/{id}` batch that used to live here 404'd for every
      // Review this queue exists to show, since Legal scope covers the Review
      // and not the Contract.
      // what the owner sent to this reviewer first (owner, 2026-10-21; AB-100)
      rows.sort((a, b) => Number(Boolean(b.review.sent_to_you))
                          - Number(Boolean(a.review.sent_to_you)));
      // QA-023: a review whose points could not be read is said, never silently left out
      const failed = perReview.filter((outcome) => outcome.status === "rejected").length;
      setState({ kind: "ready", rows, truncated, failed, mine });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.LEGAL_REVIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include legal review.</p>
      </div>
    );
  }

  const rows = state.kind === "ready" ? state.rows : [];
  const yours = rows.filter((row) => row.review.yours);
  const view = pick ?? (yours.length ? "yours" : "all");
  const shown = view === "yours" ? yours : rows;
  const mine = state.kind === "ready" ? state.mine : null;

  return (
    <>
      <div className="ws-context">
        <h1>Legal</h1>
        {state.kind === "ready" ? (
          <span className="ws-context__meta">
            {!mine ? `${plural(pointCount(rows), "point")} awaiting a decision`
              : !mine.points && !mine.changes ? "Nothing awaits your decision"
              : `${plural(mine.points, "point")}${mine.changes ? ` and ${plural(mine.changes, "change")}` : ""} await your decision`}
          </span>
        ) : null}
      </div>
      <div className="ws-docs">
        <TodoViews />
        {state.kind === "ready" && rows.length > 0 ? (
          // round 3: the one filter control; "Yours" at 0 is not offered (PLAIN-LANGUAGE §5)
          <SegmentedFilter label="Whose reviews" value={view} onChange={setPick} segments={[
            { id: "yours", label: "Yours", text: "Yours", count: pointCount(yours) },
            { id: "all", label: "All with Legal", text: "All with Legal", count: pointCount(rows), always: true },
          ]} />
        ) : null}
        <p className="ws-pane__note">
          Findings waiting for a Legal Decision. Each row opens the document, where you decide.
        </p>

        {state.kind === "error" ? (
          <ErrorState title="The Legal queue could not be loaded" error={state.error} onRetry={() => void load()} />
        ) : null}

        {state.kind === "ready" && state.failed > 0 ? (
          <div className="ws-pane__note" role="alert">
            <p>
              {state.failed === 1 ? "1 review" : `${state.failed} reviews`} could not be
              loaded, so this list may be missing points that wait for a decision.
            </p>
            <button type="button" className="ws-btn" onClick={() => void load()}>
              Try again
            </button>
          </div>
        ) : null}

        {state.kind === "loading" ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading the legal queue…
            </p>
            {[0, 1, 2].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "35%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "18%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "12%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {state.kind === "ready" && shown.length === 0 ? (
          <div className="ws-state">
            <h2>{view === "yours" && rows.length ? "Nothing awaits your decision." : "Nothing awaits a Legal Decision."}</h2>
            <p>
              {view === "yours" && rows.length
                ? "Points with your colleagues are under All with Legal."
                : "Any deviation from our standards appears here."}
            </p>
          </div>
        ) : null}

        {state.kind === "ready" && shown.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Requirement</th>
                  <th scope="col">Status</th>
                  <th scope="col">Document</th>
                  <th scope="col">Review</th>
                </tr>
              </thead>
              <tbody>
                {shown.map(({ finding, review }) => (
                  <tr key={finding.id} data-finding-id={finding.id}>
                    {/* The finding opens in the document's workspace, beside its
                        evidence — but ONLY when this caller can open that
                        document. Legal scope (`REC-09`) covers the Finding and
                        not the Contract, so for a reviewer looking at someone
                        else's document that link answered "Not found."; the
                        Review's own report is what they can actually reach.
                        Whether Legal should be able to open the document itself
                        is an OPEN owner decision (HANDOFF §4), not something
                        this page may decide. */}
                    <td>
                      <Link href={review.document_accessible
                        ? `/dashboard?id=${review.contract_id}&finding=${finding.id}`
                        : `/dashboard/reviews?id=${review.id}`}>
                        {requirementTitle(finding.requirement)}
                      </Link>
                      {review.sent_to_you ? <span className="ws-chip">Sent to you</span> : null}
                      {review.contract_outcome
                        ? <span className="ws-chip">{contractOutcomeLabel(review.contract_outcome)}</span>
                        : null}
                      {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
                    </td>
                    <td>
                      {/* the reader's three words, as on every other screen (owner,
                          2026-10-21) — the engine's own word stays in the tooltip */}
                      <StatusChip status={chipStatus(userStatus(finding), finding.in_our_favour)}
                                  title={classificationLabel(finding.classification)} />
                    </td>
                    <td>
                      {review.document_accessible ? (
                        <Link href={`/dashboard?id=${review.contract_id}`}>
                          {review.document_name ?? review.contract_id.slice(0, 8)}
                        </Link>
                      ) : (
                        <span className="ws-docs__name" title="You can open the report, not the document">
                          {review.document_name ?? review.contract_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={`ws-chip${review.status === "LEGAL_REVIEW" ? " lm-lozenge" : ""}`}
                            title={review.status}>
                        {reviewStatusLabel(review.status)}
                      </span>{" "}
                      <Link href={`/dashboard/reviews?id=${review.id}`}>Report</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {state.kind === "ready" && state.truncated ? (
          <p className="ws-pane__note">
            Showing findings from the {REVIEW_WINDOW} most recent reviews in each status. Reviews lists them all.
          </p>
        ) : null}
      </div>
    </>
  );
}

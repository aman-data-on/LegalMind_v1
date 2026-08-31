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

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Finding, Review } from "@/lib/types";

/** Step 30 statuses under which undecided Findings can still exist. LEGAL_REVIEW
 *  first: it is the explicitly-escalated lane. RESOLVED/CLOSED reviews cannot
 *  carry a DECISION_REQUIRED Finding, so they are not fetched. */
const ACTIVE_STATUSES = ["LEGAL_REVIEW", "ANALYSIS_COMPLETE"] as const;
const REVIEW_WINDOW = 25;

interface QueueRow {
  finding: Finding;
  review: Review;
}

type Load =
  | { kind: "loading" }
  | { kind: "ready"; rows: QueueRow[]; names: Record<string, string>; truncated: boolean }
  | { kind: "error"; error: unknown };

export default function LegalQueuePage() {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const pages = await Promise.all(
        ACTIVE_STATUSES.map((status) => api.reviews({ page: 1, page_size: REVIEW_WINDOW, status })),
      );
      const reviews = pages.flatMap((page) => page.items);
      const truncated = pages.some((page) => page.pagination.total > page.pagination.page_size);

      const perReview = await Promise.allSettled(
        reviews.map((review) => api.findings(review.id, { status: "DECISION_REQUIRED", page_size: 100 })),
      );
      const rows: QueueRow[] = [];
      reviews.forEach((review, index) => {
        const outcome = perReview[index];
        if (outcome?.status === "fulfilled") {
          for (const finding of outcome.value.items) rows.push({ finding, review });
        }
      });

      const ids = [...new Set(rows.map((row) => row.review.contract_id))];
      const settled = await Promise.allSettled(ids.map((id) => api.contract(id)));
      const names: Record<string, string> = {};
      ids.forEach((id, index) => {
        const outcome = settled[index];
        if (outcome?.status === "fulfilled") names[id] = outcome.value.name;
      });

      setState({ kind: "ready", rows, names, truncated });
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

  return (
    <>
      <div className="ws-context">
        <h1>Legal</h1>
        {state.kind === "ready" ? (
          <span className="ws-context__meta ws-mono">
            {state.rows.length} awaiting a decision
          </span>
        ) : null}
      </div>
      <div className="ws-docs">
        <p className="ws-pane__note">
          Findings whose Evaluations await a Legal Decision. Ruling happens in the
          document&rsquo;s workspace, beside the evidence — each row opens there.
        </p>

        {state.kind === "error" ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>The queue could not be loaded.</h2>
            <p>{describeError(state.error)}</p>
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

        {state.kind === "ready" && state.rows.length === 0 ? (
          <div className="ws-state">
            <h2>Nothing awaits a Legal Decision.</h2>
            <p>
              When an Evaluation requires one — any deviation does, under the
              zero-tolerance rule — the Finding appears here.
            </p>
          </div>
        ) : null}

        {state.kind === "ready" && state.rows.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Requirement</th>
                  <th scope="col">Classification</th>
                  <th scope="col">Document</th>
                  <th scope="col">Review</th>
                </tr>
              </thead>
              <tbody>
                {state.rows.map(({ finding, review }) => (
                  <tr key={finding.id} data-finding-id={finding.id}>
                    <td>
                      <Link href={`/workspace?id=${review.contract_id}&finding=${finding.id}`}>
                        {finding.requirement.code ?? "Requirement"}
                        {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
                      </Link>
                      {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
                    </td>
                    <td>
                      <span className="ws-chip ws-chip--fill ws-chip--classify-fill">
                        {finding.classification}
                      </span>
                    </td>
                    <td>
                      <Link href={`/workspace?id=${review.contract_id}`}>
                        {state.names[review.contract_id] ?? review.contract_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td>
                      <span className={`ws-chip${review.status === "LEGAL_REVIEW" ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}>
                        {review.status}
                      </span>{" "}
                      <Link href={`/workspace/reviews?id=${review.id}`}>Report</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {state.kind === "ready" && state.truncated ? (
          <p className="ws-pane__note">
            Showing Findings from the {REVIEW_WINDOW} most recent Reviews in each active
            status — older Reviews exist. The Reviews screen lists them all.
          </p>
        ) : null}
      </div>
    </>
  );
}

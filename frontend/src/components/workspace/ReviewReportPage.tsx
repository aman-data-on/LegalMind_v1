"use client";

/**
 * The Review report — P1 (PRODUCT_UX_ROADMAP §E screen 8), rendering exactly
 * what `GET /reviews/{id}/report` carries: counts, coverage, and an alignment
 * ratio that F-9 locks to "carries no legal meaning". Two things are absent
 * because the specification forbids them, and the page says so rather than
 * leaving a suspicious gap: no risk figure (36.10, F-8) and no overall verdict.
 *
 * Permission layering: the Review itself needs `review.view`; the report body
 * additionally needs `report.view`. A caller with the first but not the second
 * sees the Review's identity and a plain note — the report is neither faked
 * nor replaced with an error banner.
 *
 * Denial semantics (49.5): an out-of-scope Review reads identically to a
 * nonexistent one — "Not found.", never "no access".
 */

import Link from "next/link";
import { sectionRef } from "@/lib/documentTypes";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Review, ReviewReport } from "@/lib/types";

import { ExportControl } from "./ExportControl";
import { IconArrowLeft } from "./icons";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; review: Review; report: ReviewReport | null; reportDenied: boolean }
  | { kind: "error"; error: unknown };

/** Visual weight only — filled chips mark states a human still owes work to.
 *  Never a severity ranking within an axis (UI master prompt), and RESOLVED
 *  stays a workflow fact, never restyled as a MATCH (rule 14). */
const CALM_CLASSIFICATIONS = new Set(["MATCH"]);
const CALM_STATUSES = new Set(["RESOLVED", "OPEN"]);

export function ReviewReportPage({ reviewId }: { reviewId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const review = await api.review(reviewId);
      let report: ReviewReport | null = null;
      let reportDenied = false;
      try {
        report = await api.report(reviewId);
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 403) reportDenied = true;
        else throw cause;
      }
      // The document's name arrives with the Review (2026-09-04) — the extra
      // `GET /contracts/{id}` this used to make is ownership-scoped, so for a
      // Review reached through Legal scope it 404'd and the heading fell back
      // to the generic "Review report".
      setState({ kind: "ready", review, report, reportDenied });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [reviewId]);

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

  if (state.kind === "loading") {
    return (
      <div className="ws-state" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the report…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "30%", height: "1.2rem" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "55%" }} aria-hidden="true" />
      </div>
    );
  }

  if (state.kind === "error") {
    const notFound = state.error instanceof ApiError && state.error.isNotFound;
    return (
      <div className={`ws-state${notFound ? "" : " ws-state--error"}`} role={notFound ? "note" : "alert"}>
        <h2>{notFound ? "Not found." : "The report could not be loaded."}</h2>
        {notFound ? (
          <p>
            <Link href="/dashboard/reviews">Back to reviews</Link>
          </p>
        ) : (
          <p>{describeError(state.error)}</p>
        )}
      </div>
    );
  }

  const { review, report, reportDenied } = state;

  return (
    <>
      <div className="ws-context">
        <Link className="ws-context__back" href="/dashboard/reviews" aria-label="Back to reviews">
          <IconArrowLeft size={18} />
        </Link>
        <h1>{review.document_name ?? "Review report"}</h1>
        <div className="ws-context__meta">
          {review.document_type ? (
            <span className="ws-chip ws-chip--type">{review.document_type}</span>
          ) : null}
          <span className={`ws-chip${review.status === "LEGAL_REVIEW" ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}>
            {review.status}
          </span>
          <span className="ws-mono">{review.created_at ? review.created_at.slice(0, 10) : ""}</span>
          <span className="ws-mono" title="Configuration snapshot — what makes this Review reproducible (AUD-04)">
            snapshot {review.configuration_snapshot_id.slice(0, 8)}
          </span>
          <span className="ws-context__spacer" />
          {/* Offered only when the workspace will actually open for this
              caller — see the queue's own note. */}
          {review.document_accessible ? (
            <Link href={`/dashboard?id=${review.contract_id}`}>Open the workspace</Link>
          ) : null}
          <ExportControl reviewId={review.id} />
        </div>
      </div>

      <div className="ws-docs">
      {reportDenied ? (
        <div className="ws-state" role="note">
          <h2>Report restricted</h2>
          <p>Your account does not include report access.</p>
        </div>
      ) : null}

      {report ? (
        <div className="ws-report">
          {/* ARRANGEMENT (2026-09-04, owner report: "hard to understand and not
              well arranged"). Before, four equal tiles sat side by side, so the
              one number a reviewer must ACT on — findings awaiting a decision —
              read with exactly the same weight as a coverage ratio that F-9
              says means nothing legally. The page now answers, in order:
              what do I owe? · what did it find? · what could it not judge? ·
              how much was covered? Every number is still the server's own. */}
          <section className="ws-report__lead" aria-label="What this Review needs">
            {report.findings_requiring_decision > 0 ? (
              <div className="ws-stat ws-stat--attention ws-report__lead-stat">
                <span className="ws-stat__n ws-mono">{report.findings_requiring_decision}</span>
                <span className="ws-stat__label">
                  {report.findings_requiring_decision === 1 ? "Finding awaits" : "Findings await"} a
                  Legal Decision
                </span>
                {review.document_accessible ? (
                  <Link className="ws-report__lead-act"
                        href={`/dashboard?id=${review.contract_id}&status=DECISION_REQUIRED`}>
                    Open them in the document →
                  </Link>
                ) : null}
              </div>
            ) : (
              <div className="ws-stat ws-report__lead-stat">
                <span className="ws-stat__n ws-mono">0</span>
                <span className="ws-stat__label">
                  Findings await a Legal Decision — nothing here needs a ruling
                </span>
              </div>
            )}
          </section>

          <section className="ws-stats" aria-label="Report totals">
            <div className={`ws-stat${report.unmatched_provisions > 0 ? " ws-stat--attention" : ""}`}>
              <span className="ws-stat__n ws-mono">{report.unmatched_provisions}</span>
              <span className="ws-stat__label">
                clauses with no matching requirement — read by a person, never judged
              </span>
            </div>
            <div className="ws-stat">
              <span className="ws-stat__n ws-mono">
                {report.coverage.requirements_with_findings} of {report.coverage.requirements_in_snapshot}
              </span>
              <span className="ws-stat__label">requirements in the snapshot produced Findings</span>
            </div>
            <div className="ws-stat">
              <span className="ws-stat__n ws-mono">
                {report.alignment.matched} of {report.alignment.requirements_evaluated}
              </span>
              <span className="ws-stat__label">
                evaluated Requirements matched
                {report.alignment.ratio != null ? ` (ratio ${report.alignment.ratio})` : ""}
              </span>
            </div>
          </section>

          <p className="ws-pane__note">
            Counts, deliberately: this report never grades the document. The alignment figure is a
            ratio over evaluated Requirements — it carries no legal meaning and cannot alter a
            Finding (F-9, 36.10).
          </p>

          {Object.keys(report.classification_counts).length > 0 ? (
            <section aria-label="Findings by classification">
              <h2 className="ws-report__h">Findings by classification</h2>
              <div className="ws-chips">
                {/* Each count opens the workspace's findings, pre-filtered to
                    exactly the findings it counts — a summary never substitutes
                    for its parts (DESIGN.md). */}
                {Object.entries(report.classification_counts).map(([value, count]) => (
                  <Link
                    key={value}
                    href={`/dashboard?id=${review.contract_id}&classification=${value}`}
                    className={`ws-chip ws-chip--link${CALM_CLASSIFICATIONS.has(value) ? "" : " ws-chip--fill ws-chip--classify-fill"}`}
                  >
                    {value} <b className="ws-mono">{count}</b>
                  </Link>
                ))}
              </div>
            </section>
          ) : null}

          {report.unmatched_provisions_detail.length > 0 ? (
            <section aria-label="Unmatched provisions">
              <h2 className="ws-report__h">Unmatched provisions — needs a human look</h2>
              <p className="ws-pane__note">
                These clauses appear in the counterparty&rsquo;s document but have no
                corresponding requirement in our Company Standard — the system has
                nothing to compare them against, so each one is routed to a person
                rather than judged. Not automatically negative or unacceptable
                (REC-02): a fact to review, not a determination.
              </p>
              <ul className="ws-report__unmatched">
                {report.unmatched_provisions_detail.map((item) => (
                  <li key={item.evidence_id} className="ws-report__unmatched-item">
                    <Link href={`/dashboard?id=${review.contract_id}&evidence=${item.evidence_id}`}>
                      {sectionRef(item.section_number)}
                      {item.section_title ? ` ${item.section_title}` : null}
                      {!item.section_number && !item.section_title
                        ? (item.page_number != null ? `p.${item.page_number}` : "View clause")
                        : null}
                      {" →"}
                    </Link>
                    <blockquote className="ws-quote">{item.excerpt}</blockquote>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {Object.keys(report.status_counts).length > 0 ? (
            <section aria-label="Findings by workflow status">
              <h2 className="ws-report__h">Findings by workflow status</h2>
              <div className="ws-chips">
                {Object.entries(report.status_counts).map(([value, count]) => (
                  <span
                    key={value}
                    className={`ws-chip${CALM_STATUSES.has(value) ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}
                  >
                    {value} <b className="ws-mono">{count}</b>
                  </span>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
      </div>
    </>
  );
}

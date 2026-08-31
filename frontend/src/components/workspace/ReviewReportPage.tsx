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
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Review, ReviewReport } from "@/lib/types";

import { ExportControl } from "./ExportControl";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; review: Review; report: ReviewReport | null; reportDenied: boolean; contractName: string | null }
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
      let contractName: string | null = null;
      try {
        contractName = (await api.contract(review.contract_id)).name;
      } catch {
        contractName = null; // the row still renders; the id link below suffices
      }
      setState({ kind: "ready", review, report, reportDenied, contractName });
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
            <Link href="/workspace/reviews">Back to reviews</Link>
          </p>
        ) : (
          <p>{describeError(state.error)}</p>
        )}
      </div>
    );
  }

  const { review, report, reportDenied, contractName } = state;

  return (
    <>
      <div className="ws-context">
        <h1>{contractName ?? "Review report"}</h1>
        <div className="ws-context__meta">
          <span className={`ws-chip${review.status === "LEGAL_REVIEW" ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}>
            {review.status}
          </span>
          <span className="ws-mono" title="Configuration snapshot — what makes this Review reproducible (AUD-04)">
            snapshot {review.configuration_snapshot_id.slice(0, 8)}
          </span>
          <span className="ws-mono">{review.created_at ? review.created_at.slice(0, 10) : ""}</span>
          <Link href={`/workspace?id=${review.contract_id}`}>Open the workspace</Link>
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
          <section className="ws-stats" aria-label="Report totals">
            <div className="ws-stat">
              <span className="ws-stat__n ws-mono">
                {report.coverage.requirements_with_findings} of {report.coverage.requirements_in_snapshot}
              </span>
              <span className="ws-stat__label">requirements in the snapshot produced Findings</span>
            </div>
            <div className={`ws-stat${report.findings_requiring_decision > 0 ? " ws-stat--attention" : ""}`}>
              <span className="ws-stat__n ws-mono">{report.findings_requiring_decision}</span>
              <span className="ws-stat__label">
                {report.findings_requiring_decision === 1 ? "Finding awaits" : "Findings await"} a Legal Decision
              </span>
            </div>
            <div className="ws-stat">
              <span className="ws-stat__n ws-mono">{report.unmatched_provisions}</span>
              <span className="ws-stat__label">unmatched provisions — document-level observations, never Findings</span>
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
                    href={`/workspace?id=${review.contract_id}&classification=${value}`}
                    className={`ws-chip ws-chip--link${CALM_CLASSIFICATIONS.has(value) ? "" : " ws-chip--fill ws-chip--classify-fill"}`}
                  >
                    {value} <b className="ws-mono">{count}</b>
                  </Link>
                ))}
              </div>
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

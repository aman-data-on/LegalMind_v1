"use client";

/**
 * Review report — locked 52.6 (Step 9), F-8, F-9, 36.10.
 *
 * Fixed pathname `/reviews/report`; the Review it reports on is selected via
 * `?id=` rather than a path segment, so no record id appears in the URL path.
 *
 * Two things are deliberately absent, and their absence is the specification being
 * followed rather than the screen being unfinished:
 *
 * **No risk score or risk label.** Locked 36.10 forbids a risk score as the primary
 * V1 legal output; F-8 makes risk a *configured* display mapping owned by the
 * reporting layer and versioned under Step 29. No such mapping is configured, and
 * ENG-09 says an absent configuration value fails closed rather than defaulting. The
 * API omits the field and this screen invents nothing to fill the gap.
 *
 * **No overall verdict.** F-9 makes the alignment figure a ratio over evaluated
 * Requirements that "carries no legal meaning and cannot alter a Finding". It is
 * shown as counts with the ratio beside them, labelled as such — never as a pass,
 * a score, or a conclusion.
 *
 * **Export is not offered.** Locked 49.12 records export formats as NOT YET
 * SPECIFIED, so there is no endpoint and no button. Inventing a format here would be
 * inventing product behaviour.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AccessRestricted } from "@/components/AccessRestricted";
import { ErrorBanner, Loading } from "@/components/Feedback";
import { StatePill } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ReviewReport } from "@/lib/types";

function ReportView({ reviewId }: { reviewId: string }) {
  const { can } = useSession();
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.report(reviewId).then(setReport).catch(setError);
  }, [reviewId]);

  if (!can(P.REPORT_VIEW)) return <AccessRestricted what="reports" />;

  return (
    <>
      <Link className="page-back" href={`/reviews?id=${reviewId}`}>
        ← Back to findings
      </Link>
      <h1>Review report</h1>
      <ErrorBanner error={error} />

      {report === null ? (
        <Loading what="report" />
      ) : (
        <>
          <section className="card">
            <h2>Coverage</h2>
            <p>
              {report.coverage.requirements_with_findings} of{" "}
              {report.coverage.requirements_in_snapshot} Requirements in the
              configuration snapshot produced a Finding.
            </p>
            <p className="hint">
              An optional Requirement with no matching provision produces no Finding at
              all, so a gap between these two numbers is meaningful rather than a
              failure.
            </p>
          </section>

          <section className="card">
            <h2>Findings by classification</h2>
            <table>
              <thead>
                <tr>
                  <th>Classification</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.classification_counts).map(([key, count]) => (
                  <tr key={key}>
                    <td>
                      <StatePill axis="classification" value={key} />
                    </td>
                    <td>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Findings by workflow status</h2>
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.status_counts).map(([key, count]) => (
                  <tr key={key}>
                    <td>
                      <StatePill axis="status" value={key} />
                    </td>
                    <td>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="hint">
              Classification and workflow status are separate axes. A RESOLVED Finding
              keeps the classification it was given — resolved does not mean matching.
            </p>
          </section>

          <section className="card">
            <h2>Alignment</h2>
            <p>
              {report.alignment.matched} of {report.alignment.requirements_evaluated}{" "}
              evaluated Requirements were classified MATCH
              {report.alignment.ratio !== null
                ? ` (${(report.alignment.ratio * 100).toFixed(1)}%)`
                : ""}
              .
            </p>
            <p className="hint">
              A count, not an assessment. This figure carries no legal meaning and
              cannot alter a Finding.
            </p>
          </section>

          <section className="card">
            <h2>Other observations</h2>
            <p>
              {report.unmatched_provisions} provision
              {report.unmatched_provisions === 1 ? "" : "s"} in the document did not
              match any Requirement.
            </p>
            <p className="hint">
              A document-level observation, not a Finding classification. Not
              automatically negative or unacceptable — routed to a person because the
              system has nothing to compare it against, not because it is presumed
              risky (REC-02).
            </p>
            {report.unmatched_provisions_detail.length > 0 ? (
              <ul>
                {report.unmatched_provisions_detail.map((item) => (
                  <li key={item.evidence_id}>
                    <strong>
                      {item.section_number ? `§${item.section_number}` : null}
                      {item.section_title ? ` ${item.section_title}` : null}
                      {!item.section_number && !item.section_title
                        ? (item.page_number != null ? `p.${item.page_number}` : "Untitled clause")
                        : null}
                    </strong>
                    <p className="hint">{item.excerpt}</p>
                  </li>
                ))}
              </ul>
            ) : null}
            <p>
              {report.findings_requiring_decision} Finding
              {report.findings_requiring_decision === 1 ? "" : "s"} still require a
              Legal Decision.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function ReportPageInner() {
  const reviewId = useSearchParams().get("id");
  if (!reviewId) return <Loading what="report" />;
  return <ReportView key={reviewId} reviewId={reviewId} />;
}

export default function ReportPage() {
  return (
    <Suspense fallback={<Loading what="report" />}>
      <ReportPageInner />
    </Suspense>
  );
}

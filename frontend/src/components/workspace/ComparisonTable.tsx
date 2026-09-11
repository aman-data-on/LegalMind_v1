"use client";

/**
 * The comparison, as a table — owner request, 2026-09-11 ("show acceptable,
 * needs modification and missing in a table").
 *
 * Every cell comes from the deterministic evaluator's OWN Findings on a real
 * Review (`GET /reviews/{id}/findings`). The assistant produces none of it:
 * `AM-25` r4 routes a comparison question to the evaluator, and this renders
 * what the evaluator already decided. No generated row, no invented
 * requirement, no severity — rules 7 and 12.
 *
 * The Company Standard column exists only for a caller who holds
 * `legal_position.view`. Without it the server OMITS `expected_value`
 * (LEGAL-02, SEC-07), so the column is absent rather than blank — an empty
 * cell would state that the standard says nothing, which is a different claim.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Finding } from "@/lib/types";

import {
  determinationLabel,
  requirementTitle,
  sideOf,
  standardSideOf,
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
  userStatus,
} from "./findingLanguage";

/** Worst-first, so what needs a person is at the top of the table. */
function byUrgency(a: Finding, b: Finding): number {
  const rank = (f: Finding) => USER_STATUS_ORDER.indexOf(userStatus(f));
  return rank(b) - rank(a);
}

export function ComparisonTable({
  reviewId,
  contractId,
}: {
  reviewId: string;
  contractId: string | null;
}) {
  const { can } = useSession();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const showStandard = can(P.LEGAL_POSITION_VIEW);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { items } = await api.findings(reviewId, { page_size: 100 });
        if (!cancelled) setFindings([...items].sort(byUrgency));
      } catch (cause) {
        if (!cancelled) setError(cause);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reviewId]);

  if (error) {
    return (
      <p className="ws-pane__note">
        The evaluator&rsquo;s comparison could not be loaded. {describeError(error)}
      </p>
    );
  }
  if (findings === null) {
    return (
      <p className="ws-pane__note" role="status" aria-live="polite">
        Reading the evaluator&rsquo;s comparison…
      </p>
    );
  }
  if (findings.length === 0) {
    return <p className="ws-pane__note">This Review holds no Findings.</p>;
  }

  return (
    <div className="ws-chat__tablewrap">
      <table className="ws-chat__table">
        <caption className="ws-visually-hidden">
          Each requirement the evaluator checked, what the document says, and the result
        </caption>
        <thead>
          <tr>
            <th scope="col">Requirement</th>
            <th scope="col">Agreement</th>
            {showStandard ? <th scope="col">Company standard</th> : null}
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => {
            // One row per Finding, read from its FIRST evaluation — the scope the
            // card leads with. A multi-scope Finding is opened in full from the
            // link; flattening several scopes into one cell would assert a single
            // reading the evaluator did not make.
            const evaluation = finding.evaluations[0];
            const found = sideOf(evaluation?.actual_value);
            const expected = standardSideOf(evaluation?.expected_value);
            const status = userStatus(finding);
            return (
              <tr key={finding.id}>
                <th scope="row">
                  {contractId ? (
                    <Link href={`/dashboard?id=${contractId}&finding=${finding.id}`}>
                      {requirementTitle(finding.requirement)}
                    </Link>
                  ) : (
                    requirementTitle(finding.requirement)
                  )}
                  <span className="ws-chat__rowsub">
                    {determinationLabel(finding.classification) ?? finding.classification}
                  </span>
                </th>
                <td>{found.text}</td>
                {showStandard ? <td>{expected.text}</td> : null}
                <td>
                  <span
                    className={`ws-chip ws-chip--fill ws-chip--status-${status.toLowerCase()}`}
                    data-tone={USER_STATUS_TONE[status]}
                  >
                    {USER_STATUS_LABELS[status]}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

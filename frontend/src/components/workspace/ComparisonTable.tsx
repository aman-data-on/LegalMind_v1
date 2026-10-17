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

import { ClauseBusiness } from "./Angles";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AssistClauseScope, Evidence, Finding } from "@/lib/types";

import {
  determinationLabel,
  evidenceLocation,
  nextStep,
  requirementTitle,
  sideOf,
  standardSideOf,
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
  userStatus,
} from "./findingLanguage";
import { clauseFromText } from "./model";

/** The clause a Finding read: the parser's number, else the number the row's own text
 *  states (`AM-57` r3 — derived for display, nothing re-extracted), else its passage. */
export function clauseRef(row: Evidence | undefined): string {
  if (!row) return "No clause found";
  if (row.section_number) return evidenceLocation(row, 0);
  const stated = clauseFromText(row);
  // the number as the document states it — no sign added (owner, 2026-09-10)
  return stated ? stated.number : evidenceLocation(row, 0);
}

/** Worst-first, so what needs a person is at the top of the table. */
function byUrgency(a: Finding, b: Finding): number {
  const rank = (f: Finding) => USER_STATUS_ORDER.indexOf(userStatus(f));
  return rank(b) - rank(a);
}

/** The clause a routed question quoted, and what the document's markup changes in it
 *  (`AM-149`). Removed and added text are said in words as well as struck/underlined,
 *  so the change never rests on styling alone. */
function QuotedClause({ clause }: { clause: AssistClauseScope }) {
  return (
    <div className="ws-chat__clause">
      <p className="ws-pane__note">The clause you quoted: <strong>{clause.location}</strong></p>
      {clause.changes.length > 0 ? (
        <>
          <p className="ws-pane__note">What the markup changes in it:</p>
          <ul className="ws-chat__changes">
            {clause.changes.map((change, index) => (
              <li key={index}>
                {change.deleted ? <>Removed: <del>{change.deleted}</del></> : null}
                {change.deleted && change.inserted ? " — " : null}
                {change.inserted ? <>Added: <ins>{change.inserted}</ins></> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

export function ComparisonTable({
  reviewId,
  contractId,
  findings: given,
  filename,
  clause,
}: {
  /** The saved Review to read — or none, when `findings` came with the answer. */
  reviewId?: string | null;
  contractId: string | null;
  /** A chat file's temporary review (`AM-143`): the engine's Findings, already here. */
  findings?: Finding[];
  /** The chat file those Findings are about — named, since a chat may hold several. */
  filename?: string | null | undefined;
  /** `AM-149` — the clause the question quoted: only its Findings, with a way to all. */
  clause?: AssistClauseScope | null | undefined;
}) {
  const [showAll, setShowAll] = useState(false);
  const { can } = useSession();
  const [loaded, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const showStandard = can(P.LEGAL_POSITION_VIEW);
  const findings = given ? [...given].sort(byUrgency) : loaded;

  useEffect(() => {
    if (!reviewId || given) return;
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
  }, [reviewId, given]);

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
  const file = filename ? <p className="ws-pane__note">File reviewed: {filename}</p> : null;
  const quoted = clause ? <QuotedClause clause={clause} /> : null;
  const inClause = clause ? findings.filter((f) => f.evidence.some(
    (row) => clause.evidence_ids.includes(row.id))) : findings;
  const shown = showAll ? findings : inClause;
  const toggle = clause && findings.length > inClause.length ? (
    <button type="button" className="ws-viewall" onClick={() => setShowAll(!showAll)}>
      {showAll ? "Show only this clause" : `Show all ${findings.length} findings for this document`}
    </button>
  ) : null;
  if (clause && shown.length === 0) {
    return (
      <>{quoted}
        <p className="ws-pane__note">No approved standard measured this clause, so the
          evaluator holds no Finding on it — a person reads it.</p>
        {toggle}</>
    );
  }
  if (findings.length === 0) {
    return given ? (
      <>{file}<p className="ws-pane__note">None of the approved standards applied to this file.</p></>
    ) : <p className="ws-pane__note">This Review holds no Findings.</p>;
  }

  const unclear = shown.filter((f) => f.classification === "UNABLE_TO_EVALUATE").length;
  return (
    <>
    {file}
    {quoted}
    {clause ? (
      <ClauseBusiness reviewId={reviewId} findingIds={shown.map((f) => f.id)} />
    ) : null}
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
          {shown.map((finding) => {
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
                <td data-label="Agreement">
                  {found.text}
                  {/* the clause the evaluator read — or that none was found */}
                  <span className="ws-chat__rowsub">
                    {clauseRef(finding.evidence[0])}
                  </span>
                </td>
                {showStandard ? <td data-label="Company standard">{expected.text}</td> : null}
                <td data-label="Result">
                  <span
                    className={`ws-chip ws-chip--fill ws-chip--status-${status.toLowerCase()}`}
                    data-tone={USER_STATUS_TONE[status]}
                  >
                    {USER_STATUS_LABELS[status]}
                  </span>
                  {/* what it means and who acts — a Legal decision where one is needed */}
                  <span className="ws-chat__rowsub">{nextStep(finding, evaluation, status)}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
      {unclear > 0 ? (
        <p className="ws-pane__note">
          {unclear === 1 ? "One requirement" : `${unclear} requirements`} could not be
          evaluated from the document&rsquo;s text: the evidence was insufficient, so a
          person must decide — nothing was guessed.
        </p>
      ) : null}
      {toggle}
    </>
  );
}

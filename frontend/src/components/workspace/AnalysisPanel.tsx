"use client";

/**
 * The Analysis panel — the side card's default tab, matched to the owner's
 * reference design (2026-09-01). A digest of what the deterministic analysis
 * found, built ONLY from fields the server already returns; nothing here
 * derives, ranks or scores a legal outcome.
 *
 *   Status summary   three stat tiles + a segmented bar of the DD-9 buckets
 *                    (match / needs review / missing). Counts are real; the
 *                    percentages are shares of the same counts — never a
 *                    grade, never confidence (rule 12).
 *   Breakdown        a donut of the same buckets, legend per EXACT
 *                    classification value (the vocabulary always renders
 *                    beside the color).
 *   Awaiting a decision  the findings-needing-decision set the findings pane
 *                    defaults to (one shared filter), as reference-style
 *                    cards; "View all" opens the Findings tab.
 *   Key obligations  the assist lane's descriptive extraction, grouped under
 *                    the document's own party labels — facts, never judgments.
 */

import { useMemo } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { describeError } from "@/lib/api";
import type { Finding } from "@/lib/types";

import { useFindingsState } from "./findingsState";
import { classificationLabel } from "@/lib/labels";

import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconRefresh, IconXCircle } from "./icons";
import {
  classificationBucket,
  findingsNeedingDecision,
  findingsSummary,
  relativeTime,
  type StatusBucket,
} from "./model";
import { ObligationsPanel } from "./ObligationsPanel";
import { useSideTabs } from "./WorkspaceLayout";

const BUCKET_LABEL: Record<StatusBucket, string> = {
  match: "Match",
  review: "Needs review",
  missing: "Missing",
};

export function AnalysisPanel({ documentVersionId }: { documentVersionId: string }) {
  const { state, reload } = useFindingsState();

  return (
    <div className="ws-analysis">
      <div className="ws-analysis__updated">
        <span className="ws-pane__note">
          {state.kind === "ready" && state.review.completed_at
            ? `Updated ${relativeTime(state.review.completed_at)}`
            : "Counts and facts — decisions stay with people."}
        </span>
        <button type="button" className="ws-toolbtn" aria-label="Refresh analysis" onClick={reload}>
          <IconRefresh size={14} />
        </button>
      </div>
      {state.kind === "loading" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Loading the analysis…
        </p>
      ) : state.kind === "no-review" ? (
        <p className="ws-pane__note">This version has not been analysed yet.</p>
      ) : state.kind === "in-flight" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Analysis is running — this panel fills in when it completes.
        </p>
      ) : state.kind === "failed" ? (
        <p className="ws-pane__note">
          The analysis could not be completed — the Findings tab has the details.
        </p>
      ) : state.kind === "error" ? (
        <p className="ws-pane__note">{describeError(state.error)}</p>
      ) : (
        <AnalysisSummary findings={state.findings} />
      )}
      <ObligationsPanel documentVersionId={documentVersionId} />
    </div>
  );
}

function AnalysisSummary({ findings }: { findings: Finding[] }) {
  const sideTabs = useSideTabs();
  const summary = findingsSummary(findings);
  const risks = findingsNeedingDecision(findings);

  const buckets = useMemo(() => {
    const totals: Record<StatusBucket, number> = { match: 0, review: 0, missing: 0 };
    for (const { classification, n } of summary.counts) {
      totals[classificationBucket(classification)] += n;
    }
    return totals;
  }, [summary]);
  const total = findings.length;

  if (total === 0) {
    return (
      <section className="ws-analysis__section" aria-label="Status summary">
        <p className="ws-pane__note">
          Analysis completed — no findings. No ratified requirement for this
          document type produced one.
        </p>
      </section>
    );
  }

  return (
    <>
      <section className="ws-analysis__section" aria-label="Status summary">
        <div className="ws-analysis__head">
          <h3 className="ws-analysis__title">Status summary</h3>
          {sideTabs ? (
            <button type="button" className="ws-viewall" onClick={() => sideTabs.openFindings()}>
              View all
            </button>
          ) : null}
        </div>
        {/* One tile per classification that ACTUALLY occurred — the real Step 19
            vocabulary, never an invented catch-all label. "Needs review" is not
            a status in this system; DEVIATION and UNABLE_TO_EVALUATE are
            different facts and stay named as themselves (rule 7/12/14).
            Each tile is a real control (DD-14): it opens the Findings tab
            filtered to exactly that classification. */}
        <div className="ws-tiles">
          {summary.counts.map(({ classification, n }) => {
            const bucket = classificationBucket(classification);
            return (
              <button
                key={classification}
                type="button"
                className={`ws-tile ws-tile--${bucket}`}
                aria-label={`Show the ${n} ${classificationLabel(classification)} finding${n === 1 ? "" : "s"}`}
                onClick={() => sideTabs?.openFindings({ classification })}
              >
                <span className="ws-tile__n">{n}</span>
                <span className="ws-tile__label ws-mono">{classificationLabel(classification)}</span>
                <span className={`ws-status ws-status--${bucket}`}>
                  {bucket === "match" ? <IconCheckCircle size={18} /> : bucket === "missing" ? <IconXCircle size={18} /> : <IconAlertCircle size={18} />}
                </span>
              </button>
            );
          })}
        </div>
        <div
          className="ws-bar"
          role="img"
          aria-label={summary.counts.map(({ classification, n }) => `${n} ${classificationLabel(classification)}`).join(", ")}
        >
          {summary.counts.map(({ classification, n }) =>
            n > 0 ? (
              <span
                key={classification}
                className={`ws-bar__seg ws-bar__seg--${classificationBucket(classification)}`}
                style={{ flexGrow: n }}
              />
            ) : null,
          )}
        </div>
        <p className="ws-pane__note">
          Total requirements analyzed: <span className="ws-mono">{total}</span>
        </p>
      </section>

      <section className="ws-analysis__section" aria-label="Clause status breakdown">
        <h3 className="ws-analysis__title">Clause status breakdown</h3>
        <div className="ws-ring">
          <Donut match={buckets.match} review={buckets.review} missing={buckets.missing} total={total} />
          <ul className="ws-ring__legend">
            {summary.counts.map(({ classification, n }) => (
              <li key={classification} data-bucket={classificationBucket(classification)}>
                {/* The legend row is the same control as its tile (DD-14). */}
                <button
                  type="button"
                  className="ws-ring__go"
                  aria-label={`Show the ${n} ${classificationLabel(classification)} finding${n === 1 ? "" : "s"}`}
                  onClick={() => sideTabs?.openFindings({ classification })}
                >
                  <span className="ws-ring__swatch" aria-hidden="true" />
                  <span className="ws-mono">{n}</span>
                  <span className="ws-ring__pct">({Math.round((n / total) * 100)}%)</span>
                  {classificationLabel(classification)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/*
        ⚠️ "Awaiting a decision", not "Key risks" (renamed 2026-09-01).
        Rule 12: a Finding reconstructs as Evidence → Fact → Standard → Rule →
        Result — there is no risk score to rank, and nothing here is scored. What
        this list actually is, exactly, is the set of findings that need a human
        ruling (`findingsNeedingDecision`, the same filter the Findings pane
        defaults to). Naming it that tells the reader what to DO with it, which
        "risk" never did.
      */}
      {/*
        * ONE call to action, not a second copy of the list (2026-09-04 audit).
        *
        * This section used to render a card per awaiting-decision finding — name,
        * description, "View clause", "Open finding" — while the Findings tab beside
        * it opens on exactly that same set by default. Two surfaces answering "what
        * needs a decision?" in one panel is the duplication a reader notices as
        * "why am I seeing this twice?", and every card's own buttons only led to
        * the other tab anyway. The count and the way through remain; the second
        * rendering is gone.
        */}
      <section className="ws-analysis__section" aria-label="What needs a decision">
        <div className="ws-analysis__head">
          <h3 className="ws-analysis__title">What needs a decision</h3>
        </div>
        {risks.length === 0 ? (
          <p className="ws-pane__note">Nothing awaits a decision on this version.</p>
        ) : (
          <p className="ws-analysis__act">
            <b className="ws-mono">{risks.length}</b>{" "}
            {risks.length === 1 ? "finding needs" : "findings need"} a legal decision.{" "}
            {sideTabs ? (
              <button type="button" className="ws-viewall" onClick={() => sideTabs.openFindings()}>
                Open the list →
              </button>
            ) : null}
          </p>
        )}
      </section>
    </>
  );
}

/** Real counts as a three-part donut. The center is the raw total — no
 *  percentage-as-verdict, no invented score (rule 12). */
function Donut({ match, review, missing, total }: {
  match: number; review: number; missing: number; total: number;
}) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const start = circumference / 4; // 12 o'clock
  const segments: Array<{ bucket: StatusBucket; n: number }> = [
    { bucket: "match", n: match },
    { bucket: "review", n: review },
    { bucket: "missing", n: missing },
  ];
  let consumed = 0;
  return (
    <svg
      className="ws-ring__svg"
      viewBox="0 0 92 92"
      role="img"
      aria-label={`${total} findings: ${match} match, ${review} need review, ${missing} missing`}
    >
      {segments.map(({ bucket, n }) => {
        if (n === 0) return null;
        const length = (n / total) * circumference;
        const offset = start - consumed;
        consumed += length;
        return (
          <circle
            key={bucket}
            className={`ws-ring__seg ws-ring__seg--${bucket}`}
            cx="46"
            cy="46"
            r={radius}
            strokeDasharray={`${length} ${circumference - length}`}
            strokeDashoffset={offset}
          />
        );
      })}
      <text className="ws-ring__total" x="46" y="44" textAnchor="middle">{total}</text>
      <text className="ws-ring__label" x="46" y="58" textAnchor="middle">findings</text>
    </svg>
  );
}


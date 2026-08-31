"use client";

/**
 * The AI Analysis panel — the side card's default tab, matched to the owner's
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
 *   Key risks        the findings-needing-decision set the findings pane
 *                    defaults to (one shared filter), as reference-style
 *                    cards; "View all" opens the Findings tab.
 *   Key obligations  the assist lane's descriptive extraction, grouped under
 *                    the document's own party labels — facts, never judgments.
 */

import { useMemo } from "react";

import { describeError } from "@/lib/api";
import type { Finding } from "@/lib/types";

import { useFindingsState } from "./findingsState";
import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconRefresh, IconXCircle } from "./icons";
import {
  classificationBucket,
  findingsNeedingDecision,
  findingsSummary,
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

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
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
        <h3 className="ws-analysis__title">Status summary</h3>
        <div className="ws-tiles">
          <div className="ws-tile ws-tile--match">
            <span className="ws-tile__n">{buckets.match}</span>
            <span className="ws-tile__label">Match</span>
            <span className="ws-status ws-status--match"><IconCheckCircle size={18} /></span>
          </div>
          <div className="ws-tile ws-tile--review">
            <span className="ws-tile__n">{buckets.review}</span>
            <span className="ws-tile__label">Needs review</span>
            <span className="ws-status ws-status--review"><IconAlertCircle size={18} /></span>
          </div>
          <div className="ws-tile ws-tile--missing">
            <span className="ws-tile__n">{buckets.missing}</span>
            <span className="ws-tile__label">Missing</span>
            <span className="ws-status ws-status--missing"><IconXCircle size={18} /></span>
          </div>
        </div>
        <div className="ws-bar" role="img"
             aria-label={`${buckets.match} match, ${buckets.review} need review, ${buckets.missing} missing`}>
          {(["match", "review", "missing"] as const).map((bucket) =>
            buckets[bucket] > 0 ? (
              <span
                key={bucket}
                className={`ws-bar__seg ws-bar__seg--${bucket}`}
                style={{ flexGrow: buckets[bucket] }}
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
                <span className="ws-ring__swatch" aria-hidden="true" />
                <span className="ws-mono">{n}</span>
                <span className="ws-ring__pct">({Math.round((n / total) * 100)}%)</span>
                {classification}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="ws-analysis__section" aria-label="Key risks">
        <div className="ws-analysis__head">
          <h3 className="ws-analysis__title">Key risks</h3>
          {risks.length > 0 && sideTabs ? (
            <button type="button" className="ws-viewall" onClick={sideTabs.openFindings}>
              View all
            </button>
          ) : null}
        </div>
        {risks.length === 0 ? (
          <p className="ws-pane__note">Nothing awaits a decision on this version.</p>
        ) : (
          risks.map((finding) => <RiskCard key={finding.id} finding={finding} />)
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

function riskDescription(finding: Finding): string {
  if (finding.classification === "MISSING") {
    return "Expected for this document type and not found in the document.";
  }
  const line = finding.evaluations[0]?.explanation?.[0];
  return line ?? "Awaits a Legal Decision — open the finding for the full evaluation.";
}

function RiskCard({ finding }: { finding: Finding }) {
  const { point, target } = useHighlight();
  const sideTabs = useSideTabs();
  const bucket = classificationBucket(finding.classification);
  const firstEvidence = finding.evidence[0];
  return (
    <article className={`ws-risk ws-risk--${bucket}`}>
      <p className="ws-risk__name">
        <span>
          {finding.requirement.code ?? "Requirement"}
          {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
          {firstEvidence?.section_number ? ` · §${firstEvidence.section_number}` : ""}
        </span>
        <span className={`ws-chip ws-chip--bucket-${bucket}`}>{finding.classification}</span>
      </p>
      <p className="ws-risk__desc">{riskDescription(finding)}</p>
      <p className="ws-risk__meta">
        {firstEvidence ? (
          <button
            type="button"
            className="ws-evidence__loc"
            aria-current={target === firstEvidence.id ? "true" : undefined}
            onClick={() => point(firstEvidence.id, "the cited")}
          >
            View clause →
          </button>
        ) : sideTabs ? (
          <button type="button" className="ws-evidence__loc" onClick={sideTabs.openFindings}>
            Open finding →
          </button>
        ) : null}
      </p>
    </article>
  );
}

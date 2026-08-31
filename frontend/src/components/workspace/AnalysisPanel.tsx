"use client";

/**
 * The AI Analysis panel — the third column of the 2026-08-31 redesign. A
 * digest of what the deterministic analysis found, built ONLY from fields the
 * server already returns; nothing here derives, ranks or scores.
 *
 *   Ring        the loaded findings' classification counts as a two-part donut
 *               (match / needs attention). Two parts, not the reference's
 *               3-way traffic light: no classification axis renders with a
 *               severity ranking. The center is the raw total — never a
 *               percentage-as-verdict (rule 12, F-8/F-9).
 *   Key risks   the same needs-a-decision set the findings pane defaults to
 *               (one shared filter, so the views cannot disagree), as compact
 *               cards that jump to the clause via the highlight gesture.
 *   Obligations what each party has to do, per the assist lane's descriptive
 *               extraction — facts about the text, never a judgment.
 *
 * The panel reads the shared findings state machine — one fetch, one poll —
 * and renders each non-ready state in a quiet sentence (the findings pane is
 * where those states get their full treatment).
 */

import { describeError } from "@/lib/api";
import type { Finding } from "@/lib/types";

import { useFindingsState } from "./findingsState";
import { useHighlight } from "./highlight";
import { findingsNeedingDecision, findingsSummary } from "./model";
import { ObligationsPanel } from "./ObligationsPanel";

export function AnalysisPanel({ documentVersionId }: { documentVersionId: string }) {
  const { state } = useFindingsState();

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">AI Analysis</h2>
        <span className="ws-pane__note">Counts and facts — decisions stay with people.</span>
      </div>
      <div className="ws-pane__body ws-analysis">
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
            The analysis could not be completed — the Findings pane has the details.
          </p>
        ) : state.kind === "error" ? (
          <p className="ws-pane__note">{describeError(state.error)}</p>
        ) : (
          <AnalysisSummary findings={state.findings} />
        )}
        <ObligationsPanel documentVersionId={documentVersionId} />
      </div>
    </>
  );
}

function AnalysisSummary({ findings }: { findings: Finding[] }) {
  const summary = findingsSummary(findings);
  const risks = findingsNeedingDecision(findings);
  const matched = summary.counts.find((c) => c.classification === "MATCH")?.n ?? 0;
  const attention = findings.length - matched;

  return (
    <>
      <section className="ws-analysis__section" aria-label="Classification summary">
        {findings.length === 0 ? (
          <p className="ws-pane__note">
            Analysis completed — no findings. No ratified requirement for this
            document type produced one.
          </p>
        ) : (
          <div className="ws-ring">
            <ClassificationRing matched={matched} attention={attention} total={findings.length} />
            <ul className="ws-ring__legend">
              {summary.counts.map(({ classification, n }) => (
                <li key={classification} data-calm={classification === "MATCH" || undefined}>
                  <span className="ws-ring__swatch" aria-hidden="true" />
                  {classification} <span className="ws-mono">({n})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {risks.length > 0 ? (
        <section className="ws-analysis__section" aria-label="Key risks">
          <h3 className="ws-analysis__title">Key risks — needs a decision</h3>
          {risks.map((finding) => (
            <RiskCard key={finding.id} finding={finding} />
          ))}
        </section>
      ) : findings.length > 0 ? (
        <section className="ws-analysis__section" aria-label="Key risks">
          <h3 className="ws-analysis__title">Key risks</h3>
          <p className="ws-pane__note">Nothing awaits a decision on this version.</p>
        </section>
      ) : null}
    </>
  );
}

/**
 * A donut of real counts. Two arcs, exact numbers beside them, the raw total in
 * the center — no percentage, no grade, no invented score (rule 12).
 */
function ClassificationRing({
  matched,
  attention,
  total,
}: {
  matched: number;
  attention: number;
  total: number;
}) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const matchedShare = total > 0 ? (matched / total) * circumference : 0;

  return (
    <svg
      className="ws-ring__svg"
      viewBox="0 0 88 88"
      role="img"
      aria-label={`${total} findings: ${matched} match, ${attention} need attention`}
    >
      <circle className="ws-ring__track ws-ring__track--attention" cx="44" cy="44" r={radius} />
      {matched > 0 ? (
        <circle
          className="ws-ring__track ws-ring__track--match"
          cx="44"
          cy="44"
          r={radius}
          strokeDasharray={`${matchedShare} ${circumference - matchedShare}`}
          strokeDashoffset={circumference / 4}
        />
      ) : null}
      <text className="ws-ring__total" x="44" y="42" textAnchor="middle">
        {total}
      </text>
      <text className="ws-ring__label" x="44" y="56" textAnchor="middle">
        findings
      </text>
    </svg>
  );
}

function RiskCard({ finding }: { finding: Finding }) {
  const { point, target } = useHighlight();
  const firstEvidence = finding.evidence[0];
  return (
    // No data-finding-id here: the `?finding=` deep link must resolve to the
    // findings pane's card, uniquely.
    <article className="ws-risk">
      <p className="ws-risk__name">
        {finding.requirement.code ?? "Requirement"}
        {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
      </p>
      <p className="ws-risk__meta">
        <span className="ws-chip ws-chip--fill ws-chip--classify-fill">{finding.classification}</span>
        {firstEvidence ? (
          <button
            type="button"
            className="ws-evidence__loc"
            aria-current={target === firstEvidence.id ? "true" : undefined}
            onClick={() => point(firstEvidence.id, "the cited")}
          >
            View clause
            {firstEvidence.section_number ? ` §${firstEvidence.section_number}` : ""}
          </button>
        ) : (
          <span className="ws-pane__note">No supporting text found</span>
        )}
      </p>
    </article>
  );
}

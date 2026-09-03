"use client";

/**
 * The findings pane — summary first, then the drill: category → finding →
 * evidence, without ever leaving the workspace (owner directive 2026-08-31
 * §10–§13). A Finding shows its derived `classification` AND every scoped
 * Evaluation, never a single collapsed verdict (49.7 r1, locked 52.5); decision
 * controls attach to the Evaluation, never the Finding (AB-1).
 *
 * The summary strip renders the loaded findings' classification counts as
 * pressable filters — presentational grouping of server values, never a
 * client-side re-derivation (52.7). "Needs decision" stays the default view
 * when anything needs one. When every finding is a MATCH, that is a designed
 * success state, not an empty table (§29) — built from real fields only, no
 * grade, no percentage.
 *
 * While the Review is still moving through its lifecycle the pane says so and
 * polls `GET /reviews/{id}` — the lifecycle is the single source of progress
 * (52.7); no fake stages are invented.
 *
 * Evidence appears twice, deliberately: the verbatim excerpt beside the
 * finding (so the drill ends in text, not a pointer), and the highlight
 * gesture into the document pane for full context. "Ask about this" hands an
 * EDITABLE question to the Ask pane — the user sees exactly what is asked.
 */

import { useEffect, useRef, useState } from "react";

import { describeError } from "@/lib/api";
import { sectionRef } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, Evaluation, Evidence, Finding } from "@/lib/types";

import { AnalyzeControl } from "./AnalyzeControl";
import { useAskIntent } from "./askIntent";
import { DecisionControl } from "./DecisionControl";
import { EscalateControl } from "./EscalateControl";
import { useFindingsState } from "./findingsState";
import { useHighlight } from "./highlight";
import { findingsSummary } from "./model";
import { useSideTabs } from "./WorkspaceLayout";

type View = "attention" | "all" | { classification: string };

const ATTENTION_OUTCOMES = new Set(["APPROVAL_REQUIRED", "UNACCEPTABLE"]);
const CALM_CLASSIFICATIONS = new Set(["MATCH"]);
const CALM_OUTCOMES = new Set(["ACCEPTABLE", "NOT_APPLICABLE"]);

function initialView(): View {
  if (typeof window === "undefined") return "attention";
  const pointed = new URLSearchParams(window.location.search).get("classification");
  return pointed ? { classification: pointed } : "attention";
}

export function FindingsPane({ version }: { version: DocumentVersion }) {
  const { can } = useSession();
  // The one findings state machine, shared with the outline and the AI
  // Analysis panel (findingsState.tsx) — fetch and poll live there.
  const { state, reload } = useFindingsState();
  const [view, setView] = useState<View>(initialView);

  // `?finding=` — the Legal queue's deep link. One-shot per target: scroll to
  // the card and move focus to it (the same gesture the document pane gives
  // `?evidence=`). A target hidden by the current view widens the view first.
  const pointedDone = useRef<string | null>(null);
  useEffect(() => {
    if (state.kind !== "ready") return;
    const pointed = new URLSearchParams(window.location.search).get("finding");
    if (!pointed || pointedDone.current === pointed) return;
    const card = document.querySelector<HTMLElement>(`article[data-finding-id="${pointed}"]`);
    if (!card) {
      if (view !== "all") setView("all");
      return;
    }
    pointedDone.current = pointed;
    card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
  }, [state, view]);

  // Analysis-panel pointing (DD-14): a click on a status tile, a donut legend
  // row or a finding card over there lands HERE — on the matching filter, or
  // scrolled to the named finding. Same gesture as `?finding=`, in-app rather
  // than via the URL; `seq` dedupes so each click points exactly once.
  const sideTabs = useSideTabs();
  const pointSeqDone = useRef(0);
  const point = sideTabs?.findingsPoint ?? null;
  useEffect(() => {
    if (!point || point.seq === pointSeqDone.current) return;
    if (point.classification) {
      pointSeqDone.current = point.seq;
      setView({ classification: point.classification });
      return;
    }
    if (point.findingId) {
      if (state.kind !== "ready") return; // retry when findings arrive
      const card = document.querySelector<HTMLElement>(
        `article[data-finding-id="${point.findingId}"]`,
      );
      if (!card) {
        // Hidden by the current view — widen first; this effect re-runs.
        if (view !== "all") setView("all");
        return;
      }
      pointSeqDone.current = point.seq;
      card.scrollIntoView({ block: "center" });
      card.focus({ preventScroll: true });
      return;
    }
    pointSeqDone.current = point.seq;
  }, [point, state, view]);

  if (!can(P.FINDING_VIEW)) {
    return (
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Findings</h2>
        <div className="ws-state" role="note">
          <p>Your account does not include findings access.</p>
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state" aria-busy="true">
          <p className="ws-visually-hidden" role="status" aria-live="polite">
            Loading findings…
          </p>
          <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
          <span className="ws-skel ws-skel--line" style={{ width: "55%" }} aria-hidden="true" />
        </div>
      </>
    );
  }

  if (state.kind === "no-review") {
    // 2026-08-31 UX correction: the absent Review is an ACTION, not a dead end.
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state">
          <AnalyzeControl version={version} onAnalysed={reload} />
        </div>
      </>
    );
  }

  if (state.kind === "in-flight") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state" aria-busy="true">
          <p role="status" aria-live="polite">
            Analysing against configuration snapshot{" "}
            <span className="ws-mono">{state.review.configuration_snapshot_id.slice(0, 8)}</span>…
          </p>
          <p className="ws-pane__note">
            You can keep working — this pane updates when the analysis completes.
          </p>
          <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
        </div>
      </>
    );
  }

  if (state.kind === "failed") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state ws-state--error" role="alert">
          <h3>The analysis could not be completed.</h3>
          <p>
            No findings were produced. The most common causes are an undeclared
            document type or configuration this document type has no standards
            for. Nothing was decided about this document.
          </p>
        </div>
      </>
    );
  }

  if (state.kind === "error") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state ws-state--error" role="alert">
          <p>{describeError(state.error)}</p>
        </div>
      </>
    );
  }

  const { review, findings } = state;
  const summary = findingsSummary(findings);
  const effectiveView: View =
    view === "attention" && summary.needsDecision === 0 ? "all" : view;
  const shown =
    effectiveView === "all"
      ? findings
      : effectiveView === "attention"
        ? findings.filter((f) => f.requires_decision)
        : findings.filter((f) => f.classification === effectiveView.classification);

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Findings</h2>
        {/* Export moved to the page header (DD-9) — one Download, one place. */}
        <span className="ws-pane__note ws-mono">{findings.length} total</span>
      </div>
      <div className="ws-pane__body" style={{ padding: "16px" }}>
        {findings.length === 0 ? (
          <div className="ws-state" role="note">
            <h3>Analysis completed — no findings.</h3>
            <p>
              No ratified requirement for this document type produced a finding.
              That is a factual result, not an approval.
            </p>
          </div>
        ) : (
          <>
            {summary.allMatch ? (
              <div className="ws-success" role="note">
                <h3>Every evaluated provision matches the company standard.</h3>
                <p className="ws-pane__note">
                  {findings.length === 1
                    ? "1 requirement was evaluated; it matched."
                    : `${findings.length} requirements were evaluated; all matched.`}{" "}
                  No deviations, nothing missing. The findings below show each
                  match and its evidence.
                </p>
              </div>
            ) : null}
            <div className="ws-filter" role="group" aria-label="Filter findings">
              {summary.needsDecision > 0 ? (
                <button
                  type="button"
                  aria-pressed={effectiveView === "attention"}
                  onClick={() => setView("attention")}
                >
                  Needs decision ({summary.needsDecision})
                </button>
              ) : null}
              <button
                type="button"
                aria-pressed={effectiveView === "all"}
                onClick={() => setView("all")}
              >
                All ({findings.length})
              </button>
              {summary.counts.map(({ classification, n }) => (
                <button
                  key={classification}
                  type="button"
                  aria-pressed={
                    typeof effectiveView === "object" &&
                    effectiveView.classification === classification
                  }
                  onClick={() => setView({ classification })}
                >
                  {classification} ({n})
                </button>
              ))}
            </div>
            {shown.length === 0 ? (
              <p role="status">No findings in this view.</p>
            ) : (
              shown.map((finding) => (
                <FindingCard key={finding.id} finding={finding} onChanged={reload} />
              ))
            )}
          </>
        )}
      </div>
    </>
  );
}

function askQuestionFor(finding: Finding): string {
  const name = finding.requirement.name ?? finding.requirement.code ?? "this provision";
  const where = finding.evidence.find((e) => e.section_number)?.section_number;
  return finding.classification === "MISSING"
    ? `Does this document say anything about ${name}?`
    : `What does this document say about ${name}${where ? ` (§${where})` : ""}?`;
}

function FindingCard({ finding, onChanged }: { finding: Finding; onChanged: () => void }) {
  const askIntent = useAskIntent();
  const calm = CALM_CLASSIFICATIONS.has(finding.classification);
  const evidenceById = new Map(finding.evidence.map((e) => [e.id, e]));
  return (
    <article className={`ws-finding${finding.requires_decision ? " ws-finding--attention" : ""}`} data-finding-id={finding.id} tabIndex={-1}>
      <header className="ws-finding__head">
        <h3 className="ws-finding__title">
          {finding.requirement.code ?? "Requirement"}
          {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
        </h3>
        <span className={`ws-chip${calm ? "" : " ws-chip--fill ws-chip--classify-fill"}`} title="Derived summary of the Evaluations below">
          {finding.classification}
        </span>
        <span className="ws-chip">{finding.status}</span>
        {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
      </header>
      <p className="ws-finding__note">
        Classification is a derived summary — the Evaluations below are the authoritative results.
      </p>
      {finding.classification === "MISSING" ? (
        <p className="ws-finding__missing">
          This requirement is expected for this document type and was not found
          in the document.
        </p>
      ) : null}
      {finding.evaluations.map((evaluation) => (
        <EvaluationCard
          key={evaluation.id}
          evaluation={evaluation}
          evidenceById={evidenceById}
          onChanged={onChanged}
        />
      ))}
      <div className="ws-finding__acts">
        {askIntent ? (
          <button
            type="button"
            className="ws-escalate__link"
            onClick={() => askIntent.ask(askQuestionFor(finding))}
          >
            Ask about this
          </button>
        ) : null}
        <EscalateControl finding={finding} onChanged={onChanged} />
      </div>
    </article>
  );
}

function EvaluationCard({
  evaluation,
  evidenceById,
  onChanged,
}: {
  evaluation: Evaluation;
  evidenceById: Map<string, Evidence>;
  onChanged: () => void;
}) {
  const { point, target } = useHighlight();
  const attention =
    ("rule_outcome" in evaluation && evaluation.rule_outcome !== undefined
      ? ATTENTION_OUTCOMES.has(evaluation.rule_outcome)
      : false) || evaluation.requires_decision;
  const showDecision = evaluation.requires_decision || evaluation.current_decision !== null;
  const explanation = evaluation.explanation ?? [];

  return (
    <div className="ws-evaluation" data-scope={evaluation.scope_key}>
      <div className="ws-evaluation__head">
        <span className="ws-evaluation__scope">
          {evaluation.scope_key}
          {evaluation.scope_label ? ` · ${evaluation.scope_label}` : ""}
        </span>
        {/* Presence-tested, not permission-tested (52.4) — an omitted field renders nothing. */}
        {evaluation.rule_outcome !== undefined ? (
          <span className={`ws-chip${CALM_OUTCOMES.has(evaluation.rule_outcome) ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>
            {evaluation.rule_outcome}
          </span>
        ) : null}
        {evaluation.current_decision ? (
          <span className="ws-chip--fill ws-chip--decision-fill">{evaluation.current_decision.decision_type}</span>
        ) : attention ? (
          <span className="ws-chip--flag">Decision required</span>
        ) : null}
      </div>

      <dl className="ws-facts">
        <dt>Found in contract</dt>
        <dd>{renderValue(evaluation.actual_value)}</dd>
        {evaluation.expected_value !== undefined ? (
          <>
            <dt>Company Standard</dt>
            <dd>{renderValue(evaluation.expected_value)}</dd>
          </>
        ) : null}
        {evaluation.operator ? (
          <>
            <dt>Comparison</dt>
            <dd className="ws-mono">{evaluation.operator}</dd>
          </>
        ) : null}
      </dl>

      {explanation.length > 0 ? (
        // Rule 12 — the Evidence → Fact → Standard → Rule → Result chain, in
        // the engine's own words, beside the verdict it explains.
        <details className="ws-explain">
          <summary>How this result was reached</summary>
          <ol>
            {explanation.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ol>
          <p className="ws-pane__note ws-mono">{evaluation.evaluator_version}</p>
        </details>
      ) : null}

      {evaluation.evidence_refs.length > 0 ? (
        <div className="ws-evidence">
          {evaluation.evidence_refs.map((evidenceId, index) => {
            const row = evidenceById.get(evidenceId);
            return (
              <div key={evidenceId} className="ws-evidence__item">
                <button
                  type="button"
                  className="ws-evidence__loc"
                  aria-current={target === evidenceId ? "true" : undefined}
                  onClick={() => point(evidenceId, "the cited")}
                >
                  {row
                    ? [
                        sectionRef(row.section_number),
                        row.section_title,
                        row.page_number != null ? `p.${row.page_number}` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ") || `Evidence ${index + 1}`
                    : `Evidence ${index + 1}`}
                </button>
                {row ? (
                  <blockquote className="ws-evidence__quote ws-quote">{row.content}</blockquote>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="ws-pane__note">No supporting text was found in the document for this Requirement.</p>
      )}

      {showDecision ? <DecisionControl evaluation={evaluation} onRecorded={onChanged} /> : null}
    </div>
  );
}

function scalar(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

/** Values verbatim — presentation only, no interpretation (rule 12: the server's
 *  keys and values, exactly; just never a clipped one-line JSON blob). */
function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "object" && !Array.isArray(value)) {
    return (
      <span className="ws-facts__pairs">
        {Object.entries(value as Record<string, unknown>).map(([key, entry]) => (
          <span key={key} className="ws-facts__pair">
            <span className="ws-facts__k">{key}</span>{" "}
            <span className="ws-mono">{scalar(entry)}</span>
          </span>
        ))}
      </span>
    );
  }
  return scalar(value);
}

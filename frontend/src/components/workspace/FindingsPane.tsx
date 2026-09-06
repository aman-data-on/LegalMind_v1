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

import { useCallback, useEffect, useRef, useState } from "react";

import { describeError } from "@/lib/api";
import {
  classificationLabel,
  findingStatusLabel,
  reviewStatusLabel,
  ruleOutcomeLabel,
  scopeLabel,
} from "@/lib/labels";
import { shortcutKey } from "@/lib/shortcuts";
import { sectionRef } from "@/lib/documentTypes";
import { DECISION_TYPES } from "@/lib/permissions";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, Evaluation, Evidence, Finding } from "@/lib/types";

import { AnalyzeControl } from "./AnalyzeControl";
import { ClassificationGlossary } from "./ClassificationGlossary";
import { useAskIntent } from "./askIntent";
import { DecisionControl } from "./DecisionControl";
import { EscalateControl } from "./EscalateControl";
import { useFindingsState } from "./findingsState";
import { requirementHeading, reviewOrder } from "./model";
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

  /*
   * The decision shortcuts (`d`, `a`, `r`) act on the CURRENT finding, and
   * "current" is a cursor the pane keeps — not merely whatever happens to hold
   * focus. That is the model every mail and issue tool uses, and it is the one
   * the legacy screen had: a reader can press `a`, type a justification, click
   * away to re-read a clause, and press `r` without hunting for the card again.
   * Focus still MOVES the cursor (`j`/`k` and clicking a card both set it), so
   * the two never disagree.
   *
   * `a`/`r` only ever preselect a type and focus the justification. Recording
   * stays an explicit submit (Step 31 r11; 52.7 applied to input).
   */
  const [prepared, setPrepared] = useState<
    { findingId: string; decisionType: (typeof DECISION_TYPES)[number]; seq: number } | null
  >(null);
  const cursorRef = useRef<string | null>(null);
  /** The button and the `?` key must open the SAME sheet, so the button simply
   *  raises the same key event the global handler already listens for. */
  const openShortcutHelp = useCallback(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "?", bubbles: true }));
  }, []);

  useEffect(() => {
    function remember(event: FocusEvent) {
      const card = (event.target as HTMLElement | null)?.closest?.("article[data-finding-id]");
      const id = card?.getAttribute("data-finding-id");
      if (id) cursorRef.current = id;
    }
    function onKey(event: KeyboardEvent) {
      const key = shortcutKey(event);
      if (key !== "d" && key !== "a" && key !== "r") return;
      // Default the cursor to the first finding on screen, so the keys work
      // before the reader has moved at all.
      const cards = Array.from(
        document.querySelectorAll<HTMLElement>("article[data-finding-id]"));
      const current =
        cards.find((c) => c.getAttribute("data-finding-id") === cursorRef.current)
        ?? cards[0];
      const findingId = current?.getAttribute("data-finding-id");
      if (!current || !findingId) return;
      cursorRef.current = findingId;

      if (key === "d") {
        const form = current.querySelector<HTMLElement>(".ws-decision__form");
        (form?.querySelector<HTMLSelectElement>("select")
          ?? form?.querySelector<HTMLTextAreaElement>("textarea"))?.focus();
        event.preventDefault();
        return;
      }
      setPrepared((prev) => ({
        findingId,
        decisionType: key === "a" ? "ACCEPT_DEVIATION" : "REJECT",
        seq: (prev?.seq ?? 0) + 1,
      }));
      event.preventDefault();
    }
    window.addEventListener("focusin", remember);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("focusin", remember);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

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

  if (state.kind === "not-started") {
    // A Review exists but analysis was never submitted (DRAFT/UPLOADED). The
    // honest rendering is the ACTION, not a progress line about work nobody
    // started — and `AnalyzeControl` is the same control the no-review branch
    // below offers, so there is one way to start an analysis, not two.
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
          <span className="ws-pane__note">{reviewStatusLabel(state.review.status)}</span>
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
  // Review order, not engine order (P-4, 2026-09-06): what needs a decision
  // first, then the document's own order. Presentation only — see `reviewOrder`.
  const shown = reviewOrder(
    effectiveView === "all"
      ? findings
      : effectiveView === "attention"
        ? findings.filter((f) => f.requires_decision)
        : findings.filter((f) => f.classification === effectiveView.classification));

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Findings</h2>
        {/* Export moved to the page header (DD-9) — one Download, one place. */}
        {/*
          * The Review's lifecycle state, in a reviewer's words — 2026-09-04,
          * found by porting the legacy analysis test. Locked 52.7 makes the
          * lifecycle the single progress report, and the workspace showed it
          * NOWHERE once analysis had finished: a reviewer could not tell an
          * analysed Review still awaiting a decision from one already decided
          * without opening the report. The status is the server's own value,
          * rendered through `lib/labels` like everywhere else.
          */}
        <span className="ws-pane__note">{reviewStatusLabel(review.status)}</span>
        <span className="ws-pane__note ws-mono">{findings.length} total</span>
        {/* Shortcuts nobody can find are shortcuts nobody uses — every tool that
            ships them ships a visible way in. Inline in the header where the
            keys apply, so it overlays nothing. */}
        <button type="button" className="ws-shortcut-hint" onClick={openShortcutHelp}
                aria-label="Keyboard shortcuts" title="Keyboard shortcuts (press ?)">
          ?
        </button>
      </div>
      <div className="ws-pane__body" style={{ padding: "16px" }}>
        {/* What the outcomes mean — collapsed, so it costs a working reviewer
            nothing and answers a first-time reader without asking a colleague
            (2026-09-04 audit). */}
        {findings.length > 0 ? (
          <>
            <ClassificationGlossary />
            {/* 49.7 r1 / D-1.4 — the derived summary is never presented as the
                authoritative result. Stated ONCE for the pane: it used to
                repeat on every card, which on a 14-finding review meant the
                same sentence fourteen times above the findings themselves. */}
            <p className="ws-pane__note">
              Each outcome below is a summary of the evaluations inside it, which are
              the authoritative results.
            </p>
          </>
        ) : null}
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
                <FindingCard
                  key={finding.id}
                  finding={finding}
                  onChanged={reload}
                  prepared={prepared?.findingId === finding.id
                    ? { decisionType: prepared.decisionType, seq: prepared.seq }
                    : null}
                />
              ))
            )}
          </>
        )}
      </div>
    </>
  );
}

function askQuestionFor(finding: Finding): string {
  // The same reader-facing phrase the card heading uses — the question is shown
  // to the user and sent to the assistant, and "say anything about
  // EARLY-TERM-RESTRICTION-MSA-001?" is neither a question a person would ask
  // nor one worth retrieving against.
  const name = requirementHeading(finding.requirement);
  const where = finding.evidence.find((e) => e.section_number)?.section_number;
  return finding.classification === "MISSING"
    ? `Does this document say anything about ${name}?`
    : `What does this document say about ${name}${where ? ` (§${where})` : ""}?`;
}

function FindingCard({ finding, onChanged, prepared }: {
  finding: Finding;
  onChanged: () => void;
  /** A keyboard PREPARE request the pane routed to THIS finding (`a` / `r`). */
  prepared: { decisionType: (typeof DECISION_TYPES)[number]; seq: number } | null;
}) {
  const askIntent = useAskIntent();
  const calm = CALM_CLASSIFICATIONS.has(finding.classification);
  const evidenceById = new Map(finding.evidence.map((e) => [e.id, e]));
  return (
    <article
      className={`ws-finding${finding.requires_decision ? " ws-finding--attention" : ""}`}
      data-finding-id={finding.id}
      tabIndex={-1}
    >
      <header className="ws-finding__head">
        {/* The requirement in a lawyer's words, with the code as a quiet
            reference beside it. Two fixes at once (2026-09-05): the code was
            the loudest text on the card when it is support-desk material, and
            where the ratified config gives a requirement the same value for
            `name` and `code` — which it does — this printed the identifier
            TWICE, joined by an em dash. */}
        <h3 className="ws-finding__title">
          {requirementHeading(finding.requirement)}
        </h3>
        {finding.requirement.code && finding.requirement.code !== requirementHeading(finding.requirement) ? (
          <span className="ws-finding__code ws-mono">{finding.requirement.code}</span>
        ) : null}
        <span className={`ws-chip${calm ? "" : " ws-chip--fill ws-chip--classify-fill"}`} title="Derived summary of the Evaluations below">
          {classificationLabel(finding.classification)}
        </span>
        {/* The finding's workflow position — a DIFFERENT axis from the
            evaluation's "Decision required" flag below, and kept as its own
            value. Quiet text rather than a second filled chip: the actionable
            one is the flag next to the decision control, and two shouts saying
            the same thing at the same volume is what made this card noisy. */}
        <span className="ws-finding__status">{findingStatusLabel(finding.status)}</span>
        {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
      </header>
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
          prepared={prepared}
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
  prepared,
  evaluation,
  evidenceById,
  onChanged,
}: {
  evaluation: Evaluation;
  evidenceById: Map<string, Evidence>;
  onChanged: () => void;
  /** A keyboard prepare request from the owning card — see `FindingCard`. */
  prepared: { decisionType: (typeof DECISION_TYPES)[number]; seq: number } | null;
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
          {evaluation.scope_label ?? scopeLabel(evaluation.scope_key)}
        </span>
        {/* Presence-tested, not permission-tested (52.4) — an omitted field renders nothing. */}
        {/* `ws-evaluation__outcome` is a STABLE hook, not styling: LEGAL-02 turns
            on this element being absent for a caller without
            `legal_position.view` and present for one with it, and the fill
            classes below appear only for non-calm outcomes — so asserting on
            them would pass for the wrong reason on an ACCEPTABLE result. */}
        {evaluation.rule_outcome !== undefined ? (
          <span className={`ws-evaluation__outcome ws-chip${CALM_OUTCOMES.has(evaluation.rule_outcome) ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>
            {ruleOutcomeLabel(evaluation.rule_outcome)}
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
        </details>
      ) : null}

      {/*
        * WHICH evaluator produced this, always — 2026-09-04, found by porting
        * the LEGAL-02 browser test off the legacy screen.
        *
        * This line used to live INSIDE the explanation block above, and
        * `explanation` is one of the fields LEGAL-02 omits for a caller without
        * `legal_position.view`. So an owner saw a verdict with no record of what
        * produced it, while the legacy screen showed provenance to everyone.
        * 45B.10 / AM-19 are explicit that omission removes the legal POSITION and
        * not the audit trail, and an evaluator version is provenance, not a
        * position — so it is rendered unconditionally, beside the scope it
        * belongs to.
        */}
      <p className="ws-evaluation__provenance ws-pane__note ws-mono">
        {evaluation.evaluator_version}
        {" · "}
        {evaluation.evidence_refs.length}{" "}
        {evaluation.evidence_refs.length === 1 ? "evidence reference" : "evidence references"}
      </p>

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

      {showDecision ? (
        <DecisionControl evaluation={evaluation} onRecorded={onChanged} prepared={prepared} />
      ) : null}
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
    const entries = Object.entries(value as Record<string, unknown>);
    // A single-key fact prints its value alone: the row's own label already
    // says what it is, so "Found in contract: presence ABSENT" was saying
    // "presence" three times down the column for no added meaning. Multi-key
    // facts keep their keys — there the key is the distinction (amount vs unit
    // vs basis), not noise.
    if (entries.length === 1 && entries[0]) {
      return <span className="ws-mono">{scalar(entries[0][1])}</span>;
    }
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

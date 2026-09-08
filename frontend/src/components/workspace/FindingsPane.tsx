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
import {
  classificationSentence,
  classificationTone,
  evidenceLocation,
  evidenceNote,
  excerpt,
  nextStep,
  reasoningSteps,
  requirementTitle,
  sameAsTitle,
  sideOf,
  standardSideOf,
  type Side,
} from "./findingLanguage";
import { requirementHeading, reviewOrder } from "./model";
import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconXCircle } from "./icons";
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

/** Exported for `finding-card.test.tsx`, which renders one card per
 *  classification and per evidence shape — the §10 edge-case matrix — with
 *  `renderToStaticMarkup`, the harness this project already uses. */
export function FindingCard({ finding, onChanged, prepared }: {
  finding: Finding;
  onChanged: () => void;
  /** A keyboard PREPARE request the pane routed to THIS finding (`a` / `r`). */
  prepared: { decisionType: (typeof DECISION_TYPES)[number]; seq: number } | null;
}) {
  const askIntent = useAskIntent();
  const calm = CALM_CLASSIFICATIONS.has(finding.classification);
  const evidenceById = new Map(finding.evidence.map((e) => [e.id, e]));
  const title = requirementTitle(finding.requirement);
  const meaning = classificationSentence(finding.classification);
  return (
    <article
      className={`ws-finding${finding.requires_decision ? " ws-finding--attention" : ""}`}
      data-finding-id={finding.id}
      tabIndex={-1}
    >
      {/*
        * The card answers four questions in reading order (owner, 2026-09-08):
        * what was checked, what does this document say, what does our standard
        * expect, and does someone need to act. Everything that answers none of
        * them — the requirement code, the evaluator version, the comparison
        * operator, the scope key, the engine's own notes — moved into "How this
        * was determined" below, where it is one click away and no longer the
        * loudest text on the card.
        */}
      <header className="ws-finding__head">
        {/* The status mark — owner, 2026-09-08 (fourth pass): the card's
            overall state readable before a single word of it is read, the
            same three tones `Side` already uses for the comparison below
            plus the fourth for "needs a person" — never colour alone, the
            classification chip beside it still carries the word. */}
        <span className="ws-finding__titlewrap">
          <FindingStatusMark classification={finding.classification} />
          <h3 className="ws-finding__title">{title}</h3>
        </span>
        <span className={`ws-chip${calm ? "" : " ws-chip--fill ws-chip--classify-fill"}`}
              title="Derived summary of the evaluations below">
          {classificationLabel(finding.classification)}
        </span>
        {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
      </header>
      {meaning ? <p className="ws-finding__lede">{meaning}</p> : null}
      {finding.evaluations.map((evaluation) => (
        <EvaluationCard
          key={evaluation.id}
          finding={finding}
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

/** The finding's status, as an icon in a coloured disc — reuses the existing
 *  icon set (`icons.tsx`) rather than adding a new one; `aria-hidden` because
 *  the classification chip right beside it already carries the word this
 *  icon repeats visually. */
function FindingStatusMark({ classification }: { classification: string }) {
  const tone = classificationTone(classification);
  const Icon = tone === "ok" ? IconCheckCircle
    : tone === "bad" ? IconXCircle
    : IconAlertCircle;
  return (
    <span className={`ws-finding__mark ws-finding__mark--${tone}`} aria-hidden="true">
      <Icon size={16} />
    </span>
  );
}

/** One side of the comparison: a mark, then a word. The mark is never the only
 *  signal — the word carries the same fact, so the row survives greyscale,
 *  colour-blindness and a screen reader (rule 12 / accessibility). */
function SideValue({ side }: { side: Side }) {
  // A concrete value gets no mark: a tick beside "6 MONTHS" reads as
  // "satisfied" when it is only the number the standard states.
  const mark = side.tone === "present" ? "✓"
    : side.tone === "absent" ? "✗"
    : side.tone === "unknown" ? "?" : null;
  return (
    <span className={`ws-side ws-side--${side.tone}`}>
      {mark ? <span className="ws-side__mark" aria-hidden="true">{mark}</span> : null}
      <span>{side.text}</span>
      {side.detail ? (
        // A controlled-vocabulary token, verbatim (45B.4) — never reworded.
        <span className="ws-side__detail ws-mono">{side.detail}</span>
      ) : null}
    </span>
  );
}

function EvaluationCard({
  prepared,
  finding,
  evaluation,
  evidenceById,
  onChanged,
}: {
  finding: Finding;
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
  const cited = evaluation.evidence_refs
    .map((id) => evidenceById.get(id))
    .filter((row): row is Evidence => row !== undefined);
  const steps = reasoningSteps(finding, evaluation, evaluation.evidence_refs.length);
  const action = nextStep(finding, evaluation);
  /* A scope worth naming, or none. Every requirement carries a scope key and
     most are the placeholder `GENERAL`, which as a heading said nothing while
     occupying the first line of every evaluation. And when a scope IS named,
     it usually just repeats the finding's own title in different words —
     "Residuals" under a card already titled "Residuals" (owner, 2026-09-08:
     the manager's screenshot showed exactly this row). Worth showing only
     when it adds something the title did not already say — a finding whose
     evaluations span more than one scope. */
  const rawScope = evaluation.scope_label
    ?? (evaluation.scope_key && evaluation.scope_key !== "GENERAL"
      ? scopeLabel(evaluation.scope_key) : null);
  const scope = rawScope && !sameAsTitle(rawScope, requirementTitle(finding.requirement))
    ? rawScope : null;

  return (
    <div className="ws-evaluation" data-scope={evaluation.scope_key}>
      {/*
        * The primary card's header now carries only what a reader acts on:
        * a real scope name (when it says more than the title already did)
        * and whether a decision is pending or made. The RAW rule outcome
        * ("No rule covers this", "Not acceptable") moved into "How this was
        * determined" below — it is legal-position jargon layered on top of
        * facts the NEXT STEP sentence already states in plain language, and
        * it was the loudest thing on the card in the manager's screenshot
        * (owner, 2026-09-08). The element itself is unmoved in the sense that
        * matters to LEGAL-02: `.ws-evaluation__outcome` still exists, absent
        * for a caller without `legal_position.view`, present for one with
        * it — `confidentiality.spec.ts` and `legal-access.spec.ts` assert on
        * its COUNT, not its position on the page.
        */}
      {scope || evaluation.current_decision || attention ? (
        <div className="ws-evaluation__head">
          {scope ? <span className="ws-evaluation__scope">{scope}</span> : null}
          {evaluation.current_decision ? (
            <span className="ws-chip--fill ws-chip--decision-fill">{evaluation.current_decision.decision_type}</span>
          ) : attention ? (
            <span className="ws-chip--flag">Decision required</span>
          ) : null}
        </div>
      ) : null}

      {/*
        * The comparison, as the two facts a reader came for.
        *
        * `.ws-facts` and these two `dt` strings are LEGAL-02's own proof and are
        * NOT free to rename: `confidentiality.spec.ts` reads the `dt` labels to
        * assert that "Company Standard" is ABSENT for a caller without
        * `legal_position.view` and present for one with it. So the labels stay
        * exactly as they were and only the VALUES changed — from the raw
        * `ABSENT` / `PRESENT` enums to a mark and a word.
        *
        * `Comparison: presence` used to sit here as a third row. It names the
        * operator the evaluator ran, which is a fact about the engine and not
        * about the contract; it now lives in the details block below.
        */}
      <dl className="ws-facts ws-facts--compare">
        <dt>Found in contract</dt>
        <dd><SideValue side={sideOf(evaluation.actual_value)} /></dd>
        {evaluation.expected_value !== undefined ? (
          <>
            <dt>Company Standard</dt>
            <dd><SideValue side={standardSideOf(evaluation.expected_value)} /></dd>
          </>
        ) : null}
        {/* "Next step" as a third fact in the SAME comparison, not a separate
            paragraph below it (owner, 2026-09-08, fourth pass — matching the
            reference layout's three-column card). It is still a `dt`/`dd`
            pair, still genuinely a term/definition, and CSS Grid's
            `grid-auto-flow: column` (see .ws-facts--compare in workspace.css)
            is what turns however many pairs exist — two without
            `legal_position.view`, three with it — into that many side-by-side
            columns, with no column count hardcoded either place. */}
        {action ? (
          <>
            <dt>Next step</dt>
            <dd className="ws-facts__next">{action}</dd>
          </>
        ) : null}
      </dl>

      {/*
        * "How this was determined" — rule 12's Evidence → Fact → Standard →
        * Rule → Result chain, first in the reader's language and then in the
        * engine's own words, with the identifiers last.
        *
        * It replaces a `<details>` whose entire content was two engine notes
        * ("mapping CONFIRMED for RESIDUALS-NDA-001", "absence established by
        * mapping, not by evaluator inspection") rendered as a bare numbered
        * list. Those lines are the audit trail and are kept verbatim — they are
        * simply no longer the whole answer.
        */}
      <details className="ws-determined">
        <summary>How this was determined</summary>
        <ol className="ws-determined__steps">
          {steps.map((step) => (
            <li key={step.label}>
              <span className="ws-determined__label">{step.label}</span>
              <span>{step.text}</span>
            </li>
          ))}
        </ol>
        {explanation.length > 0 ? (
          // `.ws-explain` is the second LEGAL-02 hook: the engine's own record
          // travels with `explanation`, which is omitted for a caller without
          // `legal_position.view`, and `confidentiality.spec.ts` asserts the
          // element is absent for them. Presence-tested, so that holds.
          <div className="ws-explain">
            <p className="ws-determined__label">The engine&apos;s own record</p>
            <ol>
              {explanation.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ol>
          </div>
        ) : null}
        {/* The requirement code lives here now, not on the card face
            (2026-09-08, third pass) — a raw identifier is exactly the
            "internal ID" the manager's report asked off the default-visible
            surface. A legal reviewer who needs it for an escalation or a
            support request is already one click into this disclosure by the
            time they need to quote it.

            The rule outcome and the provenance line both moved IN here
            (2026-09-08, second pass): both used to sit on the visible card by
            default — "No rule covers this" in the header, "PRESENCE-v1 · 0
            evidence references" just above the evidence — and both are
            exactly the "internal/engineering information" the manager's
            report named. Neither is deleted: rule 11/12 still require the
            chain to be reconstructible, and 45B.10/AM-19 still require
            provenance to survive a LEGAL-02 omission. They are simply no
            longer competing with the plain-language NEXT STEP for the
            reader's first look. `.ws-evaluation__outcome` and
            `.ws-evaluation__provenance` are UNCHANGED as elements — same
            classes, same conditional rendering on the same fields — so every
            LEGAL-02 test (which asserts by count/text, never by position on
            the page) holds exactly as it did. */}
        <dl className="ws-determined__tech">
          {finding.requirement.code ? (
            <>
              <dt>Requirement</dt>
              <dd className="ws-mono">{finding.requirement.code}</dd>
            </>
          ) : null}
          {evaluation.rule_outcome !== undefined ? (
            <>
              <dt>Rule outcome</dt>
              <dd>
                <span className={`ws-evaluation__outcome ws-chip${CALM_OUTCOMES.has(evaluation.rule_outcome) ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>
                  {ruleOutcomeLabel(evaluation.rule_outcome)}
                </span>
              </dd>
            </>
          ) : null}
          <dt>Finding state</dt>
          <dd>{findingStatusLabel(finding.status)}</dd>
          {/*
            * WHICH evaluator produced this, always — 2026-09-04, found by
            * porting the LEGAL-02 browser test off the legacy screen, and
            * never nested inside the `.ws-explain` block above: `explanation`
            * is omitted for a caller without `legal_position.view` and this
            * row must not be.
            */}
          <dt>Evaluator</dt>
          <dd className="ws-mono ws-evaluation__provenance">
            {evaluation.evaluator_version}
            {" · "}
            {evaluation.evidence_refs.length}{" "}
            {evaluation.evidence_refs.length === 1 ? "evidence reference" : "evidence references"}
          </dd>
          {evaluation.operator ? (
            <>
              <dt>Comparison</dt>
              <dd className="ws-mono">{evaluation.operator}</dd>
            </>
          ) : null}
          <dt>Scope</dt>
          <dd className="ws-mono">{evaluation.scope_key}</dd>
        </dl>
      </details>

      {cited.length > 0 ? (
        <div className="ws-evidence">
          {/* Always from the document under review — `finding_evidence` holds
              nothing else — so the heading says so once rather than repeating
              per passage. `source_type` says how the passage was READ, and only
              OCR and table extraction are worth a reader's attention. */}
          <div className="ws-evidence__group">
            <p className="ws-evidence__source">
              {cited.length === 1 ? "Quoted from this document"
                : `Quoted from this document · ${cited.length} passages`}
            </p>
            {cited.map((row, index) => (
              <EvidenceItem
                key={row.id}
                row={row}
                index={index}
                current={target === row.id}
                onPoint={() => point(row.id, "the cited")}
              />
            ))}
          </div>
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

/** A cited passage: where it is, what it says, and a way into the document at
 *  that exact spot. A long passage is cut at a sentence boundary with an
 *  explicit control to see the rest — never silently truncated, and never a
 *  hover-only reveal. */
function EvidenceItem({ row, index, current, onPoint }: {
  row: Evidence; index: number; current: boolean; onPoint: () => void;
}) {
  const [full, setFull] = useState(false);
  const short = excerpt(row.content);
  const truncated = short !== row.content.trim();
  const note = evidenceNote(row.source_type);
  return (
    <div className="ws-evidence__item">
      <button
        type="button"
        className="ws-evidence__loc"
        aria-current={current ? "true" : undefined}
        onClick={onPoint}
        title="Show this passage in the document"
      >
        {evidenceLocation(row, index)}
      </button>
      <blockquote className="ws-evidence__quote ws-quote">
        {full ? row.content.trim() : short}
      </blockquote>
      {note ? <p className="ws-evidence__how">{note}</p> : null}
      {truncated ? (
        <button type="button" className="ws-evidence__more"
                aria-expanded={full}
                onClick={() => setFull((open) => !open)}>
          {full ? "Show less" : "Show the full passage"}
        </button>
      ) : null}
    </div>
  );
}

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
 *   The way through  ONE button — "Review pending decisions" in the hero,
 *                    filtered on the same `requires_decision` its count comes
 *                    from. A separate "What needs a decision" section restated
 *                    that identical number and is gone (2026-09-17).
 *   Key obligations  the assist lane's descriptive extraction, grouped under
 *                    the document's own party labels — facts, never judgments.
 */

import { BusinessAngle, LegalAngle } from "./Angles";
import { ContractDecision } from "./ContractDecision";
import { useMemo } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { describeError } from "@/lib/api";
import type { Finding, ReviewProgress } from "@/lib/types";

import {
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
  reviewHeadline,
  statusCounts,
  type StatusTone,
  type UserStatus,
} from "./findingLanguage";
import { useFindingsState } from "./findingsState";
import { STAGE_LABELS, classificationLabel, contractOutcomeLabel, decidedWords } from "@/lib/labels";

import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconFileMinus, IconRefresh, IconScale } from "./icons";
import {
  classificationBucket,
  findingsSummary,
  relativeTime,
} from "./model";
import { ObligationsPanel } from "./ObligationsPanel";
import { useSideTabs } from "./WorkspaceLayout";

/** The Summary speaks the card's three words (owner, 2026-09-09 — reversing
 *  the 2026-09-01 tile correction; AM-50 r4), in the one order and the one set
 *  of tones `findingLanguage` declares: Acceptable · Requires modification ·
 *  Needs a decision, green · amber · red. The tiles, the bar, the ring and its
 *  legend all read THIS list, so the four cannot disagree. */
const STATUS_TILES = USER_STATUS_ORDER.map((status) => ({
  status,
  tone: USER_STATUS_TONE[status],
}));

/** One icon per tone, everywhere a tone is drawn (tiles, marks, legend):
 *  ✓ Matches, ! Change needed, ⚖ Needs a decision. */
export function ToneIcon({ tone, size }: { tone: StatusTone; size: number }) {
  if (tone === "ok") return <IconCheckCircle size={size} />;
  if (tone === "warn") return <IconAlertCircle size={size} />;
  return <IconScale size={size} />;
}

/** One icon per WORD (AB-104): "Missing" shares the change's amber, so its own icon
 *  (a page with a minus) tells the two apart without colour. */
export function StatusIcon({ status, size }: { status: UserStatus; size: number }) {
  if (status === "MISSING") return <IconFileMinus size={size} />;
  return <ToneIcon tone={USER_STATUS_TONE[status]} size={size} />;
}

/** How the three words are decided — the same three cards on the Summary and,
 *  collapsed, above the Findings list. Plain words, no engine vocabulary, and
 *  no claim about who decides beyond "someone with legal authority". */
export function StatusExplainer({ collapsible = false }: { collapsible?: boolean }) {
  const cards = (
    <div className="ws-explain__grid">
      <div className="ws-explain__card ws-explain__card--ok">
        <b>Matches our standard</b>
        <span>The clause is there and says what our approved position says.</span>
      </div>
      <div className="ws-explain__card ws-explain__card--warn">
        <b>Change needed</b>
        <span>The clause is there, but it differs from our approved position — our wording goes to the client.</span>
      </div>
      <div className="ws-explain__card ws-explain__card--warn">
        <b>Missing</b>
        <span>The contract has no clause on this at all — our wording needs to be added.</span>
      </div>
      {/* "…or the company has no approved position yet" used to end this line,
          and it named a case this word does not carry. A reader who opened a
          finding's details, saw "Rule outcome: No rule covers this" and then
          read this card concluded the badge above it was wrong (UX review,
          2026-09-17). It is not wrong: the word follows the CLASSIFICATION alone
          (`AM-56`, owner 2026-09-09), so a missing required clause reads
          "Requires modification" — exactly what the card above this one already
          describes — while whether a person must rule on it travels separately,
          in the finding's own state and the pending-decision count. This line
          now names what actually reaches this word: unreadable, conflicting, or
          a position the Constitution itself calls unacceptable (`AM-63`). */}
      <div className="ws-explain__card ws-explain__card--bad">
        <b>Needs a decision</b>
        <span>A person must choose, and each card says what: a figure left blank, two clauses that say different things, a figure that could not be confirmed, a standard written for another type of document, or a position the Constitution calls not negotiable. Never a rejection.</span>
      </div>
    </div>
  );
  if (!collapsible) {
    return (
      <div className="ws-explain">
        <p className="ws-explain__title">What the four statuses mean</p>
        {cards}
      </div>
    );
  }
  return (
    <details className="ws-explain ws-explain--collapsible">
      <summary>What the four statuses mean</summary>
      {cards}
    </details>
  );
}

export function AnalysisPanel({ documentVersionId }: { documentVersionId: string }) {
  const { state, reload } = useFindingsState();
  const sideTabs = useSideTabs();
  // a decision changes the open points and the recommendation: re-read them (R3)
  const refreshKey = state.kind === "ready"
    ? state.findings.map((f) => f.status).join() : "";

  return (
    <div className="ws-analysis">
      {/* The panel's own heading (2026-09-08 a11y audit). Its sections are all
          `h3`, so the document went H1 → H3 with no H2 between — a level skip
          a screen-reader user navigating by heading falls straight through.
          Visually hidden because the tab above already says "Summary" on
          screen; the outline needs the level, not a second label. */}
      <h2 className="ws-visually-hidden">Summary</h2>
      <div className="ws-analysis__updated">
        <span className="ws-pane__note">
          {state.kind === "ready" && state.review.completed_at
            ? `Updated ${relativeTime(state.review.completed_at)}`
            : ""}
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
      ) : state.kind === "not-started" ? (
        /* A Review exists and analysis was never submitted — the Findings tab
           carries the control that starts it (2026-09-04 state split). */
        <p className="ws-pane__note">
          This version has not been analysed yet — start it from the Findings tab.
        </p>
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
        <>
          {/* `AM-152` — money first for the business reader; the Legal angle (the
              status tiles and the Findings) follows. Built by the server, rendered. */}
          {/* owner, 2026-10-21: the count once, then every open point once (each
              opens its finding), then the money — one list, one set of numbers */}
          {/* AB-103 (owner, 2026-10-22): where the review stands first — one stage,
              derived by the server, the same words the Findings header shows — then the
              decision on the contract, what was decided, what is still open, the money,
              and last what the analysis found */}
          <StageLine progress={state.progress} />
          {/* AM-174: once every point is decided, a reviewer decides the contract */}
          <ContractDecision reviewId={state.review.id} reviewStatus={state.review.status}
                            refreshKey={state.findings.map((f) => f.status).join()}
                            onRecorded={reload} />
          <DecidedRow progress={state.progress} />
          <LegalAngle reviewId={state.review.id} refreshKey={refreshKey}
                      decided={new Set(state.findings.filter((f) => f.status === "RESOLVED")
                                                    .map((f) => f.id))}
                      onOpen={sideTabs ? (id) => sideTabs.openFindings({ findingId: id })
                                       : undefined} />
          <BusinessAngle reviewId={state.review.id} refreshKey={refreshKey} />
          <AnalysisSummary findings={state.findings} />
        </>
      )}
      <ObligationsPanel documentVersionId={documentVersionId} />
    </div>
  );
}

function AnalysisSummary({ findings }: { findings: Finding[] }) {
  const sideTabs = useSideTabs();
  const total = findings.length;
  const statuses = statusCounts(findings);

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
    <section className="ws-hero ws-hero--secondary" aria-labelledby="ws-our-analysis">
      {/* AB-103: what the contract says against our standards — it never changes with
          decisions (rule 14), so it follows the review's progress, never leads it */}
      <h3 id="ws-our-analysis" className="ws-angle__title">Our analysis of the contract</h3>
      <div className="ws-tiles">
        {STATUS_TILES.map(({ status, tone }) => (
          <button
            key={status}
            type="button"
            className={`ws-tile ws-tile--${tone}`}
            aria-label={`Show the ${statuses[status]} ${USER_STATUS_LABELS[status]} finding${statuses[status] === 1 ? "" : "s"}`}
            onClick={() => sideTabs?.openFindings({ status })}
            disabled={statuses[status] === 0}
          >
            <span className="ws-tile__n">{statuses[status]}</span>
            <span className="ws-tile__label">{USER_STATUS_LABELS[status]}</span>
            {/* Never colour alone: the word above, the icon beside it. */}
            <span className={`ws-status ws-status--${tone}`}>
              <StatusIcon status={status} size={18} />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}



/** Who acts next, in a reader's words (AM-179). */
function nextWords(progress: ReviewProgress): string | null {
  const { who, name } = progress.next;
  if (progress.stage === "SUPERSEDED") return null;
  if (who === "owner") {
    if (progress.stage === "NOT_SENT") return `Next: ${name ?? "the contract's owner"} sends it to a reviewer.`;
    if (progress.stage === "ANALYSIS_FAILED") return `Next: ${name ?? "the contract's owner"} runs the analysis again.`;
    return `Next: ${name ?? "the contract's owner"} acts on it.`;
  }
  if (who === "reviewer") return `Next: ${name ?? "the reviewer"} decides.`;
  if (who === "legal") return "Next: a Legal reviewer decides.";
  return null;
}

/** Where the review stands — the first thing the Summary says (AB-103). */
export function StageLine({ progress }: { progress: ReviewProgress | null }) {
  const sideTabs = useSideTabs();
  if (!progress) return null;
  const { stage, required, decided, clarification, to_decide } = progress;
  const label = STAGE_LABELS[stage] ?? stage;
  const who = stage === "WITH_LEGAL" && progress.assignee ? ` — ${progress.assignee.name}` : "";
  const outcome = stage === "COMPLETE" && progress.outcome
    ? `: ${contractOutcomeLabel(progress.outcome)}` : "";
  const counted = required > 0 && stage !== "SUPERSEDED";
  return (
    <section className="ws-stage" aria-label="Where this review stands">
      <p className="ws-stage__line"><strong>{label}{who}{outcome}</strong></p>
      {counted ? (
        <>
          <progress className="ws-stage__bar" value={decided} max={required}
                    aria-label={`${decided} of ${required} points decided`} />
          <p className="ws-stage__count">
            {decided} of {required} point{required === 1 ? "" : "s"} decided
            {clarification ? ` · ${clarification} awaiting the client` : ""}
          </p>
        </>
      ) : null}
      {stage === "COMPLETE" && progress.outcome === "SIGN_WITH_CHANGES" ? (
        <p className="ws-stage__note">
          Changes to send; the revised version will be reviewed. A complete review is not
          approval to sign.
        </p>
      ) : null}
      {nextWords(progress) ? <p className="ws-stage__next">{nextWords(progress)}</p> : null}
      {sideTabs && to_decide + clarification > 0 ? (
        <button type="button" className="ws-hero__cta"
                onClick={() => sideTabs.openFindings({ state: to_decide ? "to_decide" : "clarification" })}>
          {to_decide ? "Review the points to decide" : "See what awaits the client"}
          {" "}<b className="ws-hero__ctan">{to_decide || clarification}</b>
        </button>
      ) : null}
    </section>
  );
}

/** What was decided, by kind — each opens those points (AB-103). */
export function DecidedRow({ progress }: { progress: ReviewProgress | null }) {
  const sideTabs = useSideTabs();
  const kinds = Object.entries(progress?.decided_by_type ?? {}).filter(([, n]) => n > 0);
  if (!progress || kinds.length === 0) return null;
  return (
    <section className="ws-decided" aria-labelledby="ws-decided-title">
      <h3 id="ws-decided-title" className="ws-angle__title">What was decided</h3>
      <ul className="ws-decided__list">
        {kinds.map(([type, n]) => (
          <li key={type}>
            <button type="button" className="ws-decided__item"
                    onClick={() => sideTabs?.openFindings({ decision: type })}
                    disabled={!sideTabs}>
              <span className="ws-decided__n">{n}</span> {decidedWords(type)}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

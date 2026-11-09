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

import { BusinessAngle, LegalAngle, useReviewAngles } from "./Angles";
import { ContractDecision } from "./ContractDecision";
import { ReanalyseNotice } from "./ReanalyseNotice";
import { useMemo, useState } from "react";
import { analyseVersion } from "@/lib/analysisChain";
import { sectionRef } from "@/lib/documentTypes";

import { describeError } from "@/lib/api";
import type { DealCounts, Finding, NegotiationStage, ReviewProgress } from "@/lib/types";

import {
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
  pointAnswer,
  pointState,
  reviewHeadline,
  statusCounts,
  userStatus,
  type StatusTone,
  type UserStatus,
} from "./findingLanguage";
import { useFindingsState } from "./findingsState";
import { STAGE_LABELS, changesWords, contractOutcomeLabel, decidedWords, pointsWords, stageWords, withoutSectionRefs,
         type StageViewer } from "@/lib/labels";

import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconFileMinus, IconRefresh, IconScale } from "./icons";
import {
  classificationBucket,
  findingsSummary,
  relativeTime,
  showsLegalDetails,
} from "./model";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { ObligationsPanel } from "./ObligationsPanel";
import { OfferSection } from "./OfferPlaybook";
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
        <span>The clause differs from our approved position. Our wording goes to the client.</span>
      </div>
      <div className="ws-explain__card ws-explain__card--warn">
        <b>Missing</b>
        <span>The contract has no clause on this. Our wording needs to be added.</span>
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
        <span>A person must choose, and each card says what: a figure left blank, two clauses that say different things, a figure that could not be confirmed, a standard written for another type of document, or a point our standards say is not negotiable. Never a rejection.</span>
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

/** Verifier item 5: an amendment starts from the agreed text, kept for reference only. */
export const REFERENCE_COPY_NOTE =
  "This is the contract as agreed, copied for reference. It is not reviewed again: upload the amendment's "
  + "own document, or prepare it, and that is what Legal reviews.";
export const SIGNED_COPY_NOTE =
  "This is the signed copy, filed with the signing record. Its terms were reviewed on the agreed version before signing.";

export function AnalysisPanel({ documentVersionId, stage = null, viewer = "owner", counts, signedCopy = false, isOwner = false,
  referenceCopy = false }: {
  /** an amendment's first version: the agreed text, reference only (verifier item 5) */
  referenceCopy?: boolean;
  documentVersionId: string;
  /** the reader owns the contract — only they may start its analysis (presentation only) */
  isOwner?: boolean;
  /** the FINAL_SIGNED version: filed, never analysed (the server refuses a Review of it) */
  signedCopy?: boolean;
  /** The header's one status (`AM-291` r4) — the Summary repeats its words, never a second. */
  stage?: NegotiationStage | null;
  viewer?: StageViewer;
  /** `AM-291` — the server's one `counts` object: the line and the stage chip agree. */
  counts?: DealCounts | undefined;
}) {
  const { state, reload, reference } = useFindingsState();
  const { can } = useSession();
  const legal = showsLegalDetails(can);
  const sideTabs = useSideTabs();
  // a decision changes the open points and the recommendation: re-read them (R3)
  const refreshKey = state.kind === "ready"
    ? state.findings.map((f) => f.status).join() : "";
  const angles = useReviewAngles(state.kind === "ready" ? state.review.id : null, refreshKey);

  return (
    <div className="ws-analysis">
      {/* The panel's own heading (2026-09-08 a11y audit). Its sections are all
          `h3`, so the document went H1 → H3 with no H2 between — a level skip
          a screen-reader user navigating by heading falls straight through.
          Visually hidden because the tab above already says "Summary" on
          screen; the outline needs the level, not a second label. */}
      <div className="ws-analysis__updated">
        <h2 id="ws-sum-attention" className="ws-summary__h2">What needs attention</h2>
        <button type="button" className="ws-toolbtn" aria-label="Refresh analysis"
                title={state.kind === "ready" && state.review.completed_at
                  ? `Updated ${relativeTime(state.review.completed_at)}` : "Refresh"}
                onClick={reload}>
          <IconRefresh size={14} />
        </button>
      </div>
      {state.kind === "loading" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Loading the analysis…
        </p>
      ) : state.kind === "no-review" ? (
        /* "no-review" is also a review outside this reader's scope (REC-09/AM-174: Legal's
           scope ends when it is CLOSED; SEC-07 hides that it exists) — so never claim the
           version was not analysed */
        <>
          <p className="ws-pane__note">{signedCopy ? SIGNED_COPY_NOTE : referenceCopy ? REFERENCE_COPY_NOTE
            : "No analysis of this version to show you."}</p>
          {/* AM-317 r6: the owner can start it — a scan read while nobody watched */}
          {isOwner && !signedCopy && !referenceCopy && can(P.REVIEW_CREATE)
            ? <AnalyseNow versionId={documentVersionId} onDone={reload} /> : null}
        </>
      ) : state.kind === "not-started" ? (
        /* A Review exists and analysis was never submitted — the Points tab
           carries the control that starts it (2026-09-04 state split). */
        <p className="ws-pane__note">
          This version has not been analysed yet — start it from the Points tab.
        </p>
      ) : state.kind === "in-flight" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Analysis is running — this panel fills in when it completes.
        </p>
      ) : state.kind === "failed" ? (
        <p className="ws-pane__note">
          The analysis could not be completed — the Points tab has the details.
        </p>
      ) : state.kind === "error" ? (
        <p className="ws-pane__note">{describeError(state.error)}</p>
      ) : (
        <>
          <ReanalyseNotice documentVersionId={documentVersionId}
                           snapshotId={state.review.configuration_snapshot_id}
                           onStarted={reload} />
          {/* S1 — two questions, in the order a person asks them: what needs me (where
              the review stands, the decision on the contract, the open points), then
              what the contract commits us to. The engine's tallies are Legal details. */}
          <section className="ws-summary__part" aria-labelledby="ws-sum-attention">
            <AttentionLine progress={state.progress} stage={stage} viewer={viewer}
                           canDecide={!reference && can(P.LEGAL_DECISION)} counts={counts} />
            {/* AM-174: once every point is decided, a reviewer decides the contract */}
            <ContractDecision reviewId={state.review.id} reviewStatus={state.review.status}
                              refreshKey={state.findings.map((f) => f.status).join()}
                              onRecorded={reload} readOnly={reference} />
            {/* AM-318: a Final deal has nothing open and nothing left to offer */}
            {reference || stage?.stage === "FINAL" ? null : <LegalAngle reviewId={state.review.id} refreshKey={refreshKey} withRecommendation={false}
                        allDecided={counts?.points_open === 0}
                        decided={new Set(state.findings.filter((f) => !OPEN_STATES.has(pointState(f)))
                                                      .map((f) => f.id))}
                        onOpen={sideTabs ? (id) => sideTabs.openFindings({ findingId: id })
                                         : undefined}
                        words={new Map(state.findings.map((f) => [f.id, {
                          reader: USER_STATUS_LABELS[userStatus(f)],
                          answer: pointAnswer(f, can(P.LEGAL_DECISION),
                                              state.progress?.stage !== "NOT_SENT") }]))} />}
          </section>
          {/* AM-305: how far the deal owner may go without Legal */}
          {reference || stage?.stage === "FINAL" ? null : <OfferSection contractId={state.review.contract_id} />}
          <section className="ws-summary__part" aria-labelledby="ws-sum-terms">
            <h3 id="ws-sum-terms" className="ws-summary__title">Key terms</h3>
            <BusinessAngle reviewId={state.review.id} refreshKey={refreshKey} />
            <ObligationsPanel documentVersionId={documentVersionId} />
          </section>
          {legal ? (
            <details className="ws-summary__legal">
              <summary>Legal details</summary>
              {/* AM-291 r4/r6: where the review stands and the recommendation are the
                  engine's account — here, never a second status beside the header's */}
              <StageLine progress={state.progress} />
              <Recommendation reviewId={state.review.id} refreshKey={refreshKey} />
              <DecidedRow progress={state.progress} />
              <AnalysisSummary findings={state.findings} />
            </details>
          ) : null}
        </>
      )}
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
          Analysis complete. None of our standards produced a finding.
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
    if (progress.stage === "NOT_SENT") return `Next: ${name ?? "the contract's owner"} sends it to Legal.`;
    if (progress.stage === "ANALYSIS_FAILED") return `Next: ${name ?? "the contract's owner"} runs the analysis again.`;
    return `Next: ${name ?? "the contract's owner"} acts on it.`;
  }
  if (who === "reviewer") return `Next: ${name ?? "the reviewer"} decides.`;
  if (who === "legal") return "Next: a Legal reviewer decides.";
  return null;
}

/** Where the review stands — the first thing the Summary says (AB-103).
 *
 *  S1b — ONE count. `required` (review_progress) is every point Legal must decide:
 *  to decide + awaiting the client + already decided. It is the same set the
 *  recommendation counts ("N must change and Legal must look at M more", N + M =
 *  required) and the open points less those the approved rule already accepts in our
 *  favour, which stay listed. Nothing is hidden; each number names what it counts.
 *  `canDecide` (legal.decision) chooses the action: a holder reviews the points, the
 *  deal owner sends the contract to Legal or sees that Legal has it. */
export function StageLine({ progress }: { progress: ReviewProgress | null }) {
  if (!progress) return null;
  const { stage, required, decided, clarification } = progress;
  const label = STAGE_LABELS[stage] ?? stage;
  const who = stage === "WITH_LEGAL" && progress.assignee ? ` — ${progress.assignee.name}` : "";
  const outcome = stage === "COMPLETE" && progress.outcome
    ? `: ${contractOutcomeLabel(progress.outcome)}` : "";
  const counted = required > 0 && stage !== "SUPERSEDED";
  const plural = required === 1 ? "point needs" : "points need";
  const done = decided === required ? (required === 1 ? "decided" : `all ${decided} decided`)
    : `${decided} decided so far`;
  const count = `${required} ${plural} Legal — ${done}`;
  return (
    <section className="ws-stage" aria-label="Where this review stands">
      <p className="ws-stage__line"><strong>{label}{who}{outcome}</strong></p>
      {counted ? (
        <>
          <progress className="ws-stage__bar" value={decided} max={required}
                    aria-label={count} />
          <p className="ws-stage__count">
            {count}
            {clarification ? ` · ${clarification} awaiting the client` : ""}
          </p>
        </>
      ) : null}
      {stage === "COMPLETE" && progress.outcome === "SIGN_WITH_CHANGES" ? (
        <p className="ws-stage__note">
          Send the changes; the revised version will be reviewed. Legal&rsquo;s review is done, but signing is still your decision.
        </p>
      ) : null}
      {nextWords(progress) ? <p className="ws-stage__next">{nextWords(progress)}</p> : null}
    </section>
  );
}

/** The points still open on the Summary: to decide, or waiting for the client. */
const OPEN_STATES = new Set(["to_decide", "clarification"]);

/** The Summary's first lines (page 2, `AM-291` r3/r4): the header's own stage word, then
 *  ONE count in words — the open points, and who has them — then the client's changes
 *  still to answer. A holder of `legal.decision` gets the act as a secondary button; the
 *  deal owner sends from the header's "Send to Legal…" (one way, one place). */
export function AttentionLine({ progress, stage, viewer, canDecide, counts }: {
  progress: ReviewProgress | null;
  stage: NegotiationStage | null;
  viewer: StageViewer;
  canDecide: boolean;
  counts?: DealCounts | undefined;
}) {
  const open = counts?.points_open ?? 0;
  const waiting = progress?.clarification ?? 0;
  const decided = progress?.decided ?? 0;
  // a signed contract tells one story: the stage, and the review kept for reference —
  // no open-point counter, no progress bar (owner item (b))
  const signed = stage?.stage === "SIGNED";
  const final = stage?.stage === "FINAL";                        // AM-318: the end
  if (final) {
    return <div className="ws-attn"><p className="ws-attn__count">Nothing left to do. Final contract ready.</p></div>;
  }
  const counted = !signed && progress && progress.required > 0 && progress.stage !== "SUPERSEDED";
  const points = pointsWords(counts, viewer);
  const changes = signed ? null : changesWords(counts, viewer);
  return (
    <div className="ws-attn">
      {/* the stage is the header's; the Summary starts at the count */}
      {counted && points ? (
        <>
          <p className="ws-attn__count">
            {summaryCount({ points, open, canDecide, notSent: progress.stage === "NOT_SENT",
                            assignee: progress.assignee?.name, waiting, decided, required: progress.required })}
          </p>
          {/* a meter only once something is decided: an empty bar reads as a divider */}
          {decided ? (
            <progress className="ws-stage__bar" value={decided} max={progress.required}
                      aria-label={`${decided} of ${progress.required} points decided`} />
          ) : null}
        </>
      ) : null}
      {signed ? <p className="ws-attn__count">The review is kept for reference.</p> : null}
      {changes ? <p className="ws-attn__changes">{changes}</p> : null}
    </div>
  );
}

/** The Summary's count as sentences: "1 open point needs Legal. Not sent yet." /
 *  "3 open points are with Legal. 1 of 4 decided." The verb agrees with the count. */
export function summaryCount({ points, open, canDecide, notSent, assignee, waiting, decided, required }: {
  points: string; open: number; canDecide: boolean; notSent: boolean; assignee?: string | undefined;
  waiting: number; decided: number; required: number;
}): string {
  const one = open === 1;
  const lead = !open ? (decided === required ? "Every point is decided" : points)
    : canDecide ? points
    : notSent ? `${points} ${one ? "needs" : "need"} Legal. Not sent yet`
    : `${points} ${one ? "is" : "are"} with ${assignee ?? "Legal"}`;
  return [lead,
          waiting ? `${waiting} waiting for the client` : null,
          decided && open ? `${decided} of ${required} decided` : null,
  ].filter(Boolean).join(". ") + ".";
}

/** The review's recommendation sentence (`AM-156` r5's action, AM-291 r6: Legal details). */
function Recommendation({ reviewId, refreshKey }: { reviewId: string; refreshKey: string }) {
  const angles = useReviewAngles(reviewId, refreshKey);
  return angles?.recommendation
    ? <p className="ws-attn__rec">{withoutSectionRefs(angles.recommendation)}</p> : null;
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

/** "Analyse now" — the empty Summary's one action for the contract's owner. */
function AnalyseNow({ versionId, onDone }: { versionId: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function start() {
    setBusy(true);
    setError(null);
    try {
      await analyseVersion(versionId);
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <p className="ws-pane__note">
      <button type="button" className="ws-btn ws-btn--sm" disabled={busy} onClick={() => void start()}>
        {busy ? "Analysing…" : "Analyse now"}
      </button>
      {error ? <span role="alert"> {error}</span> : null}
    </p>
  );
}

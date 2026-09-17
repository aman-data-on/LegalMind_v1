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

import { useMemo } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { describeError } from "@/lib/api";
import type { Finding } from "@/lib/types";

import {
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
  reviewHeadline,
  statusCounts,
  type StatusTone,
} from "./findingLanguage";
import { useFindingsState } from "./findingsState";
import { classificationLabel } from "@/lib/labels";

import { useHighlight } from "./highlight";
import { IconAlertCircle, IconCheckCircle, IconRefresh, IconScale } from "./icons";
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
const STATUS_SUB: Record<string, string> = {
  ACCEPTABLE: "Constitution match",
  REQUIRES_MODIFICATION: "Deviation or missing",
  NEEDS_DECISION: "Unclear, conflicting or no position",
};

const STATUS_TILES = USER_STATUS_ORDER.map((status) => ({
  status,
  tone: USER_STATUS_TONE[status],
  sub: STATUS_SUB[status] ?? "",
}));

/** One icon per tone, everywhere a tone is drawn (tiles, marks, legend):
 *  ✓ Acceptable, ! Requires modification, ⚖ Needs a decision. */
export function ToneIcon({ tone, size }: { tone: StatusTone; size: number }) {
  if (tone === "ok") return <IconCheckCircle size={size} />;
  if (tone === "warn") return <IconAlertCircle size={size} />;
  return <IconScale size={size} />;
}

/** How the three words are decided — the same three cards on the Summary and,
 *  collapsed, above the Findings list. Plain words, no engine vocabulary, and
 *  no claim about who decides beyond "someone with legal authority". */
export function StatusExplainer({ collapsible = false }: { collapsible?: boolean }) {
  const cards = (
    <div className="ws-explain__grid">
      <div className="ws-explain__card ws-explain__card--ok">
        <b>Match → Acceptable</b>
        <span>The clause matches the company&rsquo;s approved position.</span>
      </div>
      <div className="ws-explain__card ws-explain__card--warn">
        <b>Deviation or missing → Requires modification</b>
        <span>The clause differs from the approved position, or a required clause is absent — a specific change would resolve it.</span>
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
        <b>Unclear, conflicting, or not negotiable → Needs a decision</b>
        <span>The wording is unclear, two provisions conflict, the value could not be read, or the Constitution names the position unacceptable. Never a rejection — a person decides.</span>
      </div>
    </div>
  );
  if (!collapsible) {
    return (
      <div className="ws-explain">
        <p className="ws-explain__title">How the three statuses are decided</p>
        {cards}
      </div>
    );
  }
  return (
    <details className="ws-explain ws-explain--collapsible">
      <summary>How the three statuses are decided</summary>
      {cards}
    </details>
  );
}

export function AnalysisPanel({ documentVersionId }: { documentVersionId: string }) {
  const { state, reload } = useFindingsState();

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
        <AnalysisSummary findings={state.findings} />
      )}
      <ObligationsPanel documentVersionId={documentVersionId} />
    </div>
  );
}

function AnalysisSummary({ findings }: { findings: Finding[] }) {
  const sideTabs = useSideTabs();
  const summary = findingsSummary(findings);

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

  const pct = (n: number) => `${Math.round((n / total) * 100)}%`;
  return (
    <>
      {/* The hero — the owner's reference layout (2026-09-09): the one sentence
          a reader needs and the way through to what needs a person, then the
          three tiles on the left and the ring on the right. Counts only: no
          score, no grade, no severity ranking (rule 12). */}
      <section className="ws-hero" aria-label="Status summary">
        <div className="ws-hero__top">
          <div className="ws-hero__words">
            <p className="ws-analysis__headline">
              {reviewHeadline({
                total,
                needsDecision: summary.needsDecision,
                missing: statuses.REQUIRES_MODIFICATION,
                match: statuses.ACCEPTABLE,
              })}
            </p>
            <p className="ws-hero__sub">
              Five determinations — match, deviation, missing, unclear or conflicting, no
              position — shown as three statuses.
            </p>
          </div>
          {/* Points with the same field the count is taken from
              (`requires_decision`). Pointing with the reader status
              NEEDS_DECISION instead showed "No findings in this view" for every
              document whose pending items read "Requires modification" — which
              is most of them. */}
          {sideTabs && summary.needsDecision > 0 ? (
            <button
              type="button"
              className="ws-hero__cta"
              onClick={() => sideTabs.openFindings({ requiresDecision: true })}
            >
              Review pending decisions <b className="ws-hero__ctan">{summary.needsDecision}</b>
            </button>
          ) : null}
        </div>
        <div className="ws-hero__grid">
          <div className="ws-hero__left">
            <div className="ws-analysis__head">
              <h3 className="ws-analysis__title">Status breakdown</h3>
              {sideTabs ? (
                <button type="button" className="ws-viewall" onClick={() => sideTabs.openFindings()}>
                  View all in Findings
                </button>
              ) : null}
            </div>
            {/* Exactly three tiles (owner, 2026-09-09) — how many need a legal
                decision is the button above and the line below, never a tile.
                A zero tile stays visible and inert, so the three words are
                always in the same three places. */}
            <div className="ws-tiles">
              {STATUS_TILES.map(({ status, tone, sub }) => (
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
                  <span className="ws-tile__sub">{sub} ({pct(statuses[status])})</span>
                  {/* Never colour alone: the word above, the icon beside it. */}
                  <span className={`ws-status ws-status--${tone}`}>
                    <ToneIcon tone={tone} size={18} />
                  </span>
                </button>
              ))}
            </div>
            <div
              className="ws-bar"
              role="img"
              aria-label={STATUS_TILES.filter(({ status }) => statuses[status] > 0)
                .map(({ status }) => `${statuses[status]} ${USER_STATUS_LABELS[status]}`).join(", ")}
            >
              {STATUS_TILES.map(({ status, tone }) =>
                statuses[status] > 0 ? (
                  <span key={status} className={`ws-bar__seg ws-bar__seg--${tone}`} style={{ flexGrow: statuses[status] }} />
                ) : null,
              )}
            </div>
            <p className="ws-pane__note ws-hero__total">
              Total requirements analyzed: <span className="ws-mono">{total}</span>
            </p>
            <StatusExplainer />
          </div>
          <section className="ws-hero__right" aria-label="At a glance">
            <h3 className="ws-analysis__title">At a glance</h3>
            <div className="ws-ring">
              <Donut
                segments={STATUS_TILES.map(({ status, tone }) => ({
                  tone, label: USER_STATUS_LABELS[status], n: statuses[status],
                }))}
                total={total}
              />
              <ul className="ws-ring__legend">
                {STATUS_TILES.map(({ status, tone }) => (
                  <li key={status} data-tone={tone}>
                    <button
                      type="button"
                      className="ws-ring__go"
                      aria-label={`Show the ${statuses[status]} ${USER_STATUS_LABELS[status]} finding${statuses[status] === 1 ? "" : "s"}`}
                      onClick={() => sideTabs?.openFindings({ status })}
                      disabled={statuses[status] === 0}
                    >
                      <span className="ws-ring__swatch" aria-hidden="true" />
                      <span className="ws-ring__word">{USER_STATUS_LABELS[status]}</span>
                      <span className="ws-mono">{statuses[status]}</span>
                      <span className="ws-ring__pct">({pct(statuses[status])})</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      </section>

      {/*
        * SAID ONCE (2026-09-17). A "What needs a decision" section stood here,
        * reading "<n> findings need a legal decision. Open the list →".
        *
        * Its count was `findingsNeedingDecision(findings).length` and the hero's
        * is `summary.needsDecision`; both count `requires_decision`, so the two
        * were always the same number. A reader met that number four times in one
        * panel — the headline, the hero button, the ring, and here — and three
        * buttons that all led to the Findings tab. The 2026-09-04 audit removed a
        * card-per-finding from this section for the same reason and left the
        * count behind; this removes what was left of the repetition.
        *
        * Its "Open the list →" also opened ALL findings while the sentence above
        * it named the ones needing a decision — the same mismatch between what a
        * control promises and what it filters that made the hero button land on
        * an empty pane. The hero button now points at `requiresDecision` and is
        * the one way through. "View all in Findings", beside the breakdown, is a
        * different destination and stays.
        *
        * Nothing is lost when the count is zero either: `reviewHeadline` already
        * says "Nothing is waiting on a decision."
        */}
    </>
  );
}

/** Real counts as a three-part donut. The center is the raw total — no
 *  percentage-as-verdict, no invented score (rule 12). */
/** The ring reads the caller's ordered segments — it used to take three
 *  positional counts named for the engine's old buckets, which is where the
 *  legend and the ring could drift apart from the tiles above them. */
function Donut({ segments, total }: {
  segments: Array<{ tone: StatusTone; label: string; n: number }>; total: number;
}) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const start = circumference / 4; // 12 o'clock
  let consumed = 0;
  return (
    <svg
      className="ws-ring__svg"
      viewBox="0 0 92 92"
      role="img"
      aria-label={`${total} findings: ${segments
        .filter(({ n }) => n > 0)
        .map(({ n, label }) => `${n} ${label}`)
        .join(", ")}`}
    >
      {segments.map(({ tone, n }) => {
        if (n === 0) return null;
        const length = (n / total) * circumference;
        const offset = start - consumed;
        consumed += length;
        return (
          <circle
            key={tone}
            className={`ws-ring__seg ws-ring__seg--${tone}`}
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


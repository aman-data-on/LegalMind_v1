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
const STATUS_TILES = USER_STATUS_ORDER.map((status) => ({
  status,
  tone: USER_STATUS_TONE[status],
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
  const sideTabs = useSideTabs();

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
          <AnalysisSummary findings={state.findings} />
          <LegalAngle reviewId={state.review.id}
                      onOpen={sideTabs ? (id) => sideTabs.openFindings({ findingId: id })
                                       : undefined} />
          <BusinessAngle reviewId={state.review.id} />
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

  // One set of numbers (owner, 2026-10-21): the three tiles, and "open" as their sum —
  // never a second count taken from another field.
  const open = statuses.REQUIRES_MODIFICATION + statuses.NEEDS_DECISION;
  return (
    <section className="ws-hero" aria-label="Status summary">
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
              <ToneIcon tone={tone} size={18} />
            </span>
          </button>
        ))}
      </div>
      <div className="ws-hero__top">
        <p className="ws-analysis__headline">
          {open === 0
            ? `All ${total} point${total === 1 ? "" : "s"} match our standards.`
            : `${open} open point${open === 1 ? "" : "s"} — ${statuses.REQUIRES_MODIFICATION} `
              + `need${statuses.REQUIRES_MODIFICATION === 1 ? "s" : ""} a change, `
              + `${statuses.NEEDS_DECISION} need${statuses.NEEDS_DECISION === 1 ? "s" : ""} `
              + "a decision."}
        </p>
        {sideTabs && open > 0 ? (
          <button type="button" className="ws-hero__cta"
                  onClick={() => sideTabs.openFindings({ open: true })}>
            Review open points <b className="ws-hero__ctan">{open}</b>
          </button>
        ) : null}
      </div>
    </section>
  );
}


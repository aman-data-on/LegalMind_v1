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
  findingsNeedingDecision,
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
        <span>The clause differs from the approved position, or a required clause is absent.</span>
      </div>
      <div className="ws-explain__card ws-explain__card--bad">
        <b>Unclear or no position → Needs a decision</b>
        <span>The wording is unclear or conflicting, or the company has no approved position yet.</span>
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
  const risks = findingsNeedingDecision(findings);

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
          {sideTabs && summary.needsDecision > 0 ? (
            <button
              type="button"
              className="ws-hero__cta"
              onClick={() => sideTabs.openFindings({ status: "NEEDS_DECISION" })}
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


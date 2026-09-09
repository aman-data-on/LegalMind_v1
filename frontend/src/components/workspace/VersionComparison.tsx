"use client";

/**
 * What changed between two versions of one document — locked 33.15, owner
 * decision 2026-09-04 (#3).
 *
 * Locked 33.15 names both the feature and the method: *"deterministic
 * document/section comparison"*, explicitly not LLM/RAG. All of that happens on
 * the server (rule 18 — the UI derives nothing legal), so this component
 * renders an answer and computes none of it. Even the alignment key is the
 * server's, and it says so on screen: a reader is entitled to know that clauses
 * were paired by the document's own numbering.
 *
 * 33.16 is the line the SCREEN must not cross. It may show
 *
 *     §17.2  changed    "Unlimited"  ->  "12 months"
 *
 * and must never let a reader take that as acceptable, unacceptable, approved
 * or rejected. So the status words describe the TEXT (added / removed / changed
 * / unchanged) and are styled neutrally — no red for "changed", no green for
 * "unchanged", because colour is the fastest way to smuggle in a verdict the
 * engine never made. Where the evaluator has a Finding on a changed clause it
 * is quoted beside it, labelled as the analysis's — read-only, because a
 * comparison is not the place to record anything (33.16); the Findings tab is.
 *
 * Deliberately NOT a Word-style visual diff (the owner's own boundary): no
 * intra-sentence word colouring, no redline. The full text of either version is
 * one click away in the document pane.
 *
 * HOW A REVISION READS (design pass, 2026-09-05). The current wording leads and
 * the superseded wording sits beneath it, quieter and rule-marked — the order a
 * person actually reads a revision in ("this is what it says; this is what it
 * used to say"), rather than two equal columns that ask them to diff by eye.
 * The quiet is about TIME, not acceptability: 33.16 forbids the second reading
 * and nothing here supplies it. Quoted contract text uses the house serif quote
 * role, the same one the report and the findings pane use, because contract
 * wording looks like contract wording everywhere in this product.
 *
 * Unchanged clauses are collapsed behind a toggle rather than dropped — a
 * comparison that shows only the differences cannot answer "did the rest of the
 * document stay put?", which is the second question anyone asks.
 */

import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { sectionRef } from "@/lib/documentTypes";
import { USER_STATUS_LABELS, requirementTitle, userStatus } from "./findingLanguage";
import type { ClauseChange, DocumentVersion, VersionComparison as Comparison } from "@/lib/types";

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; comparison: Comparison };

/** The summary as a sentence rather than a row of tiles.
 *
 *  The product writes in plain sentences everywhere else, and four counts read
 *  as a dashboard when the reader has one question: how much moved? So the
 *  zeroes are dropped — "0 removed" is noise — and the unchanged count trails
 *  as context rather than competing as a fourth statistic. */
function countSentence(summary: Comparison["summary"]): string {
  const moved = [
    summary.CHANGED ? `${summary.CHANGED} clause${summary.CHANGED === 1 ? "" : "s"} changed` : null,
    summary.ADDED ? `${summary.ADDED} added` : null,
    summary.REMOVED ? `${summary.REMOVED} removed` : null,
  ].filter(Boolean);
  const tail = `${summary.UNCHANGED} untouched`;
  return moved.length === 0 ? `Nothing changed \u2014 ${tail}.` : `${moved.join(", ")}, ${tail}.`;
}

/** Text-only status words. See the note above on why they carry no colour. */
const STATUS_TEXT: Record<ClauseChange["status"], string> = {
  ADDED: "new clause",
  REMOVED: "clause gone",
  CHANGED: "wording changed",
  UNCHANGED: "unchanged",
};

export function VersionComparison({
  contractId,
  versions,
}: {
  contractId: string;
  /** Newest first, as the contract detail returns them. */
  versions: DocumentVersion[];
}) {
  const newest = versions[0];
  const previous = versions[1];
  const [before, setBefore] = useState(previous?.id ?? "");
  const [after, setAfter] = useState(newest?.id ?? "");
  const [showUnchanged, setShowUnchanged] = useState(false);
  const [state, setState] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    if (!before || !after) return;
    let cancelled = false;
    setState({ kind: "loading" });
    api
      .versionComparison(contractId, before, after)
      .then((comparison) => {
        if (!cancelled) setState({ kind: "ready", comparison });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ kind: "error", message: describeError(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [contractId, before, after]);

  if (!newest || !previous) return null;

  const label = (version: DocumentVersion) => `Version ${version.version_number}`;

  return (
    <section className="ws-compare" aria-label="Compare versions">
      {/* The header reads as a statement of what is on screen, not as a form:
          "Version 1 → Version 2", the two selects styled as the words they
          replace. The arrow is a real relationship between two versions — a
          direction in time — not link decoration. */}
      <div className="ws-compare__head">
        <div className="ws-compare__pair">
          <label className="ws-compare__pick">
            <span className="ws-visually-hidden">Earlier version</span>
            <select value={before} onChange={(event) => setBefore(event.target.value)}>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {label(version)}
                </option>
              ))}
            </select>
          </label>
          <span className="ws-compare__arrow" aria-hidden="true">→</span>
          <label className="ws-compare__pick">
            <span className="ws-visually-hidden">Later version</span>
            <select value={after} onChange={(event) => setAfter(event.target.value)}>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {label(version)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {state.kind === "ready" ? (
          <p className="ws-compare__counts">{countSentence(state.comparison.summary)}</p>
        ) : null}
      </div>

      {state.kind === "loading" ? (
        <p className="ws-pane__note">Comparing…</p>
      ) : state.kind === "error" ? (
        <p className="ws-pane__note" role="note">
          {state.message}
        </p>
      ) : (
        <Result
          comparison={state.comparison}
          showUnchanged={showUnchanged}
          onToggleUnchanged={() => setShowUnchanged((v) => !v)}
        />
      )}
    </section>
  );
}

function Result({
  comparison,
  showUnchanged,
  onToggleUnchanged,
}: {
  comparison: Comparison;
  showUnchanged: boolean;
  onToggleUnchanged: () => void;
}) {
  const shown = comparison.clauses.filter(
    (clause) => showUnchanged || clause.status !== "UNCHANGED",
  );
  const { unnumbered } = comparison;

  return (
    <>
      {shown.length === 0 ? (
        <p className="ws-pane__note">
          No numbered clause differs between these two versions.
        </p>
      ) : (
        <ol className="ws-compare__list">
          {shown.map((clause) => (
            <li key={`${clause.status}-${clause.section_number}`} className="ws-compare__row">
              <p className="ws-compare__clause">
                <span className="ws-mono">{sectionRef(clause.section_number) ?? "—"}</span>
                {clause.section_title ? (
                  <span className="ws-compare__title">{clause.section_title}</span>
                ) : null}
                <span className="ws-compare__status">{STATUS_TEXT[clause.status]}</span>
              </p>
              {/* Current text first, superseded text beneath it. A reader holds
                  the new draft and asks what moved; the old wording is history,
                  not a peer, so it is quieter and rule-marked rather than given
                  an equal column. The quiet is about TIME, not acceptability —
                  33.16 forbids the second reading, and nothing here supplies it. */}
              {clause.after ? (
                <Side side={clause.after} />
              ) : (
                <p className="ws-compare__gone">
                  Not in version {comparison.after.version_number}.
                </p>
              )}
              {clause.before && clause.status !== "UNCHANGED" ? (
                <Side side={clause.before} was />
              ) : null}
              {clause.findings.length > 0 ? (
                <p className="ws-compare__findings">
                  <span className="ws-compare__findlabel">The analysis of this clause:</span>
                  {clause.findings.map((finding) => (
                    /* The reader's word in the reader's colour: this chip wore
                       `--ws-classify` while every other surface showing the
                       same word wore ok/warn/bad (2026-09-09). */
                    <span
                      key={finding.finding_id}
                      className={`ws-chip ws-chip--fill ws-chip--status-${userStatus(finding).toLowerCase()}`}
                    >
                      {USER_STATUS_LABELS[userStatus(finding)]}
                      {finding.requirement_code ? ` · ${requirementTitle({ code: finding.requirement_code })}` : ""}
                    </span>
                  ))}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}

      {/* How much of the document this actually aligned, stated rather than
          implied: clause numbering is the document's own (34.12), so text
          carrying none of it can only be counted honestly. */}
      <p className="ws-pane__note">
        Clauses are matched on the document&rsquo;s own numbering. Text with no clause
        number of its own is not paired up: {unnumbered.unchanged} passage
        {unnumbered.unchanged === 1 ? "" : "s"} appear in both versions,{" "}
        {unnumbered.added} only in the later one and {unnumbered.removed} only in the
        earlier. A comparison is not a legal decision — it reports what the text does,
        not what should be done about it.
      </p>
      {comparison.summary.UNCHANGED > 0 ? (
        <button type="button" className="ws-viewall" onClick={onToggleUnchanged}>
          {showUnchanged
            ? "Hide unchanged clauses"
            : `Show ${comparison.summary.UNCHANGED} unchanged clause${
                comparison.summary.UNCHANGED === 1 ? "" : "s"
              }`}
        </button>
      ) : null}
    </>
  );
}

function Side({ side, was = false }: { side: NonNullable<ClauseChange["before"]>; was?: boolean }) {
  return (
    <div className={was ? "ws-compare__side ws-compare__side--was" : "ws-compare__side"}>
      {was ? <span className="ws-compare__was">was</span> : null}
      {/* The house role for quoted contract text — the same blockquote the
          report and the findings pane use. Contract wording looks like contract
          wording everywhere in this product; rendering it as body copy here was
          the reason this panel read as bolted on. */}
      <blockquote className="ws-compare__excerpt ws-quote">
        {side.truncated_start ? <span className="ws-compare__cut">…</span> : null}
        {side.excerpt}
        {side.truncated_end ? <span className="ws-compare__cut">…</span> : null}
      </blockquote>
      {side.page_number !== null ? (
        <span className="ws-compare__page ws-mono">p. {side.page_number}</span>
      ) : null}
    </div>
  );
}

"use client";

/**
 * The Review report — P1 (PRODUCT_UX_ROADMAP §E screen 8), rendering exactly
 * what `GET /reviews/{id}/report` carries: counts, coverage, and an alignment
 * ratio that F-9 locks to "carries no legal meaning". Two things are absent
 * because the specification forbids them, and the page says so rather than
 * leaving a suspicious gap: no risk figure (36.10, F-8) and no overall verdict.
 *
 * Permission layering: the Review itself needs `review.view`; the report body
 * additionally needs `report.view`. A caller with the first but not the second
 * sees the Review's identity and a plain note — the report is neither faked
 * nor replaced with an error banner.
 *
 * Denial semantics (49.5): an out-of-scope Review reads identically to a
 * nonexistent one — "Not found.", never "no access".
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ReportBlock, Review, ReviewReport } from "@/lib/types";

import { STAGE_LABELS } from "@/lib/labels";

import { StatusIcon } from "./AnalysisPanel";
import { ExportControl } from "./ExportControl";
import { USER_STATUS_LABELS, USER_STATUS_TONE, type UserStatus } from "./findingLanguage";
import { IconArrowLeft } from "./icons";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; review: Review; report: ReviewReport | null; reportDenied: boolean;
      stage: string | null }
  | { kind: "error"; error: unknown };

export function ReviewReportPage({ reviewId }: { reviewId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const review = await api.review(reviewId);
      let report: ReviewReport | null = null;
      let reportDenied = false;
      try {
        report = await api.report(reviewId);
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 403) reportDenied = true;
        else throw cause;
      }
      // The document's name arrives with the Review (2026-09-04) — the extra
      // `GET /contracts/{id}` this used to make is ownership-scoped, so for a
      // Review reached through Legal scope it 404'd and the heading fell back
      // to the generic "Review report".
      // where the review stands, as every screen says it (AM-179)
      const stage = await api.reviewProgress(reviewId).then((p) => p.stage, () => null);
      setState({ kind: "ready", review, report, reportDenied, stage });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [reviewId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.REVIEW_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include Review access.</p>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="ws-state" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the report…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "30%", height: "1.2rem" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "55%" }} aria-hidden="true" />
      </div>
    );
  }

  if (state.kind === "error") {
    const notFound = state.error instanceof ApiError && state.error.isNotFound;
    return (
      <div className={`ws-state${notFound ? "" : " ws-state--error"}`} role={notFound ? "note" : "alert"}>
        <h2>{notFound ? "Not found." : "The report could not be loaded."}</h2>
        {notFound ? (
          <p>
            <Link href="/dashboard/reviews">Back to reviews</Link>
          </p>
        ) : (
          <p>{describeError(state.error)}</p>
        )}
      </div>
    );
  }

  const { review, report, reportDenied, stage } = state;

  return (
    <>
      <div className="ws-context">
        <Link className="ws-context__back" href="/dashboard/reviews" aria-label="Back to reviews">
          <IconArrowLeft size={18} />
        </Link>
        <h1>{review.document_name ?? "Review report"}</h1>
        <div className="ws-context__meta">
          {review.document_type ? (
            <span className="ws-chip ws-chip--type">{review.document_type}</span>
          ) : null}
          {stage ? <span className="ws-chip">{STAGE_LABELS[stage] ?? stage}</span> : null}
          <span className="ws-context__spacer" />
          {/* Offered only when the workspace will actually open for this
              caller — see the queue's own note. */}
          {review.document_accessible ? (
            <Link href={`/dashboard?id=${review.contract_id}`}>Open the workspace</Link>
          ) : null}
          <ExportControl reviewId={review.id} />
        </div>
      </div>

      <div className="ws-docs">
      {reportDenied ? (
        <div className="ws-state" role="note">
          <h2>Report restricted</h2>
          <p>Your account does not include report access.</p>
        </div>
      ) : null}

      {/* AB-103 (owner, 2026-10-22): the report a reader downloads, shown before it is
          downloaded — the server builds it once for both, so they cannot differ */}
      {report ? <ReportDocument reviewId={review.id} /> : null}
      </div>
    </>
  );
}

/** The four reader words back to their status, so a report cell wears the same chip
 *  and icon as the Findings screen — the server sends words, never codes. */
const STATUS_OF_WORD = Object.fromEntries(
  Object.entries(USER_STATUS_LABELS).map(([status, word]) => [word, status])) as
  Record<string, UserStatus>;

function StatusWord({ text }: { text: string }) {
  const status = STATUS_OF_WORD[text];
  if (!status) return <>{text}</>;
  return (
    <span className={`ws-finding__det ws-finding__det--${USER_STATUS_TONE[status]} ws-reportdoc__status`}>
      <StatusIcon status={status} size={12} />{text}
    </span>
  );
}

/** Plain blocks, as the download carries them. */
function Blocks({ blocks }: { blocks: ReportBlock[] }) {
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (key: string) => {
    if (bullets.length) {
      out.push(<ul key={key} className="ws-reportdoc__list">
        {bullets.map((b, i) => <li key={i}>{b}</li>)}
      </ul>);
      bullets = [];
    }
  };
  blocks.forEach((b, i) => {
    if (b.kind === "bullet") { bullets.push(b.text); return; }
    flush(`ul-${i}`);
    const key = `b-${i}`;
    if (b.kind === "h3") out.push(<h4 key={key} className="ws-reportdoc__h3">{b.text}</h4>);
    else if (b.kind === "kv" && b.label === "Recommendation") out.push(
      <p key={key} className="ws-reportdoc__lead">{capitalise(b.text)}</p>);
    else if (b.kind === "kv" && STATUS_OF_WORD[b.label]) out.push(     // the key
      <p key={key} className="ws-reportdoc__key"><StatusWord text={b.label} />{b.text}</p>);
    else if (b.kind === "kv") out.push(
      <p key={key} className="ws-reportdoc__kv"><strong>{b.label}:</strong>{" "}
        {b.label === "Status" ? <StatusWord text={b.text} /> : b.text}</p>);
    else if (b.kind === "quote") out.push(
      <figure key={key} className="ws-reportdoc__quote">
        {b.label ? <figcaption>{b.label}</figcaption> : null}
        <blockquote className="ws-quote">{b.text}</blockquote>
      </figure>);
    else if (b.kind === "note") out.push(<p key={key} className="ws-reportdoc__note">{b.text}</p>);
    else if (b.kind === "change" && b.rows[0]) {
      // one tracked change as the client's lawyer marked it: struck = removed, underlined
      // = added — the words carry it too, never colour alone
      const [clause, kind, removed, added, tag] = b.rows[0];
      out.push(
        <div key={key} className="ws-change">
          <span className="ws-change__where">{clause}</span>
          <span className="ws-change__kind">{kind}</span>
          <span className="ws-change__text">
            {removed ? <del>{removed}</del> : null}
            {removed && added ? " " : null}
            {added ? <ins>{added}</ins> : null}
          </span>
          {tag === "read" ? <span className="ws-change__read">Please read</span> : null}
        </div>);
    }
    else if (b.kind === "table" && b.rows.length) {
      const status = b.rows[0]!.indexOf("Status");
      out.push(
        <div key={key} className="ws-report__scroll">
          <table className="ws-report__table">
            <thead><tr>{b.rows[0]!.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
            <tbody>{b.rows.slice(1).map((row, r) => (
              <tr key={r}>{row.map((v, c) => (
                <td key={c}>{c === status ? <StatusWord text={v} /> : v}</td>))}</tr>))}</tbody>
          </table>
        </div>);
    }
    else if (b.kind !== "h1" && b.kind !== "h2") out.push(<p key={key}>{b.text}</p>);
  });
  flush("ul-end");
  return <>{out}</>;
}

/** The step most points carry; the report's key says it once (export_render `_KEY`). */
const DEFAULT_STEP = "Seek legal review";

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** One point, closed: its name, status, clause and the difference on one line; open,
 *  everything the report says about it — our standard, the step, the contract's words. */
function PointCard({ name, blocks, status, clause, line }: {
  name: string; blocks: ReportBlock[]; status?: string; clause?: string; line?: string;
}) {
  const own = blocks.find((b) => b.kind === "kv" && b.label === "Status");
  const gap = blocks.find((b) => b.kind === "kv" && b.label === "The difference");
  const step = blocks.find((b) => b.kind === "kv" && b.label === "Recommended");
  const theirs = blocks.find((b) => b.kind === "kv" && b.label === "Changed by the client");
  const special = step && step.text !== DEFAULT_STEP ? step : null;   // the key says the default
  const shown = status || own?.text;
  return (
    <details className="ws-reportdoc__point">
      <summary>
        <span className="ws-reportdoc__pointname">{name}</span>
        {clause && clause !== "—" ? <span className="ws-reportdoc__clause">{clause}</span> : null}
        {theirs ? <span className="ws-reportdoc__theirs">Client changed this</span> : null}
        {shown ? <StatusWord text={shown} /> : null}
        {line || gap ? <span className="ws-reportdoc__gap">{line || gap!.text}</span> : null}
        {special ? <span className="ws-reportdoc__step">{special.text}</span> : null}
      </summary>
      <Blocks blocks={blocks.filter((b) => b !== own && b !== special
                                         && (b !== gap || !(line || gap)))} />
    </details>
  );
}

/** The review report on screen (owner, 2026-10-27: "a lot of information that is not
 *  needed"). The same blocks as the download — the server builds them once, so screen
 *  and file cannot differ in substance — read the way a person reads: the cover as one
 *  line of facts, the overview open, each point's detail and every appendix one click
 *  away. Nothing is dropped; the record stays whole for whoever opens it. */
export function ReportDocumentView({ blocks }: { blocks: ReportBlock[] }) {
  const sections: { head: ReportBlock | null; body: ReportBlock[] }[] = [{ head: null, body: [] }];
  for (const b of blocks) {
    if (b.kind === "h2") sections.push({ head: b, body: [] });
    else sections.at(-1)!.body.push(b);
  }
  const [cover, ...rest] = sections;
  // each point's detail by its numbered name: a table of points opens into them, so a
  // point is listed once on screen, never as a table row and again as a card
  const detail = new Map<string, ReportBlock[]>();
  for (const { body } of rest) {
    let point: ReportBlock[] | null = null;
    for (const b of body) {
      if (b.kind === "h3") detail.set(b.text, point = []);
      else point?.push(b);
    }
  }
  const opened = new Set<string>();
  const pointsTable = (b: ReportBlock) => b.kind === "table" && b.rows.length > 1
    && b.rows.slice(1).every((row) => detail.has(row[0]!));
  return (
    <article className="ws-reportdoc" aria-label="Review report">
      <dl className="ws-reportdoc__cover">
        {cover!.body.filter((b) => b.kind === "kv").map((b, i) => (
          <div key={i}><dt>{b.label}</dt><dd>{b.text}</dd></div>))}
      </dl>
      {rest.map(({ head, body }, i) => {
        const title = head!.text;
        if (title.startsWith("Appendix")) {
          return (
            <details key={i} className="ws-reportdoc__more">
              <summary>{capitalise(title.replace(/^Appendix — /, ""))}</summary>
              <Blocks blocks={body} />
            </details>);
        }
        if (body.some((b) => b.kind === "h3")) {         // what no table opened, as cards
          const left = [...detail.keys()].filter((name) => !opened.has(name)
            && body.some((b) => b.kind === "h3" && b.text === name));
          if (left.length === 0) return null;
          return (
            <section key={i} className="ws-reportdoc__section">
              <h3 className="ws-report__h">{title}</h3>
              {left.map((name) => <PointCard key={name} name={name} blocks={detail.get(name)!} />)}
            </section>);
        }
        return (
          <section key={i} className="ws-reportdoc__section">
            <h3 className="ws-report__h">{title}</h3>
            <Blocks blocks={body.filter((b) => !pointsTable(b))} />
            {body.map((b, j) => {
              if (!pointsTable(b)) return null;
              const head = b.rows[0]!;
              return (
                <div key={j}>{b.rows.slice(1).map((row) => {
                  opened.add(row[0]!);
                  const cell = (h: string) => row[head.indexOf(h)] ?? "";
                  return <PointCard key={row[0]} name={row[0]!} blocks={detail.get(row[0]!)!}
                                    status={cell("Status") || cell("Change")}
                                    clause={cell("Clause")}
                                    line={cell("What the contract says") || cell("The contract says")} />;
                })}</div>);
            })}
          </section>);
      })}
    </article>
  );
}

function ReportDocument({ reviewId }: { reviewId: string }) {
  const [blocks, setBlocks] = useState<ReportBlock[] | null>(null);
  const [failed, setFailed] = useState<unknown>(null);
  useEffect(() => {
    let cancelled = false;
    api.reportDocument(reviewId)
      .then((value) => { if (!cancelled) setBlocks(value); })
      .catch((error: unknown) => { if (!cancelled) setFailed(error); });
    return () => { cancelled = true; };
  }, [reviewId]);
  if (failed) return <p className="ws-pane__note" role="alert">{describeError(failed)}</p>;
  if (!blocks) return <p className="ws-pane__note" role="status">Preparing the report…</p>;
  return <ReportDocumentView blocks={blocks} />;
}

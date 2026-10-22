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

import { reviewStatusLabel } from "@/lib/labels";

import { ExportControl } from "./ExportControl";
import { IconArrowLeft } from "./icons";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; review: Review; report: ReviewReport | null; reportDenied: boolean }
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
      setState({ kind: "ready", review, report, reportDenied });
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

  const { review, report, reportDenied } = state;

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
          <span className={`ws-chip${review.status === "LEGAL_REVIEW" ? " ws-chip--fill ws-chip--outcome-fill" : ""}`}
                title={review.status}>
            {reviewStatusLabel(review.status)}
          </span>
          <span className="ws-mono">{review.created_at ? review.created_at.slice(0, 10) : ""}</span>
          <span className="ws-mono" title="Configuration snapshot — what makes this Review reproducible (AUD-04)">
            snapshot {review.configuration_snapshot_id.slice(0, 8)}
          </span>
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

/** The review report, block by block — the download's own content (AB-103). */
export function ReportDocumentView({ blocks }: { blocks: ReportBlock[] }) {
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
    if (b.kind === "h1") out.push(<h2 key={key} className="ws-reportdoc__title">{b.text}</h2>);
    else if (b.kind === "h2") out.push(<h3 key={key} className="ws-report__h">{b.text}</h3>);
    else if (b.kind === "h3") out.push(<h4 key={key} className="ws-reportdoc__h3">{b.text}</h4>);
    else if (b.kind === "kv") out.push(<p key={key} className="ws-reportdoc__kv"><strong>{b.label}:</strong> {b.text}</p>);
    else if (b.kind === "quote") out.push(
      <figure key={key} className="ws-reportdoc__quote">
        {b.label ? <figcaption>{b.label}</figcaption> : null}
        <blockquote className="ws-quote">{b.text}</blockquote>
      </figure>);
    else if (b.kind === "note") out.push(<p key={key} className="ws-reportdoc__note">{b.text}</p>);
    else if (b.kind === "table" && b.rows.length) out.push(
      <div key={key} className="ws-report__scroll">
        <table className="ws-report__table">
          <thead><tr>{b.rows[0]!.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
          <tbody>{b.rows.slice(1).map((row, r) => (
            <tr key={r}>{row.map((v, c) => <td key={c}>{v}</td>)}</tr>))}</tbody>
        </table>
      </div>);
    else out.push(<p key={key}>{b.text}</p>);
  });
  flush("ul-end");
  return <article className="ws-reportdoc" aria-label="Review report">{out}</article>;
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

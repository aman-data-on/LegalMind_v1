"use client";

/**
 * The document pane — the workspace's neutral ground, the target every verdict
 * and citation points at.
 *
 * Renders the document as the pipeline read it: evidence rows in reading order
 * (`GET /document-versions/{id}/evidence`, paginated and loaded progressively),
 * grouped under page markers, with the document's own clause outline beside it.
 * Verbatim text is set in the serif quote voice — the one typographic signal that
 * "this exact text came from the document" (master prompt §4.3). OCR-derived rows
 * are labelled (34.8).
 *
 * Highlight contract: when `useHighlight().target` names a row that is on screen,
 * the row lights, scrolls into view and receives focus. If the target is on a page
 * not yet loaded, loading continues until it appears — a shared link must land.
 *
 * States: loading (skeleton + announced), processing (the version is not COMPLETE
 * yet — said as a lifecycle fact, no invented progress), empty (COMPLETE with no
 * text — an honest statement, not an error), error (banner with request id).
 */

import { useEffect, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import type { DocumentVersion, EvidenceRow } from "@/lib/types";

import { useHighlight } from "./highlight";
import {
  READINESS_TEXT,
  groupByPage,
  locationLabel,
  outlineOf,
  readiness,
} from "./model";

const PAGE_SIZE = 100;

export function DocumentPane({ version }: { version: DocumentVersion }) {
  const [rows, setRows] = useState<EvidenceRow[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const { target, point, announcement } = useHighlight();
  const textRef = useRef<HTMLDivElement | null>(null);

  // Progressive load: page after page until the total is reached. Documents are
  // a few hundred rows at most; the user sees the first page immediately and the
  // rest arrive behind it, announced once.
  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setTotal(null);
    setError(null);
    (async () => {
      const collected: EvidenceRow[] = [];
      let page = 1;
      try {
        for (;;) {
          const result = await api.documentEvidence(version.id, page, PAGE_SIZE);
          if (cancelled) return;
          collected.push(...result.items);
          setRows([...collected]);
          setTotal(result.pagination.total);
          if (collected.length >= result.pagination.total || result.items.length === 0) break;
          page += 1;
        }
      } catch (cause) {
        if (!cancelled) setError(cause);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [version.id]);

  // Answer a highlight: scroll, light, focus.
  useEffect(() => {
    if (!target || !rows) return;
    const node = textRef.current?.querySelector<HTMLElement>(`[data-evidence-id="${target}"]`);
    if (!node) return;
    node.scrollIntoView({ block: "center" });
    node.focus({ preventScroll: true });
  }, [target, rows]);

  const ready = readiness(version.assist_index);

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Document</h2>
        <span className="ws-pane__note ws-mono">
          v{version.version_number} · {version.original_filename}
        </span>
        <span className="ws-readiness" data-readiness={ready}>
          {READINESS_TEXT[ready]}
        </span>
      </div>
      <p className="ws-visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>

      {error ? (
        <div className="ws-state ws-state--error" role="alert">
          <h3>The document text could not be loaded.</h3>
          <p>{describeError(error)}</p>
          {error instanceof ApiError ? (
            <p className="ws-mono ws-readiness">reference {error.requestId}</p>
          ) : null}
        </div>
      ) : rows === null ? (
        <div className="ws-state" aria-busy="true">
          <p className="ws-visually-hidden" role="status" aria-live="polite">
            Loading the document…
          </p>
          <span className="ws-skel ws-skel--line" style={{ width: "40%" }} aria-hidden="true" />
          <span className="ws-skel ws-skel--line" style={{ width: "92%" }} aria-hidden="true" />
          <span className="ws-skel ws-skel--line" style={{ width: "85%" }} aria-hidden="true" />
          <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
        </div>
      ) : rows.length === 0 ? (
        version.processing_status !== "COMPLETED" ? (
          <div className="ws-state">
            <h3>This document is still being processed.</h3>
            <p>
              Processing status is <span className="ws-mono">{version.processing_status}</span>.
              The text appears here once extraction completes; reload to check.
            </p>
          </div>
        ) : (
          <div className="ws-state">
            <h3>No text was extracted from this document.</h3>
            <p>
              Processing completed but produced no readable text — usually a scanned file
              without recoverable characters. Nothing can be cited from it.
            </p>
          </div>
        )
      ) : (
        <div className="ws-doc">
          <nav className="ws-outline" aria-label="Document outline">
            <p className="ws-outline__title">Clauses</p>
            {outlineOf(rows).map((row) => (
              <button
                key={row.id}
                type="button"
                aria-current={target === row.id ? "true" : undefined}
                onClick={() => point(row.id, row.section_number ? `clause ${row.section_number}` : "the selected")}
              >
                {row.section_number ? <span className="ws-mono">§{row.section_number}</span> : null}
                {row.section_title ?? (row.section_number ? "" : "Untitled clause")}
              </button>
            ))}
            {outlineOf(rows).length === 0 ? (
              <p className="ws-pane__note" style={{ padding: "0 12px" }}>
                No clause numbering was detected.
              </p>
            ) : null}
          </nav>
          <div className="ws-text" ref={textRef}>
            {groupByPage(rows).map((group, index) => (
              <div key={`${group.page ?? "np"}-${index}`} className="ws-page">
                <p className="ws-page__marker">
                  {group.page != null ? `Page ${group.page}` : "Unnumbered pages"}
                </p>
                {group.rows.map((row) => (
                  <article
                    key={row.id}
                    className={`ws-row${target === row.id ? " ws-row--lit" : ""}`}
                    data-evidence-id={row.id}
                    tabIndex={-1}
                    aria-label={locationLabel(row)}
                  >
                    {row.section_number || row.section_title || row.source_type === "OCR" ? (
                      /* Only when there is something to say: a clause reference or the
                         OCR provenance mark. The page is already the group marker. */
                      <p className="ws-row__loc">
                        {row.section_number || row.section_title ? (
                          <span>
                            {[row.section_number ? `§${row.section_number}` : null, row.section_title]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        ) : null}
                        {row.source_type === "OCR" ? (
                          <span className="ws-row__ocr" title="Text recovered by OCR">OCR</span>
                        ) : null}
                      </p>
                    ) : null}
                    <p className="ws-row__text">{row.content}</p>
                  </article>
                ))}
              </div>
            ))}
            {total !== null && rows.length < total ? (
              <p className="ws-pane__note" role="status" aria-live="polite">
                Loading the rest of the document… {rows.length} of {total} passages
              </p>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}

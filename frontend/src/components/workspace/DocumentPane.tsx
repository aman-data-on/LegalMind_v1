"use client";

/**
 * The document area — two cards, per the 2026-09-01 reference-matched restyle:
 *
 *   CLAUSES   the document's own outline as a card: search, per-clause status
 *             markers (the owner-approved DD-9 traffic light — green matches,
 *             amber needs review, red missing), a legend, and a pages footer.
 *   DOCUMENT  the text as the pipeline read it, under a toolbar: find-in-
 *             document, page navigation, zoom, fullscreen. Verbatim text stays
 *             in the serif quote voice; OCR-derived rows are labelled (34.8).
 *
 * Highlight contract unchanged: when `useHighlight().target` names a row, the
 * row lights, scrolls into view and receives focus. Deep links (`?evidence=`)
 * keep working. States: loading (skeleton + announced), processing, empty,
 * error — all honest, none invented.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import type { DocumentVersion, EvidenceRow } from "@/lib/types";

import { useFindingsStateOptional } from "./findingsState";
import { useHighlight } from "./highlight";
import {
  IconAlertCircle,
  IconCheckCircle,
  IconChevronDown,
  IconChevronUp,
  IconMaximize,
  IconSearch,
  IconXCircle,
} from "./icons";
import {
  READINESS_TEXT,
  clauseStatusByEvidenceId,
  groupByPage,
  locationLabel,
  outlineOf,
  outlineStatus,
  readiness,
  type ClauseStatus,
  type StatusBucket,
} from "./model";

const PAGE_SIZE = 100;
const ZOOM_STEPS = [85, 100, 115, 130, 150];

const EMPTY_STATUS = new Map<string, ClauseStatus>();

const BUCKET_TITLE: Record<StatusBucket, string> = {
  match: "Matches the company standard",
  review: "A finding here needs review",
  missing: "Expected content is missing",
};

function StatusIcon({ bucket }: { bucket: StatusBucket }) {
  return (
    <span className={`ws-status ws-status--${bucket}`} title={BUCKET_TITLE[bucket]}
          aria-label={BUCKET_TITLE[bucket]}>
      {bucket === "match" ? <IconCheckCircle /> : bucket === "review" ? <IconAlertCircle /> : <IconXCircle />}
    </span>
  );
}

export function DocumentPane({ version }: { version: DocumentVersion }) {
  const [rows, setRows] = useState<EvidenceRow[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const { target, point, announcement } = useHighlight();
  const textRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  // Toolbar state — presentation conveniences over the loaded rows.
  const [clauseQuery, setClauseQuery] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findIndex, setFindIndex] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [currentPage, setCurrentPage] = useState<number | null>(null);

  // Progressive load: page after page until the total is reached.
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

  // Per-clause status markers from the shared findings state, rolled up to the
  // owning outline row.
  const findingsState = useFindingsStateOptional();
  const clauseStatus =
    findingsState?.state.kind === "ready" && rows
      ? outlineStatus(rows, clauseStatusByEvidenceId(findingsState.state.findings))
      : EMPTY_STATUS;

  const pages = useMemo(() => {
    const seen: number[] = [];
    for (const row of rows ?? []) {
      if (row.page_number != null && !seen.includes(row.page_number)) seen.push(row.page_number);
    }
    return seen;
  }, [rows]);

  // Track which page marker is on screen so the toolbar's "n of N" stays true.
  useEffect(() => {
    const root = textRef.current;
    if (!root || pages.length === 0) return;
    const markers = root.querySelectorAll<HTMLElement>("[data-page-marker]");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const n = Number(entry.target.getAttribute("data-page-marker"));
            if (!Number.isNaN(n)) setCurrentPage(n);
          }
        }
      },
      { root, threshold: 0 },
    );
    markers.forEach((m) => observer.observe(m));
    return () => observer.disconnect();
  }, [pages, rows]);

  function jumpToPage(page: number) {
    const node = textRef.current?.querySelector<HTMLElement>(`[data-page-marker="${page}"]`);
    if (!node) return;
    node.scrollIntoView({ block: "start" });
    setCurrentPage(page);
  }

  function stepPage(direction: 1 | -1) {
    if (pages.length === 0) return;
    const at = currentPage ?? pages[0]!;
    const index = Math.max(0, pages.indexOf(at));
    const next = pages[Math.min(pages.length - 1, Math.max(0, index + direction))];
    if (next != null) jumpToPage(next);
  }

  // Find in document: cycle rows whose text contains the query; each hit is the
  // same pointing gesture every citation uses.
  const findHits = useMemo(() => {
    const query = findQuery.trim().toLowerCase();
    if (!query || !rows) return [];
    return rows.filter((row) => row.content.toLowerCase().includes(query)).map((row) => row.id);
  }, [findQuery, rows]);

  function findNext() {
    if (findHits.length === 0) return;
    const next = findIndex % findHits.length;
    point(findHits[next]!, "the matching");
    setFindIndex(next + 1);
  }

  function toggleFullscreen() {
    const node = cardRef.current;
    if (!node) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void node.requestFullscreen?.();
  }

  const ready = readiness(version.assist_index);
  const outline = rows ? outlineOf(rows) : [];
  const shownOutline = clauseQuery.trim()
    ? outline.filter((row) =>
        `${row.section_number ?? ""} ${row.section_title ?? ""}`
          .toLowerCase()
          .includes(clauseQuery.trim().toLowerCase()))
    : outline;

  if (error) {
    return (
      <div className="ws-card ws-card--pad">
        <div className="ws-state ws-state--error" role="alert">
          <h3>The document text could not be loaded.</h3>
          <p>{describeError(error)}</p>
          {error instanceof ApiError ? (
            <p className="ws-mono ws-readiness">reference {error.requestId}</p>
          ) : null}
        </div>
      </div>
    );
  }

  if (rows === null) {
    return (
      <div className="ws-card ws-card--pad" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the document…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "40%" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "92%" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "85%" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="ws-card ws-card--pad">
        {version.processing_status !== "COMPLETED" ? (
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
        )}
      </div>
    );
  }

  return (
    <>
      <p className="ws-visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>
      <div className="ws-doc">
        {/* ------------------------------------------------ clauses column */}
        <div className="ws-doc__clauses">
          <nav className="ws-card ws-outline" aria-label="Document outline">
            <p className="ws-outline__title">Clauses</p>
            <label className="ws-outline__search">
              <IconSearch size={14} />
              <span className="ws-visually-hidden">Search clauses</span>
              <input
                value={clauseQuery}
                onChange={(event) => setClauseQuery(event.target.value)}
                placeholder="Search clauses"
              />
            </label>
            <div className="ws-outline__list">
              {shownOutline.map((row) => {
                const status = clauseStatus.get(row.id);
                return (
                  <button
                    key={row.id}
                    type="button"
                    aria-current={target === row.id ? "true" : undefined}
                    onClick={() => point(row.id, row.section_number ? `clause ${row.section_number}` : "the selected")}
                  >
                    <span className="ws-outline__label">
                      {row.section_number ? <span className="ws-mono">§{row.section_number}</span> : null}
                      {row.section_title ?? (row.section_number ? "" : "Untitled clause")}
                    </span>
                    {status ? <StatusIcon bucket={status.bucket} /> : null}
                  </button>
                );
              })}
              {outline.length === 0 ? (
                <p className="ws-pane__note" style={{ padding: "0 12px" }}>
                  No clause numbering was detected.
                </p>
              ) : shownOutline.length === 0 ? (
                <p className="ws-pane__note" style={{ padding: "0 12px" }} role="status">
                  No clause matches that search.
                </p>
              ) : null}
            </div>
            {pages.length > 0 ? (
              <p className="ws-outline__pages">
                Pages: 1–{pages[pages.length - 1]} of {pages[pages.length - 1]}
              </p>
            ) : null}
          </nav>
          <div className="ws-card ws-legend" role="note" aria-label="Status legend">
            <p><StatusIcon bucket="match" /> Match (aligned)</p>
            <p><StatusIcon bucket="review" /> Needs review</p>
            <p><StatusIcon bucket="missing" /> Missing (not present)</p>
          </div>
        </div>

        {/* ------------------------------------------------ document card */}
        <div className="ws-card ws-doccard" ref={cardRef}>
          <div className="ws-doccard__bar" role="toolbar" aria-label="Document controls">
            <button
              type="button"
              className="ws-toolbtn"
              aria-expanded={findOpen}
              aria-label="Find in document"
              onClick={() => setFindOpen((open) => !open)}
            >
              <IconSearch />
            </button>
            {findOpen ? (
              <form
                className="ws-doccard__find"
                onSubmit={(event) => {
                  event.preventDefault();
                  findNext();
                }}
              >
                <span className="ws-visually-hidden">Find text in the document</span>
                <input
                  autoFocus
                  value={findQuery}
                  onChange={(event) => {
                    setFindQuery(event.target.value);
                    setFindIndex(0);
                  }}
                  placeholder="Find in document…"
                />
                <span className="ws-pane__note ws-mono">
                  {findQuery.trim() ? `${findHits.length} match${findHits.length === 1 ? "" : "es"}` : ""}
                </span>
              </form>
            ) : null}
            <span className="ws-doccard__gap" />
            <button type="button" className="ws-toolbtn" aria-label="Previous page" onClick={() => stepPage(-1)}>
              <IconChevronUp />
            </button>
            <button type="button" className="ws-toolbtn" aria-label="Next page" onClick={() => stepPage(1)}>
              <IconChevronDown />
            </button>
            <label className="ws-doccard__page">
              <span className="ws-visually-hidden">Page</span>
              <input
                inputMode="numeric"
                value={currentPage ?? pages[0] ?? ""}
                onChange={(event) => {
                  const n = Number(event.target.value);
                  if (pages.includes(n)) jumpToPage(n);
                  else setCurrentPage(Number.isNaN(n) ? null : n);
                }}
              />
              <span>of {pages.length > 0 ? pages[pages.length - 1] : "—"}</span>
            </label>
            <span className="ws-doccard__gap" />
            <button
              type="button"
              className="ws-toolbtn"
              aria-label="Zoom out"
              disabled={zoom === ZOOM_STEPS[0]}
              onClick={() => setZoom(ZOOM_STEPS[Math.max(0, ZOOM_STEPS.indexOf(zoom) - 1)]!)}
            >
              −
            </button>
            <span className="ws-mono ws-doccard__zoom">{zoom}%</span>
            <button
              type="button"
              className="ws-toolbtn"
              aria-label="Zoom in"
              disabled={zoom === ZOOM_STEPS[ZOOM_STEPS.length - 1]}
              onClick={() => setZoom(ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, ZOOM_STEPS.indexOf(zoom) + 1)]!)}
            >
              +
            </button>
            <span className="ws-doccard__gap" />
            <span className="ws-readiness" data-readiness={ready}>
              {READINESS_TEXT[ready]}
            </span>
            <button type="button" className="ws-toolbtn" aria-label="Fullscreen" onClick={toggleFullscreen}>
              <IconMaximize />
            </button>
          </div>
          <div className="ws-text" ref={textRef} style={{ fontSize: `${zoom}%` }}>
            {groupByPage(rows).map((group, index) => (
              <div key={`${group.page ?? "np"}-${index}`} className="ws-page">
                <p
                  className="ws-page__marker"
                  data-page-marker={group.page ?? undefined}
                >
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
          <p className="ws-doccard__meta ws-mono">
            v{version.version_number} · {version.original_filename}
          </p>
        </div>
      </div>
    </>
  );
}

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

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";
import { USER_STATUS_LABELS, userStatus } from "./findingLanguage";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, EvidenceRow } from "@/lib/types";

import { segmentContent, selectionInRow, useAnnotations, type Annotation } from "./annotations";
import { useFindingsStateOptional } from "./findingsState";
import { useHighlight } from "./highlight";
import { useSideTabs } from "./WorkspaceLayout";
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
  documentTextState,
  groupByPage,
  locationLabel,
  findingsByEvidenceId,
  outlineOf,
  partLabel,
  requirementHeading,
  sequenceBreaks,
  outlineStatus,
  readiness,
  rowPresentation,
  type ClauseStatus,
  type StatusBucket,
} from "./model";

const PAGE_SIZE = 100;
const ZOOM_STEPS = [85, 100, 115, 130, 150];

const EMPTY_FINDINGS = new Map<string, never[]>();
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
  // Phase 5 (2026-09-06): a re-read in place is offered only while no Review
  // exists — the server refuses otherwise, and says why; `reloadNonce` re-reads
  // the rows once a new reading is the document.
  const [reloadNonce, setReloadNonce] = useState(0);
  const [rereading, setRereading] = useState(false);
  const [rereadNote, setRereadNote] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const { target, point, announcement } = useHighlight();
  const { can } = useSession();
  const textRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  /**
   * The Original view (DD-16, 2026-09-03): the preserved original bytes (34.5),
   * rendered by the browser's own PDF renderer. A legal-document viewer must be
   * able to show the document as it actually looks — logo, layout, typography —
   * and no text-derived representation does that. The extracted text stays one
   * click away, because every pointing gesture (citations, clause outline,
   * find, annotations) addresses Evidence rows, not pixels.
   *
   * Gated on `document.download` because rendering the bytes IS handing the
   * bytes to the client — pretending otherwise would make `document.view` a
   * download permission by the back door. PDFs only: browsers render PDF
   * natively; a DOCX has no in-browser renderer, and faking one is out of scope.
   */
  const canOriginal = version.mime_type === "application/pdf" && can(P.DOCUMENT_DOWNLOAD);
  const [view, setView] = useState<"original" | "text">(canOriginal ? "original" : "text");
  useEffect(() => {
    // A different version is a different document — re-derive the default.
    setView(canOriginal ? "original" : "text");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version.id]);

  // Toolbar state — presentation conveniences over the loaded rows.
  const [clauseQuery, setClauseQuery] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findIndex, setFindIndex] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [currentPage, setCurrentPage] = useState<number | null>(null);

  // Reader annotations (DD-14): this-device marks over the unmodified text.
  const { annotations, add, remove, setNote } = useAnnotations(version.id);
  const annotationsByRow = useMemo(() => {
    const map = new Map<string, Annotation[]>();
    for (const a of annotations) {
      const list = map.get(a.rowId);
      if (list) list.push(a);
      else map.set(a.rowId, [a]);
    }
    return map;
  }, [annotations]);
  /** A live selection eligible to become a mark, with a place to put the button. */
  const [pendingMark, setPendingMark] = useState<{
    rowId: string; start: number; end: number; x: number; y: number;
  } | null>(null);
  /** The open annotation editor (click a mark), positioned near it. */
  const [openAnnotation, setOpenAnnotation] = useState<{ id: string; x: number; y: number } | null>(null);

  /** Where a selection/mark sits relative to the document card, so the small
   *  floating controls anchor next to it. */
  function cardPoint(rect: DOMRect): { x: number; y: number } {
    const host = cardRef.current?.getBoundingClientRect();
    if (!host) return { x: 0, y: 0 };
    return {
      x: Math.min(Math.max(rect.left - host.left + rect.width / 2, 70), host.width - 70),
      y: rect.top - host.top,
    };
  }

  function onTextSelect() {
    // Wait for the browser to settle the selection this event concluded.
    window.setTimeout(() => {
      const selection = window.getSelection();
      const inRow = selectionInRow(selection);
      if (!inRow) {
        setPendingMark(null);
        return;
      }
      const rect = selection!.getRangeAt(0).getBoundingClientRect();
      setPendingMark({ ...inRow, ...cardPoint(rect) });
    }, 0);
  }

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
  }, [version.id, reloadNonce]);

  /*
   * Answer a highlight — WITHOUT ejecting the reader from the document they
   * are reading (2026-09-05).
   *
   * This effect used to be `if (target) setView("text")`: every citation click
   * threw a reviewer out of the ORIGINAL — the signed PDF, with its layout,
   * tables and signatures — into the extracted-text rendering, with no way back
   * to where they were. The authoritative-looking view and the citable view are
   * different views, and only one of them has anchors.
   *
   * So the transition is now the smallest one that reaches the evidence:
   *
   *   already in Text            nothing to switch; the effect below scrolls
   *   Original + the row has a   stay in the Original and turn the PDF to that
   *     page number             page — the reader keeps the document they trust
   *   Original + no page number  Text is the only place the row exists, so
   *                             switch, and offer the way back
   *
   * The pointing MECHANISM is unchanged: `point(evidenceId)` still addresses an
   * Evidence row and `target` still names it. Only the response differs.
   */
  const [originalPage, setOriginalPage] = useState<number | null>(null);
  const [returnToOriginal, setReturnToOriginal] = useState(false);
  useEffect(() => {
    if (!target || !rows) return;
    if (view !== "original") return;
    const cited = rows.find((row) => row.id === target);
    if (cited?.page_number != null) {
      setOriginalPage(cited.page_number);
      return;
    }
    // No page to turn to — the row exists only in the text view.
    setReturnToOriginal(true);
    setView("text");
  }, [target, rows, view]);

  // A view the READER chose is not a transition to return from.
  function chooseView(next: "original" | "text") {
    setReturnToOriginal(false);
    setView(next);
  }
  useEffect(() => {
    if (!target || !rows || view !== "text") return;
    const node = textRef.current?.querySelector<HTMLElement>(`[data-evidence-id="${target}"]`);
    if (!node) return;
    node.scrollIntoView({ block: "center" });
    node.focus({ preventScroll: true });
  }, [target, rows, view]);

  // Per-clause status markers from the shared findings state, rolled up to the
  // owning outline row.
  const findingsState = useFindingsStateOptional();
  const clauseStatus =
    findingsState?.state.kind === "ready" && rows
      ? outlineStatus(rows, clauseStatusByEvidenceId(findingsState.state.findings))
      : EMPTY_STATUS;
  /* The reverse of the citation link (2026-09-05). The pane could already take
     a reader from a Finding to its evidence; from a clause there was no way to
     ask "did the analysis say anything about this?", so the review loop only
     ran one way. Indexed from the findings ALREADY loaded for the status
     markers above — no second request, no copy of the data, and nothing a
     reader could not already see in the Findings tab. */
  const findingsByEvidence =
    findingsState?.state.kind === "ready"
      ? findingsByEvidenceId(findingsState.state.findings)
      : EMPTY_FINDINGS;
  const sideTabs = useSideTabs();
  const canReread = can(P.DOCUMENT_UPLOAD) && findingsState?.state.kind === "no-review";

  async function reread() {
    setRereading(true);
    setRereadNote(null);
    try {
      const result = await api.reprocessVersion(version.id);
      if (result.document_version.processing_status === "PROCESSING") {
        setRereadNote("The text is being re-read in the background — reload the page in a moment.");
      } else if (result.processing_run.status === "FAILED") {
        setRereadNote("The current parser could not read this file either; the earlier reading stands.");
      } else {
        setReloadNonce((n) => n + 1);
        setRereadNote(`Re-read: ${result.evidence_count} passages.`);
      }
    } catch (cause) {
      setRereadNote(describeError(cause));
    } finally {
      setRereading(false);
    }
  }

  const pages = useMemo(() => {
    const seen: number[] = [];
    for (const row of rows ?? []) {
      if (row.page_number != null && !seen.includes(row.page_number)) seen.push(row.page_number);
    }
    return seen;
  }, [rows]);
  const pageGroups = useMemo(() => groupByPage(rows ?? []), [rows]);

  // Structural presentation per row (title / heading / item / paragraph) —
  // recognised from the text itself, never invented; see rowPresentation.
  const rowKinds = useMemo(() => {
    const map = new Map<string, string>();
    (rows ?? []).forEach((row, index) => map.set(row.id, rowPresentation(row, index)));
    return map;
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
  const breaks = sequenceBreaks(outline);
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

  /* `documentTextState` owns this branch — see its note in model.ts for
     why "FAILED" must not read as "still processing". Both statuses are
     surfaced because 34.15 keeps them as separate axes and a reviewer chasing
     this needs the real pair. When the Original view is available the state
     renders INSIDE the text view rather than replacing the whole pane — the
     original document is viewable the moment the upload stores it (34.5), and
     hiding it behind "still processing" would waste exactly the seconds the
     deferred-OCR path exists to give back. */
  const emptyTextState =
    rows.length === 0 ? (
      <div className="ws-card--pad">
        {documentTextState(version) === "unreadable" ? (
          <div className="ws-state">
            <h3>No readable text could be extracted from this document.</h3>
            <p>
              Either the file is a scan with no recoverable characters, or its embedded
              fonts do not map to readable text. LegalMind will not show unreadable text
              as if it were the contract, so nothing can be cited from this version and
              no finding is drawn from it.
            </p>
            <p className="ws-pane__note">
              The document may well be readable in a PDF viewer — that reads the printed
              shapes, which this does not. Re-saving or re-exporting it from the original
              source usually produces a file that extracts cleanly.
            </p>
            <p className="ws-pane__note ws-mono">
              processing {version.processing_status} · extraction{" "}
              {version.extraction_status ?? "not recorded"}
            </p>
          </div>
        ) : documentTextState(version) === "processing" ? (
          <div className="ws-state">
            <h3>Text is still being recovered from this document.</h3>
            <p>
              Processing status is <span className="ws-mono">{version.processing_status}</span>.
              {canOriginal
                ? " The original document is already viewable in the Original tab; the extracted text, clause outline and analysis appear here when recovery completes."
                : " The text appears here once extraction completes."}
            </p>
          </div>
        ) : (
          <div className="ws-state">
            <h3>No readable text could be extracted from this document.</h3>
            {/* Two real causes, and the copy no longer asserts the first one.
                Until 2026-09-03 this said "usually a scanned file", which was
                wrong for the case that prompted the fix: a PDF whose embedded
                fonts carry an incorrect character mapping extracts plenty of
                characters that are simply the wrong ones. That used to be shown
                as if it were the contract; it is now refused, which is what
                puts a reader here. */}
            <p>
              Either the file is a scan with no recoverable characters, or its embedded
              fonts do not map to readable text. LegalMind will not show unreadable text
              as if it were the contract, so nothing can be cited from this version and
              no finding is drawn from it.
            </p>
            <p className="ws-pane__note">
              The document may well be readable in a PDF viewer — that reads the printed
              shapes, which this does not. Re-saving or re-exporting it from the original
              source usually produces a file that extracts cleanly.
            </p>
          </div>
        )}
      </div>
    ) : null;

  if (rows.length === 0 && !canOriginal) {
    return <div className="ws-card">{emptyTextState}</div>;
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
            {/* "Contents", not "Clauses" (2026-09-05). This is the document's
                own outline — its headings — and a clause is the unit a finding
                attaches to, not a navigation target. The two were the same list
                until the parser could tell a heading from body text. */}
            <p className="ws-outline__title">Contents</p>
            <label className="ws-outline__search">
              <IconSearch size={14} />
              <span className="ws-visually-hidden">Search contents</span>
              <input
                value={clauseQuery}
                onChange={(event) => setClauseQuery(event.target.value)}
                placeholder="Search contents"
              />
            </label>
            <div className="ws-outline__list">
              {shownOutline.map((row) => {
                const status = clauseStatus.get(row.id);
                // §4.3.1 indents under §4.3 under §4 — depth is the section
                // number's own dot count (capped; deeper than 3 reads as 3).
                const depth = Math.min(3, row.section_number?.match(/\./g)?.length ?? 0);
                return (
                  <Fragment key={row.id}>
                  {/* A new part of the document. When the file DECLARES it —
                      "Annexure-1", "Schedule 2" — the divider says the kind
                      the document's own title uses (44.4). When it only
                      restarts its numbering, the divider says just that:
                      naming what the part IS would be inventing structure. */}
                  {partLabel(row) ? (
                    <p className="ws-outline__break">{partLabel(row)}</p>
                  ) : breaks.has(row.id) ? (
                    <p className="ws-outline__break">Numbering restarts</p>
                  ) : null}
                  <button
                    type="button"
                    data-depth={depth > 0 ? depth : undefined}
                    aria-current={target === row.id ? "true" : undefined}
                    onClick={() => point(row.id, row.section_number ? `clause ${row.section_number}` : "the selected")}
                  >
                    <span className="ws-outline__label">
                      {sectionRef(row.section_number) ? <span className="ws-mono">{sectionRef(row.section_number)}</span> : null}
                      {row.section_title ?? (row.section_number ? "" : "Untitled clause")}
                    </span>
                    {status ? <StatusIcon bucket={status.bucket} /> : null}
                  </button>
                  </Fragment>
                );
              })}
              {outline.length === 0 ? (
                <p className="ws-pane__note" style={{ padding: "0 12px" }}>
                  {rows.length === 0 && documentTextState(version) === "processing"
                    ? "The outline appears when text extraction completes."
                    : "No headings or clause numbering were detected."}
                </p>
              ) : shownOutline.length === 0 ? (
                <p className="ws-pane__note" style={{ padding: "0 12px" }} role="status">
                  Nothing in the contents matches that search.
                </p>
              ) : null}
            </div>
            {pages.length > 0 ? (
              <p className="ws-outline__pages">
                {/* Jump straight to a page — the same jump the toolbar's page
                    field performs, offered where the outline already lives. */}
                <label className="ws-outline__pagenav">
                  <span>Page</span>
                  <select
                    value={currentPage ?? pages[0]}
                    onChange={(event) => jumpToPage(Number(event.target.value))}
                  >
                    {pages.map((page) => (
                      <option key={page} value={page}>{page}</option>
                    ))}
                  </select>
                  <span>of {pages[pages.length - 1]}</span>
                </label>
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
            {canOriginal ? (
              <div className="ws-viewtoggle" role="group" aria-label="Document view">
                <button
                  type="button"
                  className="ws-viewtoggle__btn"
                  aria-pressed={view === "original"}
                  onClick={() => chooseView("original")}
                >
                  Original
                </button>
                <button
                  type="button"
                  className="ws-viewtoggle__btn"
                  aria-pressed={view === "text"}
                  onClick={() => chooseView("text")}
                >
                  Text
                </button>
              </div>
            ) : null}
            {/* Where the citation landed, and the way onward or back. Only ever
                one of these shows, and only after a citation actually moved the
                reader — a reader who switched views themselves sees neither. */}
            {canReread ? (
              /* Phase 5, Option C: shown only while nothing relies on this
                 reading; the server is the judge and names any reason. */
              <button type="button" className="ws-escalate__link" disabled={rereading}
                      onClick={() => void reread()}>
                {rereading ? "Re-reading…" : "Re-read with the current parser"}
              </button>
            ) : null}
            {rereadNote ? <p className="ws-doccard__cited" role="status">{rereadNote}</p> : null}
            {view === "original" && originalPage !== null ? (
              <p className="ws-doccard__cited">
                <span>Page {originalPage} in the original</span>
                <button type="button" className="ws-escalate__link"
                        onClick={() => chooseView("text")}>
                  Show the exact passage
                </button>
              </p>
            ) : null}
            {view === "text" && returnToOriginal ? (
              <p className="ws-doccard__cited">
                <span>This passage has no page in the original</span>
                <button type="button" className="ws-escalate__link"
                        onClick={() => chooseView("original")}>
                  Back to the original
                </button>
              </p>
            ) : null}
            {view === "text" ? (
            <button
              type="button"
              className="ws-toolbtn"
              aria-expanded={findOpen}
              aria-label="Find in document"
              onClick={() => setFindOpen((open) => !open)}
            >
              <IconSearch />
            </button>
            ) : null}
            {view === "text" && findOpen ? (
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
            {view === "text" ? (
              pages.length > 0 ? (
                <>
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
                    <span>of {pages[pages.length - 1]}</span>
                  </label>
                </>
              ) : rows.length > 0 ? (
                // A DOCX carries no fixed page model (only rendering/print time
                // creates pages), so "page N of M" has nothing real to say here —
                // an empty box would be a placeholder pretending otherwise.
                <span className="ws-pane__note">Not paginated</span>
              ) : null
            ) : null}
            <span className="ws-doccard__gap" />
            {view === "text" && rows.length > 0 ? (
              <>
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
              </>
            ) : null}
            <button type="button" className="ws-toolbtn" aria-label="Fullscreen" onClick={toggleFullscreen}>
              <IconMaximize />
            </button>
          </div>
          {view === "original" && canOriginal ? (
            <OriginalView versionId={version.id} filename={version.original_filename}
                          page={originalPage} />
          ) : rows.length === 0 ? (
            emptyTextState
          ) : (
          <div
            className="ws-text"
            ref={textRef}
            style={{ fontSize: `${zoom}%` }}
            onMouseUp={onTextSelect}
            onKeyUp={onTextSelect}
          >
            {pageGroups.map((group, index) => (
              <div key={`${group.page ?? "np"}-${index}`} className="ws-page">
                {/* When the WHOLE document has no page model (a DOCX has none
                    until printed), a lone "Unnumbered pages" banner is noise,
                    not information — every group is the same non-fact. Shown
                    only when it distinguishes this group from a numbered one
                    elsewhere in the same document. */}
                {group.page != null || pageGroups.length > 1 ? (
                  <p className="ws-page__marker" data-page-marker={group.page ?? undefined}>
                    {group.page != null ? `Page ${group.page}` : "Unnumbered pages"}
                    {/* 34.8 — OCR-derived content is identified. Identified at
                        the level it is true at: a wholly OCR page is labelled
                        once here, not on every paragraph (the per-row chip made
                        a recovered document unreadable for a second reason). A
                        mixed page keeps the per-row chip below, because there
                        the page-level claim would be false. */}
                    {group.rows.length > 0 && group.rows.every((row) => row.source_type === "OCR") ? (
                      <span className="ws-page__ocr" title="This page's text was recovered by OCR from the page image">
                        · recovered by OCR
                      </span>
                    ) : null}
                  </p>
                ) : null}
                {group.rows.map((row) => (
                  <article
                    key={row.id}
                    className={`ws-row${target === row.id ? " ws-row--lit" : ""}`}
                    data-evidence-id={row.id}
                    data-kind={rowKinds.get(row.id)}
                    tabIndex={-1}
                    aria-label={locationLabel(row)}
                  >
                    {row.source_type === "OCR" &&
                    !group.rows.every((r) => r.source_type === "OCR") ? (
                      <p className="ws-row__loc">
                        <span className="ws-row__ocr" title="Text recovered by OCR">OCR</span>
                      </p>
                    ) : null}
                    {sideTabs && (findingsByEvidence.get(row.id)?.length ?? 0) > 0 ? (
                      /* Named, not counted: "2 findings" would make the reader
                         click to discover what they are. A row with no finding
                         renders nothing at all — an affordance that leads
                         nowhere is worse than none. */
                      <p className="ws-row__findings">
                        <span className="ws-row__findlabel">The analysis of this clause:</span>
                        {findingsByEvidence.get(row.id)!.map((finding) => (
                          <button
                            key={finding.id}
                            type="button"
                            className="ws-escalate__link"
                            onClick={() => sideTabs.openFindings({ findingId: finding.id })}
                          >
                            {/* The reader's three words, not the engine's (seventh
                                pass) — one status vocabulary across the workspace. */}
                            {USER_STATUS_LABELS[userStatus(finding)]} ·{" "}
                            {requirementHeading(finding.requirement)}
                          </button>
                        ))}
                      </p>
                    ) : null}
                    <p className="ws-row__text">
                      {segmentContent(row.content, annotationsByRow.get(row.id) ?? []).map(
                        (segment, index) =>
                          segment.annotation ? (
                            <mark
                              key={index}
                              className="ws-anno"
                              tabIndex={0}
                              role="button"
                              title={segment.annotation.note || "Your highlight — open to add a note"}
                              aria-label={`Your highlight${segment.annotation.note ? `: ${segment.annotation.note}` : ""} — press Enter to edit`}
                              onClick={(event) => {
                                setOpenAnnotation({
                                  id: segment.annotation!.id,
                                  ...cardPoint(event.currentTarget.getBoundingClientRect()),
                                });
                              }}
                              onKeyDown={(event) => {
                                if (event.key !== "Enter" && event.key !== " ") return;
                                event.preventDefault();
                                setOpenAnnotation({
                                  id: segment.annotation!.id,
                                  ...cardPoint(event.currentTarget.getBoundingClientRect()),
                                });
                              }}
                            >
                              {segment.text}
                            </mark>
                          ) : (
                            segment.text
                          ),
                      )}
                    </p>
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
          )}
          {/* Select some document text → this small control marks it (DD-14).
              Reader marks live on this device only — never a Finding, never
              sent anywhere. */}
          {pendingMark ? (
            <div className="ws-markbtn" style={{ left: pendingMark.x, top: pendingMark.y }}>
              <button
                type="button"
                onClick={() => {
                  const created = add(pendingMark.rowId, pendingMark.start, pendingMark.end);
                  window.getSelection()?.removeAllRanges();
                  setOpenAnnotation({ id: created.id, x: pendingMark.x, y: pendingMark.y });
                  setPendingMark(null);
                }}
              >
                ✎ Highlight
              </button>
            </div>
          ) : null}
          {openAnnotation ? (
            <AnnotationEditor
              key={openAnnotation.id}
              annotation={annotations.find((a) => a.id === openAnnotation.id) ?? null}
              x={openAnnotation.x}
              y={openAnnotation.y}
              onSave={(note) => {
                setNote(openAnnotation.id, note);
                setOpenAnnotation(null);
              }}
              onRemove={() => {
                remove(openAnnotation.id);
                setOpenAnnotation(null);
              }}
              onClose={() => setOpenAnnotation(null)}
            />
          ) : null}
          {/* Readiness lives on the footer line (2026-09-02) — it is a fact about
              search capability (AM-29 honesty), not a control; the toolbar keeps
              only the PDF-viewer controls. */}
          <p className="ws-doccard__meta ws-mono">
            <span>
              v{version.version_number} · {version.original_filename}
            </span>
            <span className="ws-readiness" data-readiness={ready}>
              {READINESS_TEXT[ready]}
            </span>
          </p>
        </div>
      </div>
    </>
  );
}

/**
 * The Original view — the preserved original bytes (34.5) rendered by the
 * browser's own PDF renderer (no library, no new dependency: rule 19). The
 * bytes are fetched with the session's own credentials through the sanctioned
 * download endpoint and handed over as a blob URL; nothing is ever written,
 * derived, or "enhanced" — what renders is byte-for-byte what was uploaded.
 * Loaded lazily, only when this view is actually shown.
 */
function OriginalView({ versionId, filename, page }: {
  versionId: string; filename: string;
  /** Page to open at — the PDF viewer's own `#page=` open parameter, which is
   *  how a citation reaches the original without leaving it. */
  page: number | null;
}) {
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "ready"; url: string }
    | { kind: "failed"; error: unknown }
  >({ kind: "loading" });

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setState({ kind: "loading" });
    api
      .documentContentBlob(versionId)
      .then((blob) => {
        // This component only mounts when canOriginal already gated on
        // application/pdf, so the served blob's MIME needs no correcting.
        objectUrl = URL.createObjectURL(blob);
        if (cancelled) return;
        setState({ kind: "ready", url: objectUrl });
      })
      .catch((error) => {
        if (!cancelled) setState({ kind: "failed", error });
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [versionId]);

  if (state.kind === "loading") {
    return (
      <div className="ws-original ws-original--wait" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the original document…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "50%" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "92%" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "88%" }} aria-hidden="true" />
      </div>
    );
  }

  if (state.kind === "failed") {
    return (
      <div className="ws-original ws-original--wait">
        <div className="ws-state" role="alert">
          <h3>The original document could not be loaded.</h3>
          <p>{describeError(state.error)}</p>
          <p className="ws-pane__note">The extracted text view is still available above.</p>
        </div>
      </div>
    );
  }

  return (
    <iframe
      className="ws-original"
      title={`Original document — ${filename}`}
      src={page ? `${state.url}#page=${page}` : state.url}
    />
  );
}

/** The mark's editor — a note, remove, close. Plainly says where marks live:
 *  this browser only. Renders nothing if the mark was just removed. */
function AnnotationEditor({
  annotation, x, y, onSave, onRemove, onClose,
}: {
  annotation: import("./annotations").Annotation | null;
  x: number; y: number;
  onSave: (note: string) => void;
  onRemove: () => void;
  onClose: () => void;
}) {
  const [note, setNote] = useState(annotation?.note ?? "");
  if (!annotation) return null;
  return (
    <div className="ws-annopop" style={{ left: x, top: y }} role="dialog" aria-label="Your highlight">
      <textarea
        autoFocus
        rows={2}
        value={note}
        placeholder="Add a note (optional)…"
        onChange={(event) => setNote(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSave(note.trim());
          }
        }}
      />
      <div className="ws-annopop__acts">
        <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => onSave(note.trim())}>
          Save
        </button>
        <button type="button" className="ws-btn ws-btn--sm" onClick={onRemove}>
          Remove
        </button>
        <button type="button" className="ws-btn ws-btn--sm" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="ws-annopop__note">Saved on this device only — never part of a Finding.</p>
    </div>
  );
}

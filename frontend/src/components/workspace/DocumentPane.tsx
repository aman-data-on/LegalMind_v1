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

import { POINT_STATUS, PointStatusIcon, PointStatusLegend } from "./PointStatus";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { USER_STATUS_LABELS, pointAnswer, pointState, userStatus } from "./findingLanguage";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, EvidenceRow } from "@/lib/types";
import { UNREADABLE_WHY } from "@/lib/labels";

import { segmentContent, selectionInRow, useAnnotations, type Annotation } from "./annotations";
import { readingLayout, readingPieces, type ReadingLine } from "./reading";
import { hasTable, isFigure, textBlocks, type TableCell } from "./tableText";

/** A generated contract's house styles as the sheet's row kinds. */
const HOUSE_KIND: Record<string, "title" | "heading"> = {
  "LM Title": "title", "LM Schedule Title": "title", "LM Heading 1": "heading" };
import { useFindingsStateOptional } from "./findingsState";
import { useHighlight } from "./highlight";
import { useMinWidth, useSideTabs } from "./WorkspaceLayout";
import {
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconMaximize,
  IconSearch,
} from "./icons";
import {
  READINESS_TEXT,
  allOutlineNodes,
  clauseStatusByEvidenceId,
  documentTextState,
  groupByPage,
  locationLabel,
  findingsByEvidenceId,
  outlineAncestors,
  outlineTree,
  partLabel,
  requirementHeading,
  rollupBucket,
  sequenceBreaks,
  outlineStatus,
  readiness,
  readingNote,
  rowPresentation,
  visibleOutline,
  type ClauseStatus,
  type StatusBucket,
} from "./model";
import { ErrorState } from "@/components/Feedback";

const CONTENTS_KEY = "legalmind.workspace.contentsOpen";
const ZOOM_KEY = "legalmind.workspace.zoom";
const MARKS_KEY = "legalmind.workspace.marks";
const PAGE_SIZE = 100;
const ZOOM_STEPS = [85, 100, 115, 130, 150];

const EMPTY_FINDINGS = new Map<string, never[]>();
const EMPTY_STATUS = new Map<string, ClauseStatus>();

/** The marks are the one status set (`PointStatus`, AM-291 r5): the legend below, the
 *  Points filters and the Changes rows say the same four words with the same icons. */
const BUCKET_TITLE = POINT_STATUS;
function StatusIcon({ bucket }: { bucket: StatusBucket }) {
  return <PointStatusIcon bucket={bucket} />;
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
  const { target, point, exact, announcement } = useHighlight();
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

  /* The contents index collapses completely, for readers who want the paper to
     have the whole pane (owner, 2026-09-09). Remembered per browser, like the
     document toggle: a layout preference is this viewer's own convenience, it
     never needs to reach the server, and losing it costs one click. Read after
     mount — the server has no `localStorage`, and reading it in a `useState`
     initialiser is a hydration mismatch. */
  const [contentsOpen, setContentsOpen] = useState(true);
  /* page 2: on a phone the Contents is a sheet over the paper, opened from a "Contents"
     button and closed by choosing an entry — never a zero-height card above it. */
  const phoneWidth = useMinWidth(640) === false;
  /* …and the same sheet (a drawer over the paper) wherever the PANE is too narrow for the
     index and the paper side by side — the 620px the stacking container query used, which
     left a 240px card with an 8px list above the paper at ~1024px. */
  const [narrowPane, setNarrowPane] = useState(false);
  const paneWatch = useRef<ResizeObserver | null>(null);
  // a callback ref: the grid mounts only once the text has loaded
  const docRef = useCallback((el: HTMLDivElement | null) => {
    paneWatch.current?.disconnect();
    if (!el) return;
    paneWatch.current = new ResizeObserver(([entry]) => setNarrowPane((entry?.contentRect.width ?? 999) <= 620));
    paneWatch.current.observe(el);
  }, []);
  const sheet = phoneWidth || narrowPane;
  const contentsButton = useRef<HTMLButtonElement | null>(null);
  const hideContents = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (sheet) { setContentsOpen(false); return; }
    try {
      setContentsOpen(window.localStorage.getItem(CONTENTS_KEY) !== "0");
    } catch {
      // A viewer who blocks storage keeps the default, and their choice for
      // this visit only.
    }
  }, [sheet]);
  const chooseContents = useCallback((next: boolean) => {
    setContentsOpen(next);
    if (sheet) return;          // the phone's sheet is not a layout preference
    try {
      window.localStorage.setItem(CONTENTS_KEY, next ? "1" : "0");
    } catch { /* this visit only */ }
  }, [sheet]);

  // Toolbar state — presentation conveniences over the loaded rows.
  const [clauseQuery, setClauseQuery] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findIndex, setFindIndex] = useState(0);
  const [zoom, setZoom] = useState(100);
  // Remembered per browser like the two panel toggles — a reading preference.
  useEffect(() => {
    try {
      const stored = Number(window.localStorage.getItem(ZOOM_KEY));
      if (ZOOM_STEPS.includes(stored)) setZoom(stored);
    } catch { /* this visit only */ }
  }, []);
  const chooseZoom = useCallback((next: number) => {
    setZoom(next);
    try {
      window.localStorage.setItem(ZOOM_KEY, String(next));
    } catch { /* this visit only */ }
  }, []);
  const [currentPage, setCurrentPage] = useState<number | null>(null);
  /** Sections the reader has expanded in the Contents tree (2026-09-10). */
  const [openNodes, setOpenNodes] = useState<Set<string>>(() => new Set());
  const toggleNode = useCallback((id: string) => {
    setOpenNodes((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

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
  /** The Ask citation already shown in the text: going back to the original then
   *  turns its page, rather than bouncing the reader straight back to the text. */
  const exactShown = useRef<string | null>(null);
  useEffect(() => {
    if (!target || !rows) return;
    if (view !== "original") return;
    const cited = rows.find((row) => row.id === target);
    // An Ask citation asks for the passage itself (owner, 2026-10-08: "jump to and
    // highlight that part of the document"), and only the Text view can light it.
    if (cited?.page_number != null && (!exact || exactShown.current === target)) {
      setOriginalPage(cited.page_number);
      return;
    }
    // No page to turn to — the row exists only in the text view.
    if (exact) exactShown.current = target;
    setReturnToOriginal(true);
    setView("text");
  }, [target, rows, view, exact]);

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
  const canReread = can(P.DOCUMENT_UPLOAD) && findingsState?.isOwner === true
    && findingsState.state.kind === "no-review";

  async function reread() {
    setRereading(true);
    setRereadNote(null);
    try {
      const result = await api.reprocessVersion(version.id);
      if (result.document_version.processing_status === "PROCESSING") {
        setRereadNote("The text is being re-read. Reload the page in a moment.");
      } else if (result.processing_run.status === "FAILED") {
        setRereadNote("This file still could not be read. The earlier text stands.");
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
  // A page header or footer is the page's furniture, never the text (34.10, N11 #8): kept
  // out of the sheet and listed once, folded, after it.
  const furniture = useMemo(() => (rows ?? []).filter(isFurniture), [rows]);
  const pageGroups = useMemo(() => groupByPage((rows ?? []).filter((r) => !isFurniture(r))), [rows]);

  // Structural presentation per row (title / heading / item / paragraph) —
  // recognised from the text itself, never invented; see rowPresentation.
  const rowKinds = useMemo(() => {
    const map = new Map<string, string>();
    (rows ?? []).forEach((row, index) => map.set(row.id, row.house_style
      ? HOUSE_KIND[row.house_style] ?? "para"        // a generated contract says what it is
      : rowPresentation(row, index)));
    return map;
  }, [rows]);
  // The sheet's typesetting (CLM UI pass 2): each row's gutter number and indent.
  const lines = useMemo(() => {
    const list = rows ?? [];
    const set = readingLayout(list);
    return new Map(list.map((row, index) => [row.id, set[index]!]));
  }, [rows]);
  const hasMarks = useMemo(() => (rows ?? []).some((r) => r.changes?.length || r.comments?.length), [rows]);
  /* Tracked changes are marked in the text, Word-style, and can be switched off to
     read the clean text — a reading preference, remembered per browser. */
  // Read once in the initialiser: nothing it drives renders before the rows load on
  // the client, so the server's default can never mismatch.
  const [marksOn, setMarksOn] = useState(() => {
    try { return typeof window === "undefined" || window.localStorage.getItem(MARKS_KEY) !== "0"; }
    catch { return true; }
  });
  const chooseMarks = useCallback((next: boolean) => {
    setMarksOn(next);
    try { window.localStorage.setItem(MARKS_KEY, next ? "1" : "0"); } catch { /* this visit only */ }
  }, []);
  const showMarks = hasMarks && marksOn;
  const narrow = useMinWidth(900) === false;

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
      // on a phone the page scrolls, not the text (polish batch): watch the viewport then
      { root: narrow ? null : root, threshold: 0 },
    );
    markers.forEach((m) => observer.observe(m));
    return () => observer.disconnect();
  }, [pages, rows, narrow]);

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
  const note = readingNote(version);
  // The Contents as the document's own tree (2026-09-10) — see `outlineTree`.
  const tree = useMemo(() => (rows ? outlineTree(rows) : []), [rows]);
  const outline = useMemo(() => allOutlineNodes(tree), [tree]);
  // page 2: each top-level entry's declared part, the one shown before it, and a
  // skipped number ("12" then "14") said in its place — presentation only (AM-57).
  const { partBefore, gapBefore } = useMemo(() => {
    const before = new Map<string, string | null>();
    const gaps = new Map<string, string>();
    let part: string | null = null;
    let last: number | null = null;
    for (const node of tree) {
      before.set(node.row.id, part);
      const declared = partLabel(node.row);
      if (declared && declared !== part) { part = declared; last = null; }
      const n = node.number && /^\d+\.?$/.test(node.number) ? parseInt(node.number, 10) : null;
      if (n !== null) {
        if (last !== null && n === last + 2) gaps.set(node.row.id, `${last + 1} — no heading found`);
        else if (last !== null && n > last + 2) gaps.set(node.row.id, `${last + 1}–${n - 1} — no headings found`);
        if (last === null || n > last) last = n; else last = n;
      }
    }
    return { partBefore: before, gapBefore: gaps };
  }, [tree]);
  const searching = clauseQuery.trim().length > 0;
  const shownOutline = searching
    ? outline.filter((node) =>
        `${node.number ?? ""} ${node.title}`
          .toLowerCase()
          .includes(clauseQuery.trim().toLowerCase()))
    : visibleOutline(tree, (id) => openNodes.has(id));
  /* The Contents is ONE tab stop (WAI-ARIA tree-like roving focus): Tab lands on the entry
     last focused, else the cited one, else the first, and arrow keys move within it. */
  const [rove, setRove] = useState<string | null>(null);
  const tabStop = [rove, target].find((id) => id && shownOutline.some((n) => n.row.id === id))
    ?? shownOutline[0]?.row.id;
  /* Pointing at a passage opens the section that holds it, so the current entry
     is never hidden inside a collapsed parent. The target may be a body row
     rather than an outline entry; its owner is the nearest entry before it. */
  useEffect(() => {
    if (!target || !rows || outline.length === 0) return;
    const ids = new Set(outline.map((node) => node.row.id));
    let owner: string | null = null;
    for (const row of rows) {
      if (ids.has(row.id)) owner = row.id;
      if (row.id === target) break;
    }
    if (!owner) return;
    const ancestors = outlineAncestors(tree, owner);
    if (ancestors.length === 0) return;
    setOpenNodes((previous) => {
      if (ancestors.every((id) => previous.has(id))) return previous;
      return new Set([...previous, ...ancestors]);
    });
  }, [target, rows, tree, outline]);

  if (error) {
    return (
      <div className="ws-card ws-card--pad">
        <ErrorState heading="h3" title="The document text could not be loaded" error={error}
                    onRetry={() => window.location.reload()} />
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
        {documentTextState(version) === "unreadable"
          && UNREADABLE_WHY[version.unreadable_reason ?? ""] ? (
          <div className="ws-state">
            <h3>This document could not be read.</h3>
            <p>{UNREADABLE_WHY[version.unreadable_reason ?? ""]}</p>
          </div>
        ) : documentTextState(version) === "unreadable" ? (
          <div className="ws-state">
            <h3>No readable text could be extracted from this document.</h3>
            <p>
              The file is an unreadable scan, or its fonts do not map to readable text. Nothing can be cited or reviewed from this version.
            </p>
            <p className="ws-pane__note">
              Export it again from the original source, or upload the Word file.
            </p>
          </div>
        ) : documentTextState(version) === "processing" ? (
          <div className="ws-state">
            <h3>Text is still being recovered from this document.</h3>
            <p>
              {canOriginal
                ? "The original is in the Original tab. The text and analysis appear here when ready."
                : "The text appears here when ready."}
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
              The file is an unreadable scan, or its fonts do not map to readable text. Nothing can be cited or reviewed from this version.
            </p>
            <p className="ws-pane__note">
              Export it again from the original source, or upload the Word file.
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
      <div className="ws-doc" data-contents={contentsOpen ? "open" : "closed"}
           data-sheet={sheet ? "" : undefined} ref={docRef}>
        {sheet && contentsOpen ? (
          <button type="button" className="ws-doc__scrim" aria-label="Close contents"
                  onClick={() => chooseContents(false)} />
        ) : null}
        {/* ------------------------------------------------ clauses column */}
        {/* Kept MOUNTED while collapsed (`hidden`, not unmounted) so the search
            text and the list's scroll position survive a collapse — and `hidden`
            is what takes the region out of the accessibility tree, which is
            correct for a collapsed disclosure. */}
        <div className="ws-doc__clauses" id="ws-contents" hidden={!contentsOpen}
             onKeyDown={sheet ? (event) => {
               if (event.key !== "Escape") return;
               event.stopPropagation();
               chooseContents(false);
               contentsButton.current?.focus();
             } : undefined}>
          <nav className="ws-card ws-outline" aria-label="Document outline">
            {/* "Contents", not "Clauses" (2026-09-05). This is the document's
                own outline — its headings — and a clause is the unit a finding
                attaches to, not a navigation target. The two were the same list
                until the parser could tell a heading from body text. */}
            <div className="ws-outline__head">
              <p className="ws-outline__title">Contents</p>
              <button
                type="button"
                ref={hideContents}
                className="ws-outline__collapse"
                aria-expanded={contentsOpen}
                aria-controls="ws-contents"
                aria-label="Hide contents"
                title="Hide contents"
                onClick={() => chooseContents(false)}
              >
                <PanelLeftClose size={16} aria-hidden focusable="false" />
              </button>
            </div>
            <label className="ws-outline__search">
              <IconSearch size={14} />
              <span className="ws-visually-hidden">Search contents</span>
              <input
                value={clauseQuery}
                onChange={(event) => setClauseQuery(event.target.value)}
                placeholder="Search contents"
              />
            </label>
            <div className="ws-outline__list" onKeyDown={(event) => {
              const jumps = [...event.currentTarget.querySelectorAll<HTMLElement>(".ws-outline__jump")];
              const at = jumps.indexOf(event.target as HTMLElement);
              const to = at < 0 ? -1 : event.key === "ArrowDown" ? Math.min(at + 1, jumps.length - 1)
                : event.key === "ArrowUp" ? Math.max(at - 1, 0)
                : event.key === "Home" ? 0 : event.key === "End" ? jumps.length - 1 : -1;
              if (to < 0) return;
              event.preventDefault();
              jumps[to]?.focus();
            }}>
              {shownOutline.map((node) => {
                const { row } = node;
                // A search shows its matches flat; the tree's own chevrons only
                // mean something while the tree is showing.
                const branch = node.children.length > 0 && !searching;
                const expanded = branch && openNodes.has(row.id);
                // A collapsed section carries its worst hidden clause's marker.
                const bucket = rollupBucket(node, clauseStatus, branch && !expanded);
                const label = `${node.number ?? ""} ${node.title}`.trim() || "Untitled clause";
                // The number and title exactly as the document states them —
                // never a "§", never a number the file does not carry.
                return (
                  <Fragment key={row.id}>
                  {/* A new part of the document. When the file DECLARES it —
                      "Annexure-1", "Schedule 2" — the divider says the kind
                      the document's own title uses (44.4). When it only
                      restarts its numbering, the divider says just that:
                      naming what the part IS would be inventing structure. */}
                  {/* page 2: a declared part once ("Annexure-1"), never a "numbering
                      restarts" label; a top-level number the document skips is said
                      where it would be, so a missing clause is never silent */}
                  {partLabel(row) && partLabel(row) !== partBefore.get(row.id) ? (
                    <p className="ws-outline__break">{partLabel(row)}</p>
                  ) : null}
                  {!searching && gapBefore.get(row.id) ? (
                    <p className="ws-outline__gap">{gapBefore.get(row.id)}</p>
                  ) : null}
                  <div
                    className="ws-outline__node"
                    data-depth={!searching && node.depth > 0 ? Math.min(3, node.depth) : undefined}
                    data-leaf={node.leaf ? "true" : undefined}
                  >
                    {branch ? (
                      <button
                        type="button"
                        className="ws-outline__twist"
                        tabIndex={-1}
                        aria-expanded={expanded}
                        aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
                        onClick={() => toggleNode(row.id)}
                      >
                        {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                      </button>
                    ) : (
                      <span className="ws-outline__twist ws-outline__twist--none" aria-hidden="true" />
                    )}
                    <button
                      type="button"
                      className="ws-outline__jump"
                      title={label}
                      tabIndex={row.id === tabStop ? 0 : -1}
                      aria-expanded={branch ? expanded : undefined}
                      aria-current={target === row.id ? "true" : undefined}
                      onFocus={() => setRove(row.id)}
                      onKeyDown={(event) => {
                        if (branch && (event.key === "ArrowRight" ? !expanded : event.key === "ArrowLeft" && expanded)) {
                          event.preventDefault();
                          toggleNode(row.id);
                        }
                      }}
                      onClick={() => {
                        point(row.id, node.number ? `clause ${node.number}` : "the selected");
                        if (sheet) chooseContents(false);
                      }}
                    >
                      <span className="ws-outline__label">
                        {node.number ? <span className="ws-mono">{node.number}</span> : null}
                        {node.title || (node.number ? "" : "Untitled clause")}
                      </span>
                      {bucket ? <StatusIcon bucket={bucket} /> : null}
                    </button>
                  </div>
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
            {/* The page jump and the marker key, in the SAME card as the list
                they belong to (owner, 2026-09-09: "Almost everything is
                surrounded by cards/boxes… Reduce unnecessary borders and
                cards"). The legend was its own bordered card directly beneath
                this one, which is a box around three lines of key. A divider
                and the spacing carry the separation now. */}
            <div className="ws-outline__foot">
              {pages.length > 0 ? (
                /* Jump straight to a page — the same jump the toolbar's page
                   field performs, offered where the outline already lives. */
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
              ) : null}
              <div className="ws-legend" role="note" aria-label="Status legend">
                <PointStatusLegend />
              </div>
            </div>
          </nav>
        </div>
        {/* Collapsed: a rail that gives the paper the pane and says how to get
            the index back. Same control, same `aria-controls`, opposite state. */}
        {contentsOpen || sheet ? null : (
          <button
            type="button"
            className="ws-doc__rail"
            aria-expanded={false}
            aria-controls="ws-contents"
            aria-label="Show contents"
            title="Show contents"
            onClick={() => chooseContents(true)}
          >
            <PanelLeftOpen size={16} aria-hidden focusable="false" />
          </button>
        )}

        {/* ------------------------------------------------ document card */}
        <div className="ws-card ws-doccard" ref={cardRef}>
          <div className="ws-doccard__bar" role="toolbar" aria-label="Document controls">
            {sheet ? (
              <button type="button" className="ws-toolbtn ws-toolbtn--text ws-doccard__contents"
                      ref={contentsButton}
                      aria-expanded={contentsOpen} aria-controls="ws-contents"
                      onClick={() => {
                        chooseContents(!contentsOpen);
                        // into the sheet it opened (its own close button: no keyboard pops up)
                        if (!contentsOpen) requestAnimationFrame(() => hideContents.current?.focus());
                      }}>
                <PanelLeftOpen size={16} aria-hidden focusable="false" /> Contents
              </button>
            ) : null}
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
                {rereading ? "Re-reading…" : "Re-read document"}
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
                <span>
                  {/* The text view is where a passage can be lit; say why the reader is here. */}
                  {(() => {
                    const page = rows?.find((row) => row.id === target)?.page_number;
                    return page != null
                      ? `Highlighted in the text — page ${page} in the original`
                      : "This passage has no page in the original";
                  })()}
                </span>
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
                <input
                  aria-label="Find text in the document"
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
              ) : null   // a DOCX has no fixed pages: nothing to say rather than a "not paginated" note
            ) : null}
            <span className="ws-doccard__gap" />
            {view === "text" && hasMarks ? (
              <button type="button" className="ws-toolbtn ws-toolbtn--text" aria-pressed={marksOn}
                      onClick={() => chooseMarks(!marksOn)}>
                {marksOn ? "Hide changes" : "Show changes"}
              </button>
            ) : null}
            {view === "text" && rows.length > 0 ? (
              <>
                <button
                  type="button"
                  className="ws-toolbtn"
                  aria-label="Zoom out"
                  disabled={zoom === ZOOM_STEPS[0]}
                  onClick={() => chooseZoom(ZOOM_STEPS[Math.max(0, ZOOM_STEPS.indexOf(zoom) - 1)]!)}
                >
                  −
                </button>
                <span className="ws-mono ws-doccard__zoom">{zoom}%</span>
                <button
                  type="button"
                  className="ws-toolbtn"
                  aria-label="Zoom in"
                  disabled={zoom === ZOOM_STEPS[ZOOM_STEPS.length - 1]}
                  onClick={() => chooseZoom(ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, ZOOM_STEPS.indexOf(zoom) + 1)]!)}
                >
                  +
                </button>
              </>
            ) : null}
            <button type="button" className="ws-toolbtn" aria-label="Fullscreen" onClick={toggleFullscreen}>
              <IconMaximize />
            </button>
            {/* Fold the document away from its own header (owner, 2026-10-08) — the
                Contents panel's icon, so the gesture reads the same everywhere; the
                Summary/Findings row's matching icon brings it back. */}
            {sideTabs?.hideDocument ? (
              <button type="button" className="ws-toolbtn" aria-label="Hide document"
                      title="Hide document" onClick={sideTabs.hideDocument}>
                <PanelLeftClose size={16} aria-hidden focusable="false" />
              </button>
            ) : null}
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
            style={{ "--ws-zoom": zoom / 100 } as React.CSSProperties}
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
                    data-kind={row.part ? "para" : rowKinds.get(row.id)}
                    data-part={row.part}
                    data-house={row.house_style ? row.house_style.slice(3).toLowerCase().replace(/\s+\d$/, "") : undefined}
                    data-shape={lines.get(row.id)?.shape ?? undefined}
                    data-changed={showMarks && (row.changes?.length ?? 0) > 0 ? "" : undefined}
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
                      /* The way back from a clause to its point (restored 2026-11-05, owner
                         item (a)). Named, not counted; a row no point cites renders nothing. */
                      <p className="ws-row__findings">
                        <span className="ws-row__findlabel">The analysis of this clause:</span>
                        {findingsByEvidence.get(row.id)!.map((finding) => (
                          <button key={finding.id} type="button" className="ws-escalate__link"
                                  onClick={() => sideTabs.openFindings({ findingId: finding.id })}>
                            {/* B7: a decided point says its answer, as the Points pane does */}
                            {(pointState(finding) === "decided" ? pointAnswer(finding, false) : null)
                              ?? USER_STATUS_LABELS[userStatus(finding)]} · {requirementHeading(finding.requirement)}
                          </button>
                        ))}
                      </p>
                    ) : null}
                    <RowText row={row} line={lines.get(row.id)} marks={showMarks}
                             annotations={annotationsByRow.get(row.id) ?? []}
                             onOpen={(id, el) => setOpenAnnotation({
                               id, ...cardPoint(el.getBoundingClientRect()) })} />
                  </article>
                ))}
              </div>
            ))}
            {furniture.length ? (
              <details className="ws-furniture">
                <summary>Page header and footer</summary>
                {furniture.map((row) => (
                  <p key={row.id} data-evidence-id={row.id} tabIndex={-1}>{row.content}</p>
                ))}
              </details>
            ) : null}
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
          {/* page 2: the version and file name are the header's; the search line was the
              system describing itself. Only the reading's own account of what it could
              not read stays (R3). */}
          {note ? (
            <p className="ws-doccard__meta">
              <span className="ws-readiness" title={note}>{note}</span>
            </p>
          ) : null}
        </div>
      </div>
    </>
  );
}

/**
 * One row's text on the sheet (CLM UI pass 2). The `<p>`'s text content is exactly
 * `row.content` — the gutter number is a span around the text's own number (or, for a
 * heading, the parser's number drawn by CSS from `data-num`), a defined term a
 * `<strong>`, a change an `<ins>` whose replaced words are drawn by CSS — so selection
 * offsets and highlights address the unmodified evidence string (rule 17).
 */
function RowText({ row, line, marks, annotations, onOpen }: {
  row: EvidenceRow;
  line: ReadingLine | undefined;
  marks: boolean;
  annotations: Annotation[];
  onOpen: (id: string, element: HTMLElement) => void;
}) {
  // A row holding a table is set as prose blocks and tables (N11 #1); its changes are
  // listed under it, and saved highlights are drawn in their cell (`Marked`).
  // ponytail: a NEW highlight is made in paragraph text only — selecting in a table cell
  // does not map to the row's offsets yet.
  const tabled = hasTable(row.content);
  const { pieces, unplaced, lead } = tabled
    ? { pieces: [], unplaced: row.changes ?? [], lead: 0 }
    : readingPieces(row.content, {
      lead: line?.lead ?? 0, changes: row.changes ?? [], annotations, marks,
      ...(row.emphasis ? { emphasis: row.emphasis } : {}) });
  const hung = !!line && (lead > 0 || !!line.num);
  const style = line ? ({ "--indent": `${line.indent}em`, "--hang": `${hung ? line.hang : 0}em` } as React.CSSProperties) : undefined;
  return (
    <>
      {row.part === "footnote" || row.part === "endnote" ? (
        <p className="ws-row__note">
          <span className="ws-row__noteskind">{row.part === "footnote" ? "Footnote" : "Endnote"}</span>{" "}
          {row.content}
        </p>
      ) : tabled ? (
        textBlocks(row.content).map((block, index) => block.kind === "text" ? (
          block.text.trim() ? (
            <p key={index} className="ws-row__plain" style={style}>
              <Marked text={block.text} start={block.start} annotations={annotations} onOpen={onOpen} />
            </p>
          ) : null
        ) : (
          <DocTable key={index} rows={block.rows} annotations={annotations} onOpen={onOpen} />
        ))
      ) : (
      <p className="ws-row__text" style={style} data-hang={hung ? "" : undefined}
         data-num={line?.num ?? undefined}>
        {pieces.map((piece, index) => {
          let node: React.ReactNode = piece.text;
          if (piece.term) node = <strong className="ws-row__term">{node}</strong>;
          if (piece.bold) node = <strong>{node}</strong>;
          if (piece.underline) node = <u>{node}</u>;
          if (piece.ins) {
            node = <ins className="ws-mark" data-del={piece.ins.del}>{node}</ins>;
          }
          if (piece.annotation) {
            const a = piece.annotation;
            node = (
              <mark className="ws-anno" tabIndex={0} role="button"
                    title={a.note || "Your highlight — open to add a note"}
                    aria-label={`Your highlight${a.note ? `: ${a.note}` : ""} — press Enter to edit`}
                    onClick={(event) => onOpen(a.id, event.currentTarget)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      onOpen(a.id, event.currentTarget);
                    }}>
                {node}
              </mark>
            );
          }
          if (piece.lead) node = <span className="ws-row__num">{node}</span>;
          return <Fragment key={index}>{node}</Fragment>;
        })}
      </p>
      )}
      {row.unread_image ? (
        <p className="ws-row__unread" role="note">
          {row.unread_image.number
            ? `Clause ${row.unread_image.number} is an image in this file; its text could not be read.`
            : `Part of page ${row.unread_image.page ?? "this page"} is an image; its text could not be read.`}
          {" "}Check the original.
        </p>
      ) : null}
      {(marks && unplaced.length) || row.comments?.length ? (
        // what the text itself cannot show: a removal with no words left in its place,
        // and the notes made on this passage — one quiet line each, at the text's indent
        <div className="ws-row__notes" style={style} aria-label="Changes and notes on this passage">
          {marks && unplaced.length ? (
            <p>
              <span className="ws-row__noteskind">Also changed</span>{" "}
              {unplaced.map((c, i) => (
                <span key={i} className="ws-row__notechange">
                  {c.deleted && c.inserted ? <>&ldquo;<del>{c.deleted}</del>&rdquo; to &ldquo;<ins>{c.inserted}</ins>&rdquo;</>
                    : c.deleted ? <>removed &ldquo;<del>{c.deleted}</del>&rdquo;</>
                    : <>added &ldquo;<ins>{c.inserted}</ins>&rdquo;</>}
                </span>
              ))}
            </p>
          ) : null}
          {row.comments?.map((n, i) => (
            <p key={`n${i}`}>
              <span className="ws-row__noteskind">Note{n.author ? ` · ${n.author}` : ""}</span> {n.text}
            </p>
          ))}
        </div>
      ) : null}
    </>
  );
}

function isFurniture(row: EvidenceRow): boolean {
  return row.part === "header" || row.part === "footer";
}

/** A table from the file, set as a table (N11 #1): it scrolls inside its own frame on a
 *  narrow screen, never the page. The first row is the table's own heading row. */
/** ``text`` (at ``start`` in its row's content) with the reader's highlights that fall in
 *  it drawn as they are in a paragraph — a highlight saved on a table row still shows in
 *  its cell (review 2026-11-09). */
function Marked({ text, start, annotations, onOpen }: {
  text: string; start: number; annotations: Annotation[];
  onOpen: (id: string, element: HTMLElement) => void;
}) {
  if (start < 0 || annotations.length === 0) return <>{text}</>;
  const own = annotations.map((a) => ({ ...a, start: a.start - start, end: a.end - start }));
  return (
    <>
      {segmentContent(text, own).map((seg, i) => seg.annotation ? (
        <mark key={i} className="ws-anno" tabIndex={0} role="button"
              title={seg.annotation.note || "Your highlight — open to add a note"}
              aria-label={`Your highlight${seg.annotation.note ? `: ${seg.annotation.note}` : ""} — press Enter to edit`}
              onClick={(event) => onOpen(seg.annotation!.id, event.currentTarget)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                onOpen(seg.annotation!.id, event.currentTarget);
              }}>{seg.text}</mark>
      ) : <Fragment key={i}>{seg.text}</Fragment>)}
    </>
  );
}

/** A table from the file, set as a table (N11 #1): it scrolls inside its own frame on a
 *  narrow screen, never the page. The first row is the table's own heading row. */
function DocTable({ rows, annotations, onOpen }: {
  rows: TableCell[][]; annotations: Annotation[];
  onOpen: (id: string, element: HTMLElement) => void;
}) {
  const [head, ...body] = rows;
  const mark = (text: string, start: number) => (
    <Marked text={text} start={start} annotations={annotations} onOpen={onOpen} />);
  const cells = (row: TableCell[], heading: boolean) => row.map((c, i) => {
    const content = c.nested ? (
      <table className="ws-table ws-table--nested">
        <tbody>{c.nested.map((r, j) => (
          <tr key={j}>{r.map((t, k) => <td key={k}>{mark(t, c.nestedStart?.[j]?.[k] ?? -1)}</td>)}</tr>
        ))}</tbody>
      </table>
    ) : mark(c.text, c.start);
    return heading
      ? <th key={i} scope="col" colSpan={c.span > 1 ? c.span : undefined}>{content}</th>
      : <td key={i} colSpan={c.span > 1 ? c.span : undefined}
            data-figure={isFigure(c.text) ? "" : undefined}>{content}</td>;
  });
  return (
    <div className="ws-tablewrap" role="region" aria-label="Table" tabIndex={0}>
      <table className="ws-table">
        {head && rows.length > 1 ? <thead><tr>{cells(head, true)}</tr></thead> : null}
        <tbody>{(rows.length > 1 ? body : rows).map((row, i) => <tr key={i}>{cells(row, false)}</tr>)}</tbody>
      </table>
    </div>
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
        // Checked first: a URL made after the cleanup ran is never revoked.
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
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
        aria-label="Note for this highlight"
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

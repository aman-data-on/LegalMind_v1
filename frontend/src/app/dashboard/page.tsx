"use client";

/**
 * Dashboard — the working inventory and the front door — and one contract's
 * workspace (2026-09-01 professional-polish redesign, owner-directed;
 * supersedes the 2026-08-31 UX correction's visual shape while keeping every
 * one of its rules: upload-first intake, human-declared type, permission-
 * layered `latest_analysis`, byte-identical scope).
 *
 * Both views live at the fixed pathname `/dashboard`; which one renders is
 * decided by the `?id=` query parameter rather than a path segment, so no
 * record id ever appears in the URL path itself. Every other query param a
 * link into the workspace carries (`classification`, `evidence`, `finding`,
 * `version`) is unaffected — `WorkspacePage` still reads those itself. This
 * redesign touches ONLY the list view below; the workspace import and its
 * behaviour are untouched.
 *
 * The status vocabulary on this page is FOUR DERIVED BUCKETS
 * (`documentStatusBucket`) — draft / analyzing / needs_attention / analyzed —
 * never a new lifecycle enum and never a Finding Classification (REC-02's
 * boundary). The server computes the identical bucket for `?status=` and for
 * the stat-tile summary (`_status_bucket`), so a tile, a filter and a row can
 * never disagree with each other.
 *
 * Each row's Findings column shows the real Step-19 classifications the
 * workspace already uses (DD-9's match/review/missing coloring) — never an
 * invented status; a contract with no analysis yet shows an honest dash, not
 * a zero implying something was checked.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { api, describeError, type ContractScope } from "@/lib/api";
import { DOCUMENT_SOURCES, DOCUMENT_TYPES, documentTypeLabel } from "@/lib/documentTypes";
import { CONTRACT_STATUSES } from "@/lib/labels";
import * as P from "@/lib/permissions";
import { chainAnalysis } from "@/lib/analysisChain";
import { useSession } from "@/lib/session";
import type { Contract, ContractsSummary, Counterparty, DepartmentMembers, Pagination } from "@/lib/types";

import {
  documentStatusBucket,
  knownCounterparties,
  relativeTime,
  STATUS_BUCKET_LABEL,
  type DocumentStatusBucket,
} from "@/components/workspace/model";
import { Pipeline } from "@/components/workspace/Pipeline";
import { UploadContract } from "@/components/workspace/UploadContract";
import { WorkspacePage } from "@/components/workspace/WorkspacePage";
import {
  IconAlertCircle,
  IconCheckCircle,
  IconChevronRight,
  IconClock,
  IconFile,
  IconSearch,
  IconXCircle,
} from "@/components/workspace/icons";

const PAGE_SIZE = 25;

/** The seven columns, in one place — the table renders them and so does the
 *  loading skeleton, which must reserve the header's height or the whole body
 *  jumps down the instant data lands. */
const COLUMNS = [
  "Document", "Type", "Status", "Findings", "Last Analyzed", "Added", "Action",
] as const;

function TableHead() {
  return (
    <tr>
      {COLUMNS.map((column) => <th key={column} scope="col">{column}</th>)}
    </tr>
  );
}

const STATUS_ICON: Record<DocumentStatusBucket, React.ReactNode> = {
  draft: <IconClock size={13} />,
  analyzing: <span className="ws-spin" aria-hidden="true" />,
  needs_attention: <IconAlertCircle size={13} />,
  analyzed: <IconCheckCircle size={13} />,
};

function StatusPill({ contract }: { contract: Contract }) {
  const bucket = documentStatusBucket(contract);
  return (
    <span className={`ws-status-pill ws-status-pill--${bucket}`}>
      {STATUS_ICON[bucket]} {STATUS_BUCKET_LABEL[bucket]}
    </span>
  );
}

/** The four real classification buckets, always in the same order, dashes
 *  when nothing has been analyzed yet — never a zero standing in for "not
 *  checked". Each populated badge is a real link, pre-filtered exactly like
 *  the workspace's own classification chips. */
function FindingsCell({ contract }: { contract: Contract }) {
  const analyzed = documentStatusBucket(contract) !== "draft"
    && documentStatusBucket(contract) !== "analyzing";
  const counts = contract.latest_analysis?.user_status_counts;
  if (!analyzed || !counts) {
    return <span className="ws-findings-cell ws-pane__note">—</span>;
  }
  // Accepted · Needs review · Not accepted — the same three words as the card.
  const buckets: Array<{ key: "match" | "review" | "missing"; n: number }> = [
    { key: "match", n: counts.ACCEPTED ?? 0 },
    { key: "review", n: counts.NEEDS_REVIEW ?? 0 },
    { key: "missing", n: counts.NOT_ACCEPTED ?? 0 },
  ];
  return (
    <span className="ws-findings-cell">
      {buckets.map(({ key, n }) => (
        <span key={key} className={`ws-findings-badge ws-findings-badge--${key}${n === 0 ? " ws-findings-badge--zero" : ""}`}>
          {n}
        </span>
      ))}
    </span>
  );
}

/** A count, and — only where one exists — somewhere to go with it. `onSelect`
 *  turns the tile into a real button; without it the tile stays inert markup
 *  rather than a control that looks clickable and does nothing. */
function StatTile({
  icon, n, label, bucket, onSelect,
}: {
  icon: React.ReactNode; n: number; label: string;
  bucket?: DocumentStatusBucket; onSelect?: () => void;
}) {
  /* `--act` is what carries the hover lift and the pointer: a tile without an
     `onSelect` is a plain count, and giving all four the same hover response
     advertised three controls that do nothing (2026-09-08 audit). */
  const className = `ws-doctile${bucket ? ` ws-doctile--${bucket}` : ""}`
    + (onSelect ? " ws-doctile--act" : "");
  const body = (
    <>
      <div className="ws-doctile__head">
        <span className="ws-doctile__label">{label}</span>
        <span className="ws-doctile__icon" aria-hidden="true">{icon}</span>
      </div>
      <span className="ws-doctile__n ws-mono">{n}</span>
    </>
  );
  if (!onSelect) return <div className={className}>{body}</div>;
  return (
    <button type="button" className={className} onClick={onSelect}>
      {body}
      <span className="ws-visually-hidden">Show these contracts</span>
    </button>
  );
}

function DocumentsListView() {
  const { can, identity } = useSession();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [summary, setSummary] = useState<ContractsSummary | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [qInput, setQInput] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatusBucket | "">("");
  const [sort, setSort] = useState("created_desc");
  /** AB-12 r3 — "My deals" is every account's default; "Department deals" exists
   *  only for a holder of `department.view`, and the server scopes the query on
   *  its own either way. */
  const [scope, setScope] = useState<ContractScope>("own");
  /** AB-12 r6 — the shelf, kept apart from the working list. */
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  /** The row whose action menu is open, and the row being edited or deleted.
   *
   *  The menu itself renders through a portal (see `.ws-menu__list` below and
   *  `menuPortalTarget` further down): `menuPos` is the fixed-viewport
   *  coordinate it renders at, captured from the toggle button's own position
   *  at open time. Without the portal, the menu's nearest positioned ancestor
   *  is inside `.ws-docs__table`, which clips overflow for its own reasons
   *  (the horizontal scroller, the rounded card on the index view) — so a
   *  menu opened on any row got silently cut off at the table's edge instead
   *  of floating above the page. Positioning by viewport coordinates escapes
   *  every such ancestor, not just this one. */
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{
    top?: number; bottom?: number; right: number; minWidth: number;
  } | null>(null);
  const [editing, setEditing] = useState<Contract | null>(null);
  /** AB-13 r6 — the companies THIS caller deals with; the server scopes it. */
  const [companies, setCompanies] = useState<Counterparty[]>([]);
  const [archiving, setArchiving] = useState<Contract | null>(null);
  const [deleting, setDeleting] = useState<Contract | null>(null);
  const [transferring, setTransferring] = useState<Contract | null>(null);
  /** The open menu's own node, and the toggle that opened it — a menu is not
   *  part of the page's tab ring, so it has to move focus in itself and hand
   *  focus back when it closes. Before this, opening the menu with the keyboard
   *  left focus on the toggle and the next Tab went to the FOLLOWING ROW's
   *  document link (measured 2026-09-08): every item in it was unreachable
   *  without a pointer. */
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuToggleRef = useRef<HTMLElement | null>(null);
  /** Which list request is the current one — see `load` below. */
  const loadSeq = useRef(0);

  function closeMenu(restoreFocus = false) {
    setMenuFor(null);
    setMenuPos(null);
    if (restoreFocus) menuToggleRef.current?.focus();
  }

  /** Arrows move within the menu and wrap; Tab and Escape close it and return
   *  focus to the toggle, which is the WAI-ARIA menu-button behaviour. (No
   *  Home/End: the menu holds three items at most, where both keys are one
   *  arrow press.) */
  function onMenuKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']") ?? [],
    );
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Tab" || event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    const to = event.key === "ArrowDown" ? (at + 1) % items.length
      : event.key === "ArrowUp" ? (at - 1 + items.length) % items.length
      : -1;
    if (to < 0) return;
    event.preventDefault();
    items[to]?.focus();
  }

  /** Where the portal renders (2026-09-03 fix, owner-reported against the
   *  live site). EVERY design token this app has — `--ws-surface`,
   *  `--ws-z-dialog`, `--ws-radius`, all of it — is scoped to the `.ws`
   *  wrapper class (`WorkspaceShell.tsx`), not `:root` (deliberately, so this
   *  stylesheet and the legacy one never fight over a global scope). A first
   *  version of this fix portaled straight into `document.body`, which sits
   *  OUTSIDE `.ws` — so the menu lost every one of those tokens. `z-index:
   *  var(--ws-z-dialog)` fell back to `auto` and `background:
   *  var(--ws-surface)` fell back to transparent. It still correctly
   *  occluded clicks (confirmed by hit-testing: DOM order alone put it on
   *  top), but with no opaque background to back that up, the row underneath
   *  visually painted straight through it — exactly the "still overlapping"
   *  screenshot this fix answers. Portaling into `.ws` itself instead keeps
   *  every token, and `.ws` sets no `transform`/`filter`/`contain` of its
   *  own, so `position: fixed` still resolves against the viewport exactly
   *  as the positioning math in `openMenu` assumes. */
  function menuPortalTarget(): Element {
    return document.querySelector(".ws") ?? document.body;
  }

  /** Opens toward the row's start edge, flipping to open ABOVE the toggle when
   *  the row is near the bottom of the viewport — otherwise a menu on the last
   *  visible row would render below the fold instead of just below the
   *  table's clipping edge.
   *
   *  Width is the wider of 168px and the row's own Action `<td>` (2026-09-03
   *  fix, owner-reported against the live site): a menu narrower than the
   *  cell it floats over covers only PART of the row below — that row's own
   *  "Review"/"Analyze" link and toggle peek out from under one edge instead
   *  of being cleanly hidden, which reads as a rendering glitch rather than an
   *  intentional overlay. Every row shares one table column, so anchoring to
   *  THIS row's cell width and right edge guarantees full coverage of
   *  whichever row's Action cell the menu ends up floating over. */
  function openMenu(id: string, toggle: HTMLElement) {
    menuToggleRef.current = toggle;
    const rect = toggle.getBoundingClientRect();
    const cellRect = toggle.closest("td")?.getBoundingClientRect() ?? rect;
    const estimatedHeight = 176; // up to four items (Edit, Transfer, Archive, Delete) plus padding
    const opensAbove = window.innerHeight - rect.bottom < estimatedHeight + 8;
    setMenuPos({
      right: window.innerWidth - rect.right,
      minWidth: Math.max(168, cellRect.width),
      ...(opensAbove
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
    setMenuFor(id);
  }

  const load = useCallback(async () => {
    // Only the NEWEST request may write to the table (2026-09-08). Every filter,
    // sort, page and scope change fires a request and none of them cancels the
    // last, so two were routinely in flight while someone worked the toolbar —
    // and nothing said they had to come back in order. A slower earlier response
    // landing second repainted the table with the PREVIOUS filter's rows while
    // every control still read the new one: a table that quietly disagrees with
    // the toolbar above it, which on this page means disagreeing about which
    // contracts need attention.
    const seq = loadSeq.current + 1;
    loadSeq.current = seq;
    const current = () => seq === loadSeq.current;
    setError(null);
    try {
      const result = await api.contracts(page, PAGE_SIZE, {
        q: q || undefined,
        contract_type: typeFilter || undefined,
        status: statusFilter || undefined,
        sort,
        scope,
        archived: showArchived || undefined,
      });
      if (!current()) return;
      setContracts(result.items);
      setPagination(result.pagination);
      // The companies this caller deals with, for the edit dialog's picker.
      // Best-effort: the list is a convenience, and failing to load it must not
      // take the whole Dashboard down.
      try {
        const companyList = await api.counterparties();
        if (current()) setCompanies(companyList);
      } catch {
        if (current()) setCompanies([]);
      }
    } catch (cause) {
      // A superseded request's failure is not this view's failure either: it
      // would otherwise raise a banner over rows that loaded perfectly well.
      if (current()) setError(cause);
    }
  }, [page, q, typeFilter, statusFilter, sort, scope, showArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  // The stat tiles are independent of the current page/filter — real counts
  // across every contract the caller owns, loaded once and refreshed whenever
  // the list itself reloads (e.g. right after an upload lands).
  useEffect(() => {
    let cancelled = false;
    api.contractsSummary(scope).then((s) => {
      if (!cancelled) setSummary(s);
    }).catch(() => {
      // The stat row is a convenience; the table still works without it.
    });
    return () => {
      cancelled = true;
    };
  }, [contracts, scope]);

  // Debounce the search box so every keystroke doesn't fire a request.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setQ(qInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [qInput]);

  // The row action menu (⋯) is a click-outside/Escape dismissible popover like
  // every other disclosure in this app (AskDock's Escape handling, the modals
  // below) — without this it stayed open until another toggle was clicked.
  //
  // The menu list itself renders through a portal (see `menuPortalTarget`
  // above), so it is no longer a DOM descendant of `.ws-menu` — the
  // outside-click check has to recognise `.ws-menu__list` explicitly rather
  // than relying on ancestry. And because its position is captured once, in
  // viewport coordinates, at open time, any scroll (the page, or the table's
  // own horizontal scroller) would leave it floating over the wrong row —
  // so a scroll closes it instead of rendering it stale.
  useEffect(() => {
    if (!menuFor) return;
    // Focus lands on the first item, so the menu is operable by the keyboard
    // that opened it. Pointer users never notice: the ring is `:focus-visible`.
    //
    // `preventScroll` is load-bearing, not tidiness. A plain `focus()` asks the
    // browser to bring the element into view, and the scroll EVENT that request
    // produces is dispatched a frame later — by which time the `scroll` listener
    // below is attached, so the menu closed itself the instant it opened
    // (caught by `dashboard-list.spec.ts`, whose second case does not
    // pre-scroll the row). `openMenu` has already placed the menu inside the
    // viewport, flipping it above the toggle when it would not fit, so there is
    // nothing to scroll to in the first place.
    menuRef.current
      ?.querySelector<HTMLElement>("[role='menuitem']")
      ?.focus({ preventScroll: true });
    function onPointerDown(event: MouseEvent) {
      if (!(event.target instanceof Element)
          || !event.target.closest(".ws-menu, .ws-menu__list")) {
        closeMenu();
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu(true);
    }
    function onScroll(event: Event) {
      if (event.target instanceof Element && event.target.closest(".ws-menu__list")) return;
      closeMenu();
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [menuFor]);

  if (!can(P.CONTRACT_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include document access.</p>
      </div>
    );
  }

  const canUpload = can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD);
  const canEdit = can(P.CONTRACT_UPDATE);
  const canArchive = can(P.CONTRACT_ARCHIVE);
  const canTransfer = can(P.CONTRACT_TRANSFER);
  const canSeeDepartment = can(P.DEPARTMENT_VIEW);
  /** Writes are owner-only server-side (AB-12): a Lead reading a colleague's
   *  deal is not offered Edit/Archive on it — Transfer is how they take it on. */
  const isMine = (contract: Contract) => contract.owner_id === identity?.user_id;
  /** A genuinely empty ACCOUNT — the only state that may invite a first upload.
   *
   *  `showArchived` and `scope` belong in this test and were missing until the
   *  2026-09-08 audit measured the consequence: switching "Show:" to Archived
   *  with nothing archived rendered "No contracts yet · Upload your first
   *  contract" plus the whole five-step explainer to an account holding forty
   *  contracts. An empty shelf is not an empty account, and neither is a
   *  department view for someone with no department. */
  const noFilters = !q && !typeFilter && !statusFilter;
  /** Rows are already on screen, so whatever just failed was a REFRESH. */
  const stale = !!contracts && contracts.length > 0;
  const firstRun = contracts !== null && contracts.length === 0 && page === 1
    && noFilters && !showArchived && scope === "own";
  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;

  /** Send the table to one bucket. Every entry point resets the page — landing
   *  on page 3 of a filter you just applied shows an empty table. */
  function filterTo(bucket: DocumentStatusBucket) {
    setStatusFilter(bucket);
    setPage(1);
  }

  /** Every mutation refetches rather than editing local state: the server owns
   *  the row, and an archive or a transfer in particular changes what the
   *  summary counts say. A spliced array would drift from both. */
  async function refresh() {
    closeMenu();
    await load();
  }

  return (
    <>
      <div className="ws-context ws-context--dash">
        <span className="ws-context__icon" aria-hidden="true"><IconFile size={18} /></span>
        <h1>Dashboard</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total contracts</span>
        ) : null}
        {/* The page's primary action, in the page header where the workspace
            already puts its own (`.ws-context__acts`) — 2026-09-08. It used to
            hold a row of its own below the header, which spent ~60px of every
            viewport on one right-aligned button and pushed the table further
            below the fold on exactly the short laptop (1366×768) where only
            five rows were visible to begin with. */}
        {canUpload ? (
          <>
            <span className="ws-context__spacer" />
            <div className="ws-context__acts">
              <button
                type="button"
                className="ws-btn ws-btn--primary"
                aria-expanded={uploadOpen}
                aria-controls="ws-upload-panel"
                onClick={() => setUploadOpen((open) => !open)}
              >
                {uploadOpen ? "Close" : "+ Upload Contract"}
              </button>
            </div>
          </>
        ) : null}
      </div>
      <div className="ws-docs ws-docs--index">
        {/*
          No lede. It read "Upload a contract, confirm its type, and every clause
          is measured against the standard your organization has approved for that
          type…" — which is exactly what the five-step strip below says, in the
          same order and more legibly. Two statements of one fact is one statement
          plus one piece of filler (owner, 2026-09-01).

          The earlier wording also had to be rewritten for `AI-01` and owner Q9
          before it could ship at all; the strip now carries that correctness, and
          `documents-pipeline.test.tsx` guards it there.
        */}

        {/*
          Upload is the page's primary action, so it reads as one — a button,
          not a permanently-open form occupying the fold. The panel below is a
          disclosure, absent from the DOM until asked for, rather than an
          overlay: DESIGN.md reserves modals for a genuine interruption (a
          destructive confirmation, a truly blocking choice), and starting an
          upload is neither.

          `UploadContract` itself is untouched — same state machine, same calls,
          same human-declared type on confirm (owner Q9). Only where it lives
          changed.
        */}
        {uploadOpen ? (
          <section id="ws-upload-panel" className="ws-dash__upload">
            <UploadContract firstRun={!!firstRun} counterparties={knownCounterparties(contracts)} />
          </section>
        ) : null}

        {/* A scope FILTER, not a tablist (2026-09-08). `role="tablist"` promises
            a `tabpanel` for each tab and arrow-key traversal between them — the
            workspace's real tabs (Document/Summary/Findings) provide both, and
            these two never did: they re-query the server and re-render the same
            one region. Two pressed-state buttons in a labelled group say what
            this actually is, and stop assistive technology announcing a tab
            whose panel does not exist. */}
        {canSeeDepartment ? (
          <div className="ws-tabs" role="group" aria-label="Which deals">
            <button type="button" aria-pressed={scope === "own"}
                    className={`ws-tab ${scope === "own" ? "ws-tab--active" : ""}`}
                    onClick={() => { setScope("own"); setPage(1); }}>
              My deals
            </button>
            <button type="button" aria-pressed={scope === "department"}
                    className={`ws-tab ${scope === "department" ? "ws-tab--active" : ""}`}
                    onClick={() => { setScope("department"); setPage(1); }}>
              Department deals{identity?.department ? ` · ${identity.department.name}` : ""}
            </button>
          </div>
        ) : null}
        {canSeeDepartment && scope === "department" && !identity?.department ? (
          <p className="ws-pane__note" role="note">
            Your account is not in a department yet, so this view is empty until an administrator places you in one.
          </p>
        ) : null}

        {summary ? (
          <section className="ws-doctiles" aria-label="Contract totals">
            <StatTile icon={<IconFile size={16} />} n={summary.total} label="Total Contracts" />
            {/* The one tile with somewhere to go: it names a queue the table can
                actually show. The other three describe states nobody navigates
                to on purpose, and a link that resolves to a shrug is worse than
                no link. */}
            <StatTile
              icon={<IconAlertCircle size={16} />}
              n={summary.needs_attention}
              label="Needs Attention"
              bucket="needs_attention"
              {...(summary.needs_attention > 0
                ? { onSelect: () => filterTo("needs_attention") } : {})}
            />
            <StatTile icon={<IconCheckCircle size={16} />} n={summary.analyzed} label="Analyzed" bucket="analyzed" />
            <StatTile icon={<IconClock size={16} />} n={summary.draft + summary.analyzing} label="Draft / In Progress" bucket="draft" />
          </section>
        ) : null}

        {/*
          No separate "Needs Attention" list here any more (2026-09-02
          redesign — previously `.ws-doctend`/`.ws-queue`, a whole card of its
          own above the table). The row that needs attention is now flagged
          IN the table itself (a soft amber row, see `ws-tr--attention`
          below), which is where the owner asked for the cue to live instead.

          That still leaves the cross-page/cross-filter question the old
          section existed to answer: a contract needing attention that is not
          on the page or filter you're currently looking at. Two things below
          still cover it without a dedicated section: the "Needs Attention"
          stat tile is a real link into `status=needs_attention` account-wide
          (see `filterTo`), and the same value is one option in the Status
          filter. Nothing that was reachable before is unreachable now.
        */}

        {/* Two different failures, and they were telling the same story
            (2026-09-08 audit measured "Documents could not be loaded" sitting
            above twenty-five perfectly good rows). If rows are already on
            screen, the request that failed was a REFRESH: the table is real,
            just not current, and saying otherwise teaches the reader to
            distrust a correct table. With no rows to show, the original
            message is the right one. */}
        {error ? (
          <div className={`ws-state ws-state--${stale ? "warn" : "error"}`} role="alert">
            <h2>
              {stale ? "These results could not be refreshed."
                : "Documents could not be loaded."}
            </h2>
            <p>
              {describeError(error)}
              {stale ? " The rows below are the last ones loaded successfully." : ""}
            </p>
            <button type="button" className="ws-btn ws-btn--sm" onClick={() => void load()}>
              Try again
            </button>
          </div>
        ) : null}

        {/*
          One card holds the toolbar, the table and the footer — the reference's
          shape, and the right one: the column header stays visible when there
          are no rows, so an empty table still says what it will hold instead of
          collapsing into an unrelated-looking panel.
        */}
        <div className="ws-doctable">
        <div className="ws-doctoolbar">
          <label className="ws-doctoolbar__search">
            <IconSearch size={14} />
            <span className="ws-visually-hidden">Search contracts</span>
            <input
              value={qInput}
              onChange={(event) => setQInput(event.target.value)}
              placeholder="Search contracts…"
            />
          </label>
          <label className="ws-doctoolbar__select">
            <span className="ws-visually-hidden">Filter by type</span>
            <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(1); }}>
              <option value="">Type: All</option>
              {DOCUMENT_TYPES.map((t) => (
                <option key={t.code} value={t.code}>{t.label}</option>
              ))}
            </select>
          </label>
          <label className="ws-doctoolbar__select">
            <span className="ws-visually-hidden">Filter by status</span>
            <select
              value={statusFilter}
              onChange={(event) => { setStatusFilter(event.target.value as DocumentStatusBucket | ""); setPage(1); }}
            >
              <option value="">Status: All</option>
              {(["needs_attention", "analyzed", "analyzing", "draft"] as const).map((b) => (
                <option key={b} value={b}>{STATUS_BUCKET_LABEL[b]}</option>
              ))}
            </select>
          </label>
          <label className="ws-doctoolbar__select">
            <span className="ws-visually-hidden">Active or archived</span>
            <select value={showArchived ? "archived" : "active"}
                    onChange={(event) => { setShowArchived(event.target.value === "archived"); setPage(1); }}>
              <option value="active">Show: Active</option>
              <option value="archived">Show: Archived</option>
            </select>
          </label>
          <label className="ws-doctoolbar__select">
            <span className="ws-visually-hidden">Sort</span>
            <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }}>
              <option value="created_desc">Sort: Recently Added</option>
              <option value="created_asc">Sort: Oldest First</option>
              <option value="name_asc">Sort: Name A–Z</option>
              <option value="name_desc">Sort: Name Z–A</option>
            </select>
          </label>
        </div>

        {contracts === null && !error ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading documents…
            </p>
            {/* The column header is part of the loading state, not something
                that appears afterwards (2026-09-08): rendering the skeleton
                without it moved every row down by the header's height the
                instant data landed — a layout shift on the page's first paint,
                every visit. Six skeleton rows also hold roughly the height a
                full page of results occupies, so the card does not jump size. */}
            <table aria-hidden="true"><thead><TableHead /></thead></table>
            {[0, 1, 2, 3, 4, 5].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "40%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "12%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "10%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {contracts ? (
          <div className="ws-docs__table">
            <table>
              <thead><TableHead /></thead>
              <tbody>
                {contracts.map((contract) => {
                  const bucket = documentStatusBucket(contract);
                  // One word, used as both the visible label and the head of the
                  // accessible name — written twice, they drifted immediately.
                  const verb = contract.archived_at ? "View"
                    : bucket === "draft" ? "Analyze"
                    : bucket === "analyzing" ? "View Progress" : "Review";
                  return (
                    <tr key={contract.id} className={bucket === "needs_attention" ? "ws-tr--attention" : undefined}>
                      <td>
                        {/* `title` carries the untruncated name: the cell clips
                            to one line so rows stay a uniform height, and the
                            full value must still be reachable by pointer and by
                            keyboard focus. */}
                        <Link
                          href={`/dashboard?id=${contract.id}`}
                          className="ws-doc-name"
                          title={contract.name}
                        >
                          <IconFile size={15} />
                          <span className="ws-doc-name__text">{contract.name}</span>
                        </Link>
                        {scope === "department" && contract.owner_name ? (
                          <div className="ws-pane__note">{contract.owner_name}</div>
                        ) : null}
                        {contract.archived_at ? (
                          <div className="ws-pane__note">Archived {contract.archived_at.slice(0, 10)}</div>
                        ) : null}
                      </td>
                      {/* `data-label` is what the narrow-viewport card layout
                          renders as each value's own label (see `ws-docs--index`
                          under 900px in workspace.css). Below that width the
                          seven-column row cannot hold its columns — measured
                          777px of table inside a 320px viewport, which put the
                          row's own "Review" link and ⋯ menu at x=657–778, off
                          screen behind a nested scroller nobody discovers. The
                          same cells, labelled, stack into a card instead: every
                          value still present, every control reachable. */}
                      <td data-label="Type">
                        {contract.contract_type ? (
                          <span className="ws-chip ws-chip--type" title={documentTypeLabel(contract.contract_type)}>
                            {contract.contract_type}
                          </span>
                        ) : (
                          <span className="ws-chip">not declared</span>
                        )}
                      </td>
                      <td data-label="Status"><StatusPill contract={contract} /></td>
                      <td data-label="Findings"><FindingsCell contract={contract} /></td>
                      <td className="ws-mono" data-label="Last analyzed">
                        {bucket === "analyzing" ? "In progress"
                          : relativeTime(contract.latest_analysis?.completed_at ?? null)}
                      </td>
                      <td className="ws-mono" data-label="Added">{contract.created_at ? contract.created_at.slice(0, 10) : "—"}</td>
                      <td>
                        <div className="ws-rowact">
                          {/* A per-row action reads better as a link than a
                              repeated solid button (2026-09-02) — the page's
                              one true `.btn--primary` stays "+ Upload
                              Contract" in the header above. */}
                          {/* The visible word stays short; the ACCESSIBLE name
                              carries the contract (2026-09-08). Twenty-five
                              links all announcing "Review, link" gave a screen
                              reader no way to tell one row's action from
                              another's — the same reason the ⋯ toggle already
                              names its contract.

                              An archived contract reads "View": it is
                              read-only server-side (AB-12 r6), so offering
                              "Analyze" on it advertised an operation the
                              server refuses. */}
                          <Link
                            href={`/dashboard?id=${contract.id}`}
                            className="ws-btn ws-btn--sm ws-btn--link"
                            aria-label={`${verb} ${contract.name}`}
                          >
                            {verb}
                            <IconChevronRight size={13} aria-hidden="true" />
                          </Link>
                          {/* Only the operations this caller actually has. An
                              action shown-but-disabled advertises a capability
                              the account does not carry; hiding it says the
                              truth. The server re-checks regardless — this
                              gating is presentation only (47.6). */}
                          {(canEdit && isMine(contract)) || (canArchive && isMine(contract)) || canTransfer ? (
                            // canArchive also gates Delete below (AM-55): the
                            // same owner-scoped write capability covers both.
                            <div className="ws-menu">
                              <button
                                type="button"
                                className="ws-btn ws-btn--sm ws-menu__toggle"
                                aria-haspopup="menu"
                                aria-expanded={menuFor === contract.id}
                                aria-label={`More actions for ${contract.name}`}
                                onClick={(event) => menuFor === contract.id
                                  ? closeMenu()
                                  : openMenu(contract.id, event.currentTarget)}
                              >
                                ⋯
                              </button>
                              {menuFor === contract.id && menuPos
                                ? createPortal(
                                  <div
                                    ref={menuRef}
                                    className="ws-menu__list"
                                    role="menu"
                                    aria-orientation="vertical"
                                    onKeyDown={onMenuKeyDown}
                                    style={{
                                      position: "fixed",
                                      right: menuPos.right,
                                      top: menuPos.top,
                                      bottom: menuPos.bottom,
                                      minWidth: menuPos.minWidth,
                                    }}
                                  >
                                    {canEdit && isMine(contract) && !contract.archived_at ? (
                                      <button type="button" role="menuitem"
                                              className="ws-menu__item"
                                              onClick={() => {
                                                closeMenu();
                                                setEditing(contract);
                                              }}>
                                        Edit details
                                      </button>
                                    ) : null}
                                    {canTransfer && !contract.archived_at ? (
                                      <button type="button" role="menuitem"
                                              className="ws-menu__item"
                                              onClick={() => {
                                                closeMenu();
                                                setTransferring(contract);
                                              }}>
                                        Transfer ownership
                                      </button>
                                    ) : null}
                                    {canArchive && isMine(contract) && !contract.archived_at ? (
                                      <button type="button" role="menuitem"
                                              className="ws-menu__item ws-menu__item--bad"
                                              onClick={() => {
                                                closeMenu();
                                                setArchiving(contract);
                                              }}>
                                        Archive
                                      </button>
                                    ) : null}
                                    {canArchive && isMine(contract) && contract.archived_at ? (
                                      <button type="button" role="menuitem"
                                              className="ws-menu__item"
                                              onClick={() => {
                                                closeMenu();
                                                void api.restoreContract(contract.id).then(refresh).catch(setError);
                                              }}>
                                        Restore
                                      </button>
                                    ) : null}
                                    {canArchive && isMine(contract) ? (
                                      <button type="button" role="menuitem"
                                              className="ws-menu__item ws-menu__item--bad"
                                              onClick={() => {
                                                closeMenu();
                                                setDeleting(contract);
                                              }}>
                                        Delete permanently
                                      </button>
                                    ) : null}
                                  </div>,
                                  menuPortalTarget(),
                                )
                                : null}
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/*
              Two different emptinesses, and they need different answers. Nothing
              uploaded yet is an invitation; nothing matching a filter is a dead
              end the reader can back out of. Conflating them would leave someone
              staring at "upload your first contract" while holding twenty.
            */}
            {contracts.length === 0 ? (
              firstRun ? (
                <div className="ws-docempty">
                  <span className="ws-docempty__mark" aria-hidden="true">
                    <IconFile size={22} />
                  </span>
                  {/* No body copy: the heading states the condition, the button
                      states the action. A sentence between them restates both. */}
                  <h2>No contracts yet</h2>
                  {canUpload ? (
                    <button
                      type="button"
                      className="ws-btn ws-btn--primary"
                      onClick={() => setUploadOpen(true)}
                    >
                      Upload your first contract
                    </button>
                  ) : null}
                </div>
              ) : noFilters ? (
                /* An empty VIEW, not an empty account (2026-09-08): the shelf
                   holds nothing, or this department's members own nothing yet.
                   Either way the reader has contracts, so neither the first-run
                   invitation nor a "clear your filters" dead end is true. */
                <div className="ws-docempty">
                  <span className="ws-docempty__mark" aria-hidden="true">
                    <IconFile size={22} />
                  </span>
                  <h2>{showArchived ? "Nothing archived" : "No deals in this view yet"}</h2>
                  <p>
                    {showArchived
                      ? "A contract you archive is kept here — read-only, with its versions, findings and history — and can be restored at any time."
                      : "Deals owned by the other people in your department appear here as they are added."}
                  </p>
                  {showArchived ? (
                    <button
                      type="button"
                      className="ws-btn"
                      onClick={() => { setShowArchived(false); setPage(1); }}
                    >
                      Back to active contracts
                    </button>
                  ) : null}
                </div>
              ) : (
                <div className="ws-docempty">
                  <span className="ws-docempty__mark" aria-hidden="true">
                    <IconSearch size={22} />
                  </span>
                  <h2>No contracts match this search</h2>
                  <button
                    type="button"
                    className="ws-btn"
                    onClick={() => {
                      setQInput("");
                      setTypeFilter("");
                      setStatusFilter("");
                      setPage(1);
                    }}
                  >
                    Clear search and filters
                  </button>
                </div>
              )
            ) : null}
          </div>
        ) : null}

        {/*
          The formats are already stated on the upload card; only the ceiling is
          new information, so only the ceiling is here.

          "How analysis works" is gone rather than shortened: it pointed at
          `?guide=1`, which renders nothing. A control that does not work
          misrepresents the product — the same reason the login screen carries no
          "forgot password".
        */}
        <div className="ws-doctable__foot">
          <span>Maximum file size 25&nbsp;MB</span>
        </div>
        </div>

        {pagination && pagination.total > 0 ? (
          <nav className="ws-pager" aria-label="Pagination">
            {/* Announced (2026-09-08): paging is a keyboard-and-screen-reader
                operation whose only feedback was the table's own contents
                changing silently below the fold. */}
            <span className="ws-pane__note" role="status" aria-live="polite">
              Showing {pagination.total === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1}
              {" "}to {Math.min(pagination.page * pagination.page_size, pagination.total)} of {pagination.total} contracts
            </span>
            <span className="ws-pager__spacer" />
            <button type="button" className="ws-btn ws-btn--sm" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            {Array.from({ length: pageCount }, (_, i) => i + 1)
              .filter((n) => n === 1 || n === pageCount || Math.abs(n - pagination.page) <= 1)
              .reduce<number[]>((acc, n) => {
                if (acc.length > 0 && n - acc[acc.length - 1]! > 1) acc.push(-1);
                acc.push(n);
                return acc;
              }, [])
              .map((n, i) => (n === -1 ? (
                <span key={`gap-${i}`} className="ws-pane__note">…</span>
              ) : (
                <button
                  key={n}
                  type="button"
                  className="ws-btn ws-btn--sm"
                  aria-current={n === pagination.page ? "page" : undefined}
                  onClick={() => setPage(n)}
                >
                  {n}
                </button>
              )))}
            <button
              type="button"
              className="ws-btn ws-btn--sm"
              disabled={pagination.page * pagination.page_size >= pagination.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        ) : null}

        {/*
          The five-step explainer, for the one reader it is for.

          It used to render on every visit. It says the same five words every
          time and never reflects the state of anything, so for someone who has
          already uploaded a contract it is a permanent block of the fold
          spent restating what they just did. On an empty account it is
          orientation. `Pipeline` itself is unchanged — only when the page asks
          for it changed.
        */}
        {firstRun ? <Pipeline /> : null}
      </div>

      {editing ? (
        <EditContractDialog
          contract={editing}
          counterparties={knownCounterparties(contracts)}
          companies={companies}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); void refresh(); }}
        />
      ) : null}

      {archiving ? (
        <ArchiveContractDialog
          contract={archiving}
          onClose={() => setArchiving(null)}
          onArchived={() => { setArchiving(null); void refresh(); }}
        />
      ) : null}
      {deleting ? (
        <DeleteContractDialog
          contract={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => { setDeleting(null); void refresh(); }}
        />
      ) : null}
      {transferring ? (
        <TransferContractDialog
          contract={transferring}
          onClose={() => setTransferring(null)}
          onTransferred={() => { setTransferring(null); void refresh(); }}
        />
      ) : null}
    </>
  );
}

/**
 * Rename a contract, or correct its declared type.
 *
 * Both write through `api.updateContract` — the same PATCH the intake confirm
 * has always used. Nothing new is being decided here: the type stays
 * human-declared (owner Q9), and this is simply the second chance to declare it
 * that the product previously lacked. A contract typed wrongly at upload was,
 * until now, typed wrongly forever, and the declared type is what selects the
 * Company Standard the contract is measured against.
 */
function EditContractDialog({
  contract, counterparties, companies, onClose, onSaved,
}: {
  contract: Contract; counterparties: string[]; companies: Counterparty[];
  onClose: () => void; onSaved: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [name, setName] = useState(contract.name);
  const [type, setType] = useState(contract.contract_type ?? "");
  // P-1 (2026-09-06): Step 2's Draft / Active / Superseded, declared here and
  // nowhere else — never inferred from a date or a version.
  const [status, setStatus] = useState(contract.status);
  // AB-13 r2 — who this deal is WITH. "" is unlinked; NEW opens a name field.
  // This is the identity; the per-version free text below stays the frozen
  // declaration (r7) and the two answer different questions.
  const [companyId, setCompanyId] = useState(contract.counterparty_id ?? "");
  const [newCompany, setNewCompany] = useState("");
  // The latest version's declared facts (2026-09-06). `frozen` is PRESENTATION
  // only (rule 18): the server refuses the write once a Review exists whatever
  // the client shows; disabling the fields just says so before the attempt.
  const latest = contract.latest_version ?? null;
  const frozen = !!contract.latest_analysis;
  const [source, setSource] = useState(latest?.source ?? "");
  const [counterparty, setCounterparty] = useState(latest?.counterparty ?? "");
  const [effectiveDate, setEffectiveDate] = useState(latest?.effective_date ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, []);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // A brand-new company is created first, then linked in the same save —
      // one gesture for the reader, two calls because identity must exist
      // before anything can point at it.
      let linkId: string | null | undefined;
      if (companyId === "NEW" && newCompany.trim()) {
        linkId = (await api.createCounterparty({ name: newCompany.trim() })).id;
      } else if (companyId !== "NEW") {
        linkId = companyId || null;
      }
      const typeChanged = (type || null) !== (contract.contract_type ?? null);
      await api.updateContract(contract.id, {
        name: name.trim(),
        contract_type: type || null,
        ...(status !== contract.status ? { status } : {}),
        ...(linkId !== undefined && linkId !== (contract.counterparty_id ?? null)
          ? { counterparty_id: linkId }
          : {}),
      });
      // Only what changed, and only while the server will take it. A field
      // emptied by the reader is sent as null so it is cleared, not kept.
      if (latest && !frozen) {
        const declared: Record<string, string | null> = {};
        if ((latest.source ?? "") !== source) declared.source = source || null;
        if ((latest.counterparty ?? "") !== counterparty.trim()) {
          declared.counterparty = counterparty.trim() || null;
        }
        if ((latest.effective_date ?? "") !== effectiveDate) {
          declared.effective_date = effectiveDate || null;
        }
        if (Object.keys(declared).length > 0) await api.declareVersion(latest.id, declared);
      }
      // A newly declared type is the human act analysis was waiting for (AM-50):
      // run it now, best-effort, rather than telling the reader it will not.
      if (typeChanged && type) await chainAnalysis(contract.id, true);
      onSaved();
    } catch (cause) {
      setError(cause);
      setSaving(false);
    }
  }

  /* No scrim-click dismissal on THIS dialog (2026-09-08), unlike the two
     confirmations below. It is a form: a stray click beside it discarded a
     half-typed name, a corrected document type and three declared version
     facts with no warning and no undo. Escape and Cancel are both still here,
     and both are deliberate gestures. */
  return (
    <div className="ws-modal">
      <div ref={dialogRef} className="ws-modal__box" role="dialog" aria-modal="true"
           aria-labelledby="ws-edit-title" tabIndex={-1}
           onKeyDown={(e) => {
             if (e.key === "Escape") onClose();
             e.stopPropagation();
           }}>
        <h2 id="ws-edit-title">Edit contract details</h2>
        <form onSubmit={save}>
          <label className="ws-field">
            <span className="ws-field__label">Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="ws-field">
            <span className="ws-field__label">Document type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">Not declared</option>
              {DOCUMENT_TYPES.map((t) => (
                <option key={t.code} value={t.code}>{t.label} ({t.code})</option>
              ))}
            </select>
            <span className="ws-field__help">
              The type selects which approved standard this contract is measured
              against. Changing it runs a fresh analysis; earlier ones stay on record.
            </span>
          </label>
          <label className="ws-field">
            <span className="ws-field__label">Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {CONTRACT_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <span className="ws-field__help">
              Where this contract stands — being negotiated, in force, or replaced.
              Declared by you; recorded on the audit trail.
            </span>
          </label>
          <label className="ws-field">
            <span className="ws-field__label">Company (counterparty)</span>
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Not linked</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
              <option value="NEW">+ Add a new company…</option>
            </select>
            {companyId === "NEW" ? (
              <input
                aria-label="New company name"
                placeholder="Company name"
                maxLength={500}
                value={newCompany}
                onChange={(e) => setNewCompany(e.target.value)}
              />
            ) : null}
            <span className="ws-field__help">
              Linking a deal to a company is what groups its documents together —
              the NDA, the MSA and their revisions in one place.
            </span>
          </label>
          {latest ? (
            <>
              <label className="ws-field">
                <span className="ws-field__label">Source</span>
                <select value={source} disabled={frozen}
                        onChange={(e) => setSource(e.target.value)}>
                  <option value="">Not declared</option>
                  {DOCUMENT_SOURCES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label className="ws-field">
                <span className="ws-field__label">Counterparty</span>
                <input list="ws-counterparties-edit" maxLength={500} value={counterparty}
                       disabled={frozen} onChange={(e) => setCounterparty(e.target.value)} />
                <datalist id="ws-counterparties-edit">
                  {counterparties.map((known) => <option key={known} value={known} />)}
                </datalist>
              </label>
              <label className="ws-field">
                <span className="ws-field__label">Effective date</span>
                <input type="date" value={effectiveDate} disabled={frozen}
                       onChange={(e) => setEffectiveDate(e.target.value)} />
                <span className="ws-field__help">
                  {frozen
                    ? <>These describe version {latest.version_number}, which has been
                        analysed, so they are fixed. Upload a new version to change them.</>
                    : <>These describe version {latest.version_number}. Declared by you,
                        never read from the document.</>}
                </span>
              </label>
            </>
          ) : null}
          {error ? (
            <p className="ws-field__error" role="alert">{describeError(error)}</p>
          ) : null}
          <div className="ws-modal__acts">
            <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="ws-btn ws-btn--primary"
                    disabled={saving || !name.trim()}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Archive confirmation — the one modal shape DESIGN.md names outright, because
 * taking a deal off the working list is a genuine interruption.
 *
 * One message, always true (AB-12 r6): nothing is destroyed. The document, its
 * versions, findings and audit trail stay; the contract becomes read-only and
 * leaves the active list, and can be restored. There is no branch on whether
 * the contract was analysed, because the server no longer has one either.
 */
function ArchiveContractDialog({
  contract, onClose, onArchived,
}: { contract: Contract; onClose: () => void; onArchived: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, []);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.archiveContract(contract.id);
      onArchived();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <div className="ws-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div ref={dialogRef} className="ws-modal__box" role="dialog" aria-modal="true"
           aria-labelledby="ws-arc-title" tabIndex={-1}
           onKeyDown={(e) => {
             if (e.key === "Escape") onClose();
             e.stopPropagation();
           }}>
        <h2 id="ws-arc-title">Archive this contract?</h2>
        <p className="ws-modal__body">
          <strong>{contract.name}</strong>
        </p>
        <p className="ws-modal__body">
          It leaves your active deals and becomes read-only. The document, every version, the findings and
          the history are kept, and you can restore it from the archived view at any time.
        </p>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ws-btn ws-btn--bad"
                  disabled={busy} onClick={() => void confirm()}>
            {busy ? "Archiving…" : "Archive"}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Delete confirmation — AM-55. Same modal shape as Archive, deliberately: the
 * interruption is the same weight, the consequence is not. Unlike Archive,
 * this destroys the document, every version, its Reviews, Findings,
 * Evaluations and Legal Decisions, with no restore surface.
 */
function DeleteContractDialog({
  contract, onClose, onDeleted,
}: { contract: Contract; onClose: () => void; onDeleted: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, []);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteContract(contract.id);
      onDeleted();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <div className="ws-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div ref={dialogRef} className="ws-modal__box" role="dialog" aria-modal="true"
           aria-labelledby="ws-del-title" tabIndex={-1}
           onKeyDown={(e) => {
             if (e.key === "Escape") onClose();
             e.stopPropagation();
           }}>
        <h2 id="ws-del-title">Delete this contract permanently?</h2>
        <p className="ws-modal__body">
          <strong>{contract.name}</strong>
        </p>
        <p className="ws-modal__body">
          This cannot be undone. The document, every version, and any findings, evaluations and
          legal decisions on it are destroyed. If you may want this back, archive it instead.
        </p>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ws-btn ws-btn--bad"
                  disabled={busy} onClick={() => void confirm()}>
            {busy ? "Deleting…" : "Delete permanently"}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Ownership transfer — AB-12 r5. The Department Lead's coverage tool: a deal
 * moves to a colleague in the same department, with a reason the audit trail
 * keeps. The server decides who is eligible (`/departments/mine/members`) and
 * enforces the boundary again on submit; this dialog only collects the choice.
 */
function TransferContractDialog({
  contract, onClose, onTransferred,
}: { contract: Contract; onClose: () => void; onTransferred: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [members, setMembers] = useState<DepartmentMembers | null>(null);
  const [newOwnerId, setNewOwnerId] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, []);

  useEffect(() => {
    api.departmentMembers().then(setMembers).catch(setError);
  }, []);

  const eligible = (members?.members ?? []).filter((m) => m.id !== contract.owner_id);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.transferContract(contract.id, newOwnerId, reason.trim());
      onTransferred();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <div className="ws-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div ref={dialogRef} className="ws-modal__box" role="dialog" aria-modal="true"
           aria-labelledby="ws-xfer-title" tabIndex={-1}
           onKeyDown={(e) => {
             if (e.key === "Escape") onClose();
             e.stopPropagation();
           }}>
        <h2 id="ws-xfer-title">Transfer this contract?</h2>
        <p className="ws-modal__body">
          <strong>{contract.name}</strong>
          {contract.owner_name ? <> — currently with {contract.owner_name}</> : null}
        </p>
        <p className="ws-modal__body">
          The new owner takes over the document, its versions, findings and history. Private questions the
          previous owner asked stay theirs.
        </p>
        {members && members.department === null ? (
          <p className="ws-field__error" role="alert">
            Your account is not in a department, so there is nobody to transfer to.
          </p>
        ) : null}
        {/* A department of one (2026-09-08). Without this the reader got a
            select holding nothing but its own placeholder and a permanently
            disabled Transfer button, with no statement of why. */}
        {members && members.department !== null && eligible.length === 0 ? (
          <p className="ws-field__error" role="alert">
            You are the only member of {members.department.name}, so there is nobody
            to transfer this to yet.
          </p>
        ) : null}
        <label className="ws-field">
          <span className="ws-field__label">New owner</span>
          <select value={newOwnerId} onChange={(e) => setNewOwnerId(e.target.value)}
                  disabled={busy || !members}>
            <option value="">Choose a colleague…</option>
            {eligible.map((m) => (
              <option key={m.id} value={m.id}>{m.name} ({m.email})</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Reason <span className="ws-field__req">(required)</span></span>
          <input value={reason} onChange={(e) => setReason(e.target.value)}
                 placeholder="e.g. Aman is on leave for two weeks" disabled={busy} />
        </label>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ws-btn ws-btn--primary"
                  disabled={busy || !newOwnerId || !reason.trim()} onClick={() => void confirm()}>
            {busy ? "Transferring…" : "Transfer"}
          </button>
        </div>
      </div>
    </div>
  );
}

function WorkspacePageInner() {
  const contractId = useSearchParams().get("id");
  return contractId ? (
    <WorkspacePage key={contractId} contractId={contractId} />
  ) : (
    <DocumentsListView />
  );
}

export default function WorkspaceRoute() {
  return (
    <Suspense fallback={null}>
      <WorkspacePageInner />
    </Suspense>
  );
}

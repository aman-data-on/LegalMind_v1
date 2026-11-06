"use client";

/**
 * Contracts home — the person's home and the list of their contracts.
 *
 * Critic round (2026-11-03): whose contracts (H1) and the one primary action; then what is
 * THIS person's turn (`HomeQueue`, from the server's To-do and stage); then the list. The
 * list's only status vocabulary is the deal stage (`AM-260`); each row shows one count in
 * words — points that differ from our standard — never four unlabelled numbers. For the
 * lawyer the queue is the page and the list sits behind "All contracts".
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { api, describeError, type ContractScope } from "@/lib/api";
import { DOCUMENT_SOURCES, DOCUMENT_TYPES } from "@/lib/documentTypes";
import { ACTION, CONTRACT_STATUSES, changesWords, contractDisplayName, pointsWords, reviewStatusLabel, type StageViewer } from "@/lib/labels";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type {
  Contract, ContractsSummary, Counterparty, DepartmentMembers, NegotiationStageCode, Pagination,
} from "@/lib/types";

import { STAGE_LABEL, STAGE_ORDER, StageBadge } from "@/components/workspace/StageBadge";
import {
  contractFacts,
  contractHref,
  documentStatusBucket,
  homeTitle,
  knownCounterparties,
  personaFor,
  shortDate,
  stageViewer,
  UNFINISHED_REVIEW_STATUSES,
} from "@/components/workspace/model";
import { Dialog } from "@/components/Dialog";
import { UploadContractDialog } from "@/components/workspace/UploadContractDialog";
import { NewContractChooser } from "@/components/newcontract/NewContractChooser";
import { HomeQueue } from "@/components/workspace/TodoViews";
import { PageHeader } from "@/components/page/PageHeader";
import { nextStep } from "@/lib/nextStep";
import { IconPlus, IconSearch } from "@/components/workspace/icons";

const PAGE_SIZE = 25;

/** The one count a row shows, in words (critic round, 2026-11-03): how many points differ
 *  from our standard, from the server's folded counts — or why there is no count yet.
 *  Replaces four unlabelled coloured numbers and a second status vocabulary. */
/** The two nouns on a row (`AM-291`), from the server's `counts` only: the client's
 *  changes in the open round, and the points still open. Before an analysis has
 *  finished the review's own word stands in for the points. */
function CountsCell({ contract, viewer }: { contract: Contract; viewer: StageViewer }) {
  const review = contract.latest_analysis?.review_status;
  const changes = changesWords(contract.counts, viewer);
  let points: React.ReactNode = pointsWords(contract.counts, viewer);
  if (review && UNFINISHED_REVIEW_STATUSES.has(review)) points = reviewStatusLabel(review);
  else if (documentStatusBucket(contract) === "analyzing") points = <span className="ws-home__quiet">Being read</span>;
  else if (points === null) points = <span className="ws-home__quiet">Not checked yet</span>;
  return (
    <span className="ws-home__counts">
      {changes ? <span>{changes}</span> : null}
      <span>{points}</span>
    </span>
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
  /** Types seen on this person's contracts — the type filter offers only these.
   *  ponytail: grows as pages load; a server facet if a type on an unseen page matters. */
  const [seenTypes, setSeenTypes] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState("created_desc");
  /** `AM-260` — one negotiation stage, filtered server-side (`?stage=`). The stage is the
   *  list's only status vocabulary. */
  const [stageFilter, setStageFilter] = useState<NegotiationStageCode | "">("");
  const persona = personaFor(can);
  // S1: a Lead's home is the team's contracts; "My deals" stays one press away (AB-12 r3)
  const [scope, setScope] = useState<ContractScope>(
    persona === "lead" ? "department" : persona === "legal" ? "legal" : "own");
  /** AB-12 r6 — the shelf, kept apart from the working list. */
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [chooseOpen, setChooseOpen] = useState(false);
  /** The row whose ⋯ menu is open. It renders through a portal into `.ws` (every token is
   *  scoped there) at fixed viewport coordinates, so no clipping ancestor cuts it off. */
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
  /** The open menu's node and its toggle — the menu moves focus in itself and hands it
   *  back on close (WAI-ARIA menu button). */
  const menuRef = useRef<HTMLDivElement | null>(null);
  /** The Filter disclosure — closed by a press outside it or Escape, like any popover. */
  const filterRef = useRef<HTMLDetailsElement | null>(null);
  const menuToggleRef = useRef<HTMLElement | null>(null);
  /** Which list request is the current one: only the newest may write the table. */
  const loadSeq = useRef(0);

  function closeMenu(restoreFocus = false) {
    setMenuFor(null);
    setMenuPos(null);
    if (restoreFocus) menuToggleRef.current?.focus();
  }

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

  function menuPortalTarget(): Element {
    return document.querySelector(".ws") ?? document.body;
  }

  /** Opens below the toggle, or above it near the viewport's bottom; never narrower than
   *  the row's own action cell, so the row below never peeks out from under it. */
  function openMenu(id: string, toggle: HTMLElement) {
    menuToggleRef.current = toggle;
    const rect = toggle.getBoundingClientRect();
    const cellRect = toggle.closest("td")?.getBoundingClientRect() ?? rect;
    const estimatedHeight = 176; // up to four items plus padding
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
    const seq = loadSeq.current + 1;
    loadSeq.current = seq;
    const current = () => seq === loadSeq.current;
    setError(null);
    try {
      const result = await api.contracts(page, PAGE_SIZE, {
        q: q || undefined,
        contract_type: typeFilter || undefined,
        sort,
        scope,
        archived: showArchived || undefined,
        stage: stageFilter || undefined,
      });
      if (!current()) return;
      setContracts(result.items);
      setPagination({ page, page_size: PAGE_SIZE, total: result.pagination.total });
      setSeenTypes((seen) => {
        const fresh = result.items.map((c) => c.contract_type).filter((t): t is string => !!t && !seen.has(t));
        return fresh.length ? new Set([...seen, ...fresh]) : seen;
      });
      // The companies this caller deals with — names the client on each row and feeds the
      // edit dialog's picker. Best-effort: the list works without it.
      try {
        const companyList = await api.counterparties();
        if (current()) setCompanies(companyList);
      } catch {
        if (current()) setCompanies([]);
      }
    } catch (cause) {
      // A superseded request's failure is not this view's failure.
      if (current()) setError(cause);
    }
  }, [page, q, typeFilter, stageFilter, sort, scope, showArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  // The stage counts are scope-wide, not page-wide; refreshed whenever the list reloads.
  useEffect(() => {
    let cancelled = false;
    api.contractsSummary(scope).then((s) => {
      if (!cancelled) setSummary(s);
    }).catch(() => {
      // The chips are a convenience; the table still works without them.
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

  // The ⋯ menu closes on an outside press, Escape, or any scroll (its position is fixed at
  // open time). Focus lands on its first item with `preventScroll` — a plain focus()
  // scrolls, and that scroll would close the menu the instant it opened; the listeners
  // attach a frame late for the same reason.
  useEffect(() => {
    if (!menuFor) return;
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
    const raf = requestAnimationFrame(() => {
      document.addEventListener("mousedown", onPointerDown);
      document.addEventListener("keydown", onKey);
      document.addEventListener("scroll", onScroll, true);
    });
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [menuFor]);

  useEffect(() => {
    function close(event: Event) {
      const box = filterRef.current;
      if (!box?.open) return;
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !box.contains(event.target as Node)) {
        box.open = false;
      }
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);

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
  /** Writes are owner-only server-side (AB-12): a Lead reading a colleague's deal is not
   *  offered Edit/Archive on it — Transfer is how they take it on. */
  const isMine = (contract: Contract) => contract.owner_id === identity?.user_id;
  const clientOf = (contract: Contract) =>
    companies.find((co) => co.id === contract.counterparty_id)?.name;
  /** A genuinely empty ACCOUNT — the only state that may invite a first upload. An empty
   *  shelf, a filter or a department view is not an empty account (2026-09-08). */
  const noFilters = !q && !typeFilter && !stageFilter;
  /** Rows are already on screen, so whatever just failed was a REFRESH. */
  const stale = !!contracts && contracts.length > 0;
  const firstRun = contracts !== null && contracts.length === 0 && page === 1
    && noFilters && !showArchived && (scope !== "department" || persona === "lead");
  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;
  /** Stages that hold a deal this reader can see — an all-zero row of chips said nothing. */
  const stagesHeld = STAGE_ORDER.filter((code) => (summary?.stages?.[code] ?? 0) > 0 || code === stageFilter);
  const activeFilters = (typeFilter ? 1 : 0) + (showArchived ? 1 : 0) + (sort !== "created_desc" ? 1 : 0);

  function clearFilters() {
    setQInput(""); setQ(""); setTypeFilter(""); setStageFilter(""); setPage(1);
  }

  /** Every mutation refetches: the server owns the row. */
  async function refresh() {
    closeMenu();
    await load();
  }

  const list = (
    <>
      {/* nothing to search or filter on an empty account */}
      {firstRun ? null : <div className="ws-home__tools">
        <label className="ws-home__search">
          <IconSearch size={14} />
          <span className="ws-visually-hidden">Search contracts</span>
          <input type="search" value={qInput} onChange={(event) => setQInput(event.target.value)}
                 placeholder="Search by contract name" />
        </label>
        {/* One Filter button: type, the archive shelf and the order, folded away inline
            (not floating — nothing to position, nothing to clip on a phone). */}
        <details className="ws-home__filter" ref={filterRef}>
          <summary className="ws-btn">Filter{activeFilters ? ` · ${activeFilters}` : ""}</summary>
          <div className="ws-home__filterpanel">
            <label className="ws-field">
              <span className="ws-field__label">Type</span>
              <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(1); }}>
                <option value="">All types</option>
                {DOCUMENT_TYPES.filter((t) => seenTypes.has(t.code) || t.code === typeFilter).map((t) => (
                  <option key={t.code} value={t.code}>{t.label}</option>
                ))}
              </select>
            </label>
            <label className="ws-field">
              <span className="ws-field__label">Show</span>
              <select value={showArchived ? "archived" : "active"}
                      onChange={(event) => { setShowArchived(event.target.value === "archived"); setPage(1); }}>
                <option value="active">Active contracts</option>
                <option value="archived">Archived contracts</option>
              </select>
            </label>
            <label className="ws-field">
              <span className="ws-field__label">Order</span>
              <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }}>
                <option value="created_desc">Newest first</option>
                <option value="created_asc">Oldest first</option>
                <option value="name_asc">Name A–Z</option>
                <option value="name_desc">Name Z–A</option>
              </select>
            </label>
          </div>
        </details>
      </div>}

      {/* A scope FILTER, not a tablist: two pressed-state buttons re-query one region. */}
      {canSeeDepartment ? (
        <div className="ws-filter ws-home__chips" role="group" aria-label="Which deals">
          <button type="button" aria-pressed={scope === "own"} onClick={() => { setScope("own"); setPage(1); }}>
            My deals
          </button>
          <button type="button" aria-pressed={scope === "department"}
                  onClick={() => { setScope("department"); setPage(1); }}>
            {identity?.department ? `${identity.department.name} deals` : "Department deals"}
          </button>
        </div>
      ) : null}
      {canSeeDepartment && scope === "department" && !identity?.department ? (
        <p className="ws-pane__note" role="note">
          Your account is not in a department yet, so this view is empty until an administrator places you in one.
        </p>
      ) : null}

      {/* Where every deal stands (`AM-260`): only the stages holding a deal, in the deal's
          own order, one line that scrolls sideways on a phone. */}
      {stagesHeld.length ? (
        <div className="ws-filter ws-home__chips" role="group" aria-label="Filter by stage">
          <button type="button" aria-pressed={stageFilter === ""}
                  onClick={() => { setStageFilter(""); setPage(1); }}>
            All stages
          </button>
          {stagesHeld.map((code) => (
            <button key={code} type="button" aria-pressed={stageFilter === code}
                    onClick={() => { setStageFilter(stageFilter === code ? "" : code); setPage(1); }}>
              {STAGE_LABEL[code]}
              <span className="ws-filter__n">{summary?.stages?.[code] ?? 0}</span>
            </button>
          ))}
        </div>
      ) : null}

      {error ? (
        <div className={`ws-state ws-state--${stale ? "warn" : "error"}`} role="alert">
          <p className="ws-home__errtitle">
            {stale ? "These results could not be refreshed." : "Contracts could not be loaded."}
          </p>
          <p>
            {describeError(error)}
            {stale ? " The rows below are the last ones loaded successfully." : ""}
          </p>
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => void load()}>
            Try again
          </button>
        </div>
      ) : null}

      {contracts === null && !error ? (
        <div className="ws-hometable" aria-busy="true">
          <p className="ws-visually-hidden" role="status" aria-live="polite">Loading contracts…</p>
          {[0, 1, 2, 3].map((row) => (
            <div key={row} className="ws-docs__skel" aria-hidden="true">
              <span className="ws-skel ws-skel--line" style={{ width: "40%" }} />
              <span className="ws-skel ws-skel--line" style={{ width: "14%" }} />
            </div>
          ))}
        </div>
      ) : null}

      {contracts && contracts.length > 0 ? (
        <div className="ws-hometable">
          <table>
            <thead>
              <tr>
                <th scope="col">Contract</th>
                <th scope="col">Stage</th>
                <th scope="col">Changes and points</th>
                <th scope="col"><span className="ws-visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((contract) => {
                // the tint marks a row with a step for THIS reader — the header's own resolver
                const turn = !!contract.negotiation_stage && !!nextStep({
                  stage: contract.negotiation_stage.stage, counts: contract.counts,
                  viewer: stageViewer(can, isMine(contract)), canAnswer: isMine(contract) });
                const facts = contractFacts(contract, clientOf(contract));
                return (
                  <tr key={contract.id} className={turn ? "ws-hometable__turn" : undefined}>
                    <td>
                      <Link href={contractHref(contract.id)} className="ws-hometable__name" title={contract.name}>
                        {contractDisplayName(contract.name)}
                      </Link>
                      <span className="ws-hometable__facts">
                        {[...facts,
                          scope !== "own" ? contract.owner_name : null,
                          contract.archived_at ? `Archived ${shortDate(contract.archived_at)}` : null,
                        ].filter(Boolean).map((part) => <span key={part}>{part}</span>)}
                      </span>
                    </td>
                    <td data-label="Stage">
                      <StageBadge stage={contract.negotiation_stage} counts={contract.counts}
                                  viewer={stageViewer(can, isMine(contract))} />
                    </td>
                    <td data-label="Changes and points">
                      <CountsCell contract={contract} viewer={stageViewer(can, isMine(contract))} />
                    </td>
                    <td>
                      <div className="ws-rowact">
                        {/* the visible word stays short; the accessible name carries the contract */}
                        <Link href={contractHref(contract.id)} className="ws-btn ws-btn--sm"
                              aria-label={`${ACTION.open} ${contract.name}`}>
                          {ACTION.open}
                        </Link>
                        {/* Only the operations this caller has — absent, never disabled (47.6). */}
                        {(canEdit && isMine(contract)) || (canArchive && isMine(contract)) || canTransfer ? (
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
                                    <button type="button" role="menuitem" className="ws-menu__item"
                                            onClick={() => { closeMenu(); setEditing(contract); }}>
                                      Edit details
                                    </button>
                                  ) : null}
                                  {canTransfer && !contract.archived_at ? (
                                    <button type="button" role="menuitem" className="ws-menu__item"
                                            onClick={() => { closeMenu(); setTransferring(contract); }}>
                                      Transfer ownership
                                    </button>
                                  ) : null}
                                  {canArchive && isMine(contract) && !contract.archived_at ? (
                                    <button type="button" role="menuitem" className="ws-menu__item ws-menu__item--bad"
                                            onClick={() => { closeMenu(); setArchiving(contract); }}>
                                      Archive
                                    </button>
                                  ) : null}
                                  {canArchive && isMine(contract) && contract.archived_at ? (
                                    <button type="button" role="menuitem" className="ws-menu__item"
                                            onClick={() => {
                                              closeMenu();
                                              void api.restoreContract(contract.id).then(refresh).catch(setError);
                                            }}>
                                      Restore
                                    </button>
                                  ) : null}
                                  {/* canArchive also gates Delete (AM-55) */}
                                  {canArchive && isMine(contract) ? (
                                    <button type="button" role="menuitem" className="ws-menu__item ws-menu__item--bad"
                                            onClick={() => { closeMenu(); setDeleting(contract); }}>
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
        </div>
      ) : null}

      {/* Two emptinesses, two answers: nothing yet is an invitation; nothing matching is a
          dead end to back out of. One line each — no header, no icon. */}
      {contracts && contracts.length === 0 ? (
        <p className="ws-home__empty">
          {firstRun ? (persona === "legal" ? "Nothing has been sent to Legal yet." : "No contracts yet.")
            : !noFilters ? "No contracts match."
            : showArchived ? "Nothing archived. An archived contract is kept here, read-only, and can be restored."
            : "No deals in this view yet."}
          {firstRun && canUpload && persona !== "legal" ? (
            <button type="button" className="ws-btn ws-btn--sm" onClick={() => setUploadOpen(true)}>
              Upload your first contract
            </button>
          ) : !firstRun && !noFilters ? (
            <button type="button" className="ws-btn ws-btn--sm" onClick={clearFilters}>Clear search and filters</button>
          ) : showArchived && noFilters ? (
            <button type="button" className="ws-btn ws-btn--sm"
                    onClick={() => { setShowArchived(false); setPage(1); }}>
              Back to active contracts
            </button>
          ) : null}
        </p>
      ) : null}

      {pagination && pagination.total > pagination.page_size ? (
        <nav className="ws-pager" aria-label="Pagination">
          <span className="ws-pane__note" role="status" aria-live="polite">
            {(pagination.page - 1) * pagination.page_size + 1}–{Math.min(pagination.page * pagination.page_size, pagination.total)} of {pagination.total}
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
              <button key={n} type="button" className="ws-btn ws-btn--sm"
                      aria-current={n === pagination.page ? "page" : undefined} onClick={() => setPage(n)}>
                {n}
              </button>
            )))}
          <button type="button" className="ws-btn ws-btn--sm"
                  disabled={pagination.page * pagination.page_size >= pagination.total}
                  onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </nav>
      ) : null}
    </>
  );

  return (
    <>
      <div className="lm-page ws-home">
        {/* The person's home (S1, critic round 2026-11-03): whose contracts, the one primary
            action, what is this person's turn, then the list. For the lawyer the queue IS
            the page and the repository sits behind "All contracts". */}
        <PageHeader title={homeTitle(persona, scope)}
                    primary={canUpload ? (
                      <button type="button" className="ws-btn ws-btn--primary" onClick={() => setChooseOpen(true)}>
                        <IconPlus size={15} /> New contract
                      </button>
                    ) : null} />
        <HomeQueue companies={companies} />
        {persona === "legal" ? (
          <details className="ws-home__all">
            <summary className="ws-home__qtitle">
              All contracts
              {pagination ? <span className="ws-home__qn">{pagination.total}</span> : null}
            </summary>
            <div className="ws-home__list">{list}</div>
          </details>
        ) : (
          <section className="ws-home__list" aria-labelledby="ws-home-all">
            <h2 id="ws-home-all" className="ws-home__qtitle">
              All contracts
              {pagination ? <span className="ws-home__qn">{pagination.total}</span> : null}
            </h2>
            {list}
          </section>
        )}
      </div>

      {chooseOpen ? (
        <NewContractChooser onClose={() => setChooseOpen(false)}
                            onUpload={() => { setChooseOpen(false); setUploadOpen(true); }} />
      ) : null}

      {uploadOpen ? (
        <UploadContractDialog
          firstRun={!!firstRun}
          counterparties={knownCounterparties(contracts)}
          onClose={() => setUploadOpen(false)}
        />
      ) : null}

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
  const [name, setName] = useState(contract.name);
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
      // AM-64 (owner, 2026-09-13): the reader never selects a document type —
      // the intake records the assist lane's confident inference, and the review
      // is content-first either way. Nothing here touches `contract_type`.
      await api.updateContract(contract.id, {
        name: name.trim(),
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
      onSaved();
    } catch (cause) {
      setError(cause);
      setSaving(false);
    }
  }

  /* No scrim-click dismissal on THIS dialog (2026-09-08), unlike the two
     confirmations below. It is a form: a stray click beside it discarded a
     half-typed name and three declared version
     facts with no warning and no undo. Escape and Cancel are both still here,
     and both are deliberate gestures. */
  return (
    <Dialog onClose={onClose} titleId="ws-edit-title" dismissOnScrimClick={false}>
        <h2 id="ws-edit-title">Edit contract details</h2>
        <form onSubmit={save}>
          <label className="ws-field">
            <span className="ws-field__label">Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)} />
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
    </Dialog>
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

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
    <Dialog onClose={onClose} titleId="ws-arc-title">
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
    </Dialog>
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

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
    <Dialog onClose={onClose} titleId="ws-del-title">
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
    </Dialog>
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
  const [members, setMembers] = useState<DepartmentMembers | null>(null);
  const [newOwnerId, setNewOwnerId] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

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
    <Dialog onClose={onClose} titleId="ws-xfer-title">
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
    </Dialog>
  );
}

/** `?id=` never reaches this page: next.config.ts redirects it to `/contracts/{id}`. */
export default DocumentsListView;

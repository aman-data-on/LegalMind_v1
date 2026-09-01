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

import { api, describeError } from "@/lib/api";
import { DOCUMENT_TYPES, documentTypeLabel } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, ContractsSummary, Pagination } from "@/lib/types";

import {
  documentStatusBucket,
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
/** How many rows the priority queue shows before deferring to "View all". Five
 *  is a glance; a longer list is the table's job, and the table is right there. */
const ATTENTION_LIMIT = 5;

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
  const counts = contract.latest_analysis?.classification_counts;
  if (!analyzed || !counts) {
    return <span className="ws-findings-cell ws-pane__note">—</span>;
  }
  const buckets: Array<{ key: "match" | "review" | "missing"; n: number }> = [
    { key: "match", n: counts.MATCH ?? 0 },
    {
      key: "review",
      n: Object.entries(counts).reduce(
        (sum, [c, n]) => sum + (c !== "MATCH" && c !== "MISSING" ? n : 0), 0),
    },
    { key: "missing", n: counts.MISSING ?? 0 },
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

/** "Review 9 issues" — everything the analysis did not classify as a MATCH.
 *  Counted from the classifications the server sent, never re-derived from
 *  anything else: 52.7 keeps the client from computing a second opinion. */
function openIssueLabel(contract: Contract): string {
  const counts = contract.latest_analysis?.classification_counts ?? {};
  const n = Object.entries(counts)
    .reduce((sum, [c, v]) => sum + (c !== "MATCH" ? v : 0), 0);
  return `Review ${n} issue${n === 1 ? "" : "s"}`;
}

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  if (seconds < 172800) return "yesterday";
  return `${Math.round(seconds / 86400)} d ago`;
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
  const { can } = useSession();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [summary, setSummary] = useState<ContractsSummary | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [qInput, setQInput] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatusBucket | "">("");
  const [sort, setSort] = useState("created_desc");
  const [error, setError] = useState<unknown>(null);
  /** The priority queue, fetched on its own terms — see the effect below. */
  const [attention, setAttention] = useState<Contract[] | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  /** The row whose action menu is open, and the row being edited or deleted. */
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [editing, setEditing] = useState<Contract | null>(null);
  const [deleting, setDeleting] = useState<Contract | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.contracts(page, PAGE_SIZE, {
        q: q || undefined,
        contract_type: typeFilter || undefined,
        status: statusFilter || undefined,
        sort,
      });
      setContracts(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, q, typeFilter, statusFilter, sort]);

  useEffect(() => {
    void load();
  }, [load]);

  // The stat tiles are independent of the current page/filter — real counts
  // across every contract the caller owns, loaded once and refreshed whenever
  // the list itself reloads (e.g. right after an upload lands).
  useEffect(() => {
    let cancelled = false;
    api.contractsSummary().then((s) => {
      if (!cancelled) setSummary(s);
    }).catch(() => {
      // The stat row is a convenience; the table still works without it.
    });
    return () => {
      cancelled = true;
    };
  }, [contracts]);

  /*
   * The priority queue asks its own question, so it makes its own request.
   *
   * It used to be derived — `contracts.find(c => bucket(c) === "needs_attention")`
   * over whatever the table happened to be showing. That reads the wrong
   * dataset: the table is one page of 25, ordered by the user's current sort and
   * narrowed by their current filters, so a contract needing attention that sat
   * at position 26, or that fell outside an active filter, was invisible while
   * the tile beside it still counted it. The section rendered nothing and looked
   * like "all clear".
   *
   * `status` is a real server-side filter (the API computes the same
   * `_status_bucket` the row displays), so this asks the whole collection
   * directly and the queue can no longer disagree with the tile above it.
   */
  useEffect(() => {
    // Wait for the first list load rather than racing it. Without this the
    // effect fires twice on every mount — once at `contracts === null` and
    // again when the list arrives — asking the same question of the server
    // twice and rendering the answer twice.
    if (contracts === null) return;
    let cancelled = false;
    api.contracts(1, ATTENTION_LIMIT, {
      status: "needs_attention",
      sort: "created_desc",
    }).then((result) => {
      if (!cancelled) setAttention(result.items);
    }).catch(() => {
      // The queue is a shortcut into the table below; the table still stands.
    });
    return () => {
      cancelled = true;
    };
  }, [contracts]);

  // Debounce the search box so every keystroke doesn't fire a request.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setQ(qInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [qInput]);

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
  const canDelete = can(P.CONTRACT_DELETE);
  const firstRun = contracts !== null && contracts.length === 0 && page === 1
    && !q && !typeFilter && !statusFilter;
  // Only shown on the plain, unfiltered landing view — under an active
  // search/filter it would be answering a different question than the table
  // below it.
  const isDefaultView = page === 1 && !q && !typeFilter && !statusFilter;
  const queue = isDefaultView ? attention ?? [] : [];
  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;

  /** Send the table to one bucket. Every entry point resets the page — landing
   *  on page 3 of a filter you just applied shows an empty table. */
  function filterTo(bucket: DocumentStatusBucket) {
    setStatusFilter(bucket);
    setPage(1);
  }

  /** Both mutations refetch rather than editing local state: the server owns
   *  the row, and a soft delete in particular changes what the summary counts
   *  say. A spliced array would drift from both. */
  async function refresh() {
    setMenuFor(null);
    await load();
  }

  return (
    <>
      <div className="ws-context">
        <span className="ws-context__icon" aria-hidden="true"><IconFile size={18} /></span>
        <h1>Dashboard</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total contracts</span>
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
        {canUpload ? (
          <div className="ws-dash__act">
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
        ) : null}

        {uploadOpen ? (
          <section id="ws-upload-panel" className="ws-dash__upload">
            <UploadContract firstRun={!!firstRun} />
          </section>
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

        {queue.length > 0 ? (
          <section className="ws-doctend" aria-label="Contracts needing attention">
            <div className="ws-doctend__head">
              <h2 className="ws-attend__title">Needs Attention</h2>
              {summary && summary.needs_attention > queue.length ? (
                <button type="button" className="ws-viewall"
                        onClick={() => filterTo("needs_attention")}>
                  View all {summary.needs_attention}
                </button>
              ) : null}
            </div>
            <ul className="ws-queue">
              {queue.map((row) => (
                <li key={row.id}>
                  <Link href={`/dashboard?id=${row.id}`} className="ws-queue__row">
                    <span className="ws-queue__main">
                      <span className="ws-doctend__name">{row.name}</span>
                      {row.contract_type ? (
                        <span className="ws-chip ws-chip--type">{row.contract_type}</span>
                      ) : null}
                      <StatusPill contract={row} />
                    </span>
                    <span className="ws-queue__meta">
                      <FindingsCell contract={row} />
                      <span className="ws-pane__note ws-queue__when">
                        {row.latest_analysis?.completed_at
                          ? `Analyzed ${relativeTime(row.latest_analysis.completed_at)}`
                          : `Added ${row.created_at ? row.created_at.slice(0, 10) : "—"}`}
                      </span>
                      <span className="ws-doctend__go">
                        {openIssueLabel(row)} <IconChevronRight size={14} />
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>Documents could not be loaded.</h2>
            <p>{describeError(error)}</p>
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
            {[0, 1, 2].map((row) => (
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
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Type</th>
                  <th scope="col">Status</th>
                  <th scope="col">Findings</th>
                  <th scope="col">Last Analyzed</th>
                  <th scope="col">Added</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((contract) => {
                  const bucket = documentStatusBucket(contract);
                  return (
                    <tr key={contract.id}>
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
                      </td>
                      <td>
                        {contract.contract_type ? (
                          <span className="ws-chip ws-chip--type" title={documentTypeLabel(contract.contract_type)}>
                            {contract.contract_type}
                          </span>
                        ) : (
                          <span className="ws-chip">not declared</span>
                        )}
                      </td>
                      <td><StatusPill contract={contract} /></td>
                      <td><FindingsCell contract={contract} /></td>
                      <td className="ws-mono">
                        {bucket === "analyzing" ? "In progress"
                          : relativeTime(contract.latest_analysis?.completed_at ?? null)}
                      </td>
                      <td className="ws-mono">{contract.created_at ? contract.created_at.slice(0, 10) : "—"}</td>
                      <td>
                        <div className="ws-rowact">
                          <Link href={`/dashboard?id=${contract.id}`} className="ws-btn ws-btn--sm ws-btn--primary">
                            {bucket === "draft" ? "Analyze"
                              : bucket === "analyzing" ? "View Progress" : "Review"}
                          </Link>
                          {/* Only the operations this caller actually has. An
                              action shown-but-disabled advertises a capability
                              the account does not carry; hiding it says the
                              truth. The server re-checks regardless — this
                              gating is presentation only (47.6). */}
                          {canEdit || canDelete ? (
                            <div className="ws-menu">
                              <button
                                type="button"
                                className="ws-btn ws-btn--sm ws-menu__toggle"
                                aria-haspopup="menu"
                                aria-expanded={menuFor === contract.id}
                                aria-label={`More actions for ${contract.name}`}
                                onClick={() => setMenuFor(
                                  menuFor === contract.id ? null : contract.id)}
                              >
                                ⋯
                              </button>
                              {menuFor === contract.id ? (
                                <div className="ws-menu__list" role="menu">
                                  {canEdit ? (
                                    <button type="button" role="menuitem"
                                            className="ws-menu__item"
                                            onClick={() => {
                                              setMenuFor(null);
                                              setEditing(contract);
                                            }}>
                                      Edit details
                                    </button>
                                  ) : null}
                                  {canDelete ? (
                                    <button type="button" role="menuitem"
                                            className="ws-menu__item ws-menu__item--bad"
                                            onClick={() => {
                                              setMenuFor(null);
                                              setDeleting(contract);
                                            }}>
                                      Delete
                                    </button>
                                  ) : null}
                                </div>
                              ) : null}
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
          <span>Maximum file size 50&nbsp;MB</span>
        </div>
        </div>

        {pagination && pagination.total > 0 ? (
          <nav className="ws-pager" aria-label="Pagination">
            <span className="ws-pane__note">
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
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); void refresh(); }}
        />
      ) : null}

      {deleting ? (
        <DeleteContractDialog
          contract={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => { setDeleting(null); void refresh(); }}
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
  contract, onClose, onSaved,
}: { contract: Contract; onClose: () => void; onSaved: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [name, setName] = useState(contract.name);
  const [type, setType] = useState(contract.contract_type ?? "");
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
      await api.updateContract(contract.id, {
        name: name.trim(),
        contract_type: type || null,
      });
      onSaved();
    } catch (cause) {
      setError(cause);
      setSaving(false);
    }
  }

  return (
    <div className="ws-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
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
              against. Changing it does not re-run an analysis already on record.
            </span>
          </label>
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
 * Delete confirmation — the one modal shape DESIGN.md names outright, because a
 * destructive act is a genuine interruption.
 *
 * The copy differs by whether the contract has been analyzed, because the
 * server's behaviour differs: an unanalyzed contract is destroyed, an analyzed
 * one is withdrawn from view while its findings and audit trail are kept
 * (rule 17). Saying "permanently deleted" in both cases would be a lie in one
 * of them, and it is the case involving legal records.
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

  // Analyzed exactly as the row's own status reports it — not a second opinion
  // computed here (52.7). Whether the server hard- or soft-deletes follows the
  // same fact, so the warning and the outcome cannot disagree.
  const analyzed = contract.latest_analysis != null;

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
        <h2 id="ws-del-title">Delete this contract?</h2>
        <p className="ws-modal__body">
          <strong>{contract.name}</strong>
        </p>
        <p className="ws-modal__body">
          {analyzed
            ? "It has an analysis on record, so it will be removed from your workspace while its findings, decisions and audit history are retained."
            : "It has not been analyzed, so the contract and the file you uploaded will be permanently removed."}
        </p>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ws-btn ws-btn--bad"
                  disabled={busy} onClick={() => void confirm()}>
            {busy ? "Deleting…" : "Delete"}
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

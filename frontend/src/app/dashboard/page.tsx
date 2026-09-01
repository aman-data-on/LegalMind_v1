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
import { Suspense, useCallback, useEffect, useState } from "react";

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

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  if (seconds < 172800) return "yesterday";
  return `${Math.round(seconds / 86400)} d ago`;
}

function StatTile({
  icon, n, label, bucket,
}: { icon: React.ReactNode; n: number; label: string; bucket?: DocumentStatusBucket }) {
  return (
    <div className={`ws-doctile${bucket ? ` ws-doctile--${bucket}` : ""}`}>
      <div className="ws-doctile__head">
        <span className="ws-doctile__label">{label}</span>
        <span className="ws-doctile__icon" aria-hidden="true">{icon}</span>
      </div>
      <span className="ws-doctile__n ws-mono">{n}</span>
    </div>
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

  const firstRun = contracts !== null && contracts.length === 0 && page === 1
    && !q && !typeFilter && !statusFilter;
  // Only shown on the plain, unfiltered landing view — under an active
  // search/filter it would be answering a different question than the table
  // below it.
  const isDefaultView = page === 1 && !q && !typeFilter && !statusFilter;
  const attention = isDefaultView && summary && summary.needs_attention > 0
    ? contracts?.find((c) => documentStatusBucket(c) === "needs_attention") ?? null
    : null;
  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;

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

        {summary ? (
          <section className="ws-doctiles" aria-label="Document totals">
            <StatTile icon={<IconFile size={16} />} n={summary.total} label="Total Contracts" />
            <StatTile icon={<IconAlertCircle size={16} />} n={summary.needs_attention} label="Needs Attention" bucket="needs_attention" />
            <StatTile icon={<IconCheckCircle size={16} />} n={summary.analyzed} label="Analyzed" bucket="analyzed" />
            <StatTile icon={<IconClock size={16} />} n={summary.draft + summary.analyzing} label="Draft / In Progress" bucket="draft" />
          </section>
        ) : null}

        <div className="ws-docs__top">
          <UploadContract firstRun={!!firstRun} />
          <Pipeline />
        </div>

        {attention ? (
          <section className="ws-doctend" aria-label="Needs attention preview">
              <div className="ws-doctend__head">
                <h2 className="ws-attend__title">Needs Attention</h2>
                {summary && summary.needs_attention > 1 ? (
                  <button type="button" className="ws-viewall" onClick={() => setStatusFilter("needs_attention")}>
                    View all
                  </button>
                ) : null}
              </div>
              <Link href={`/dashboard?id=${attention.id}`} className="ws-doctend__card">
                <div className="ws-doctend__row">
                  <span className="ws-doctend__name">{attention.name}</span>
                  {attention.contract_type ? (
                    <span className="ws-chip ws-chip--type">{attention.contract_type}</span>
                  ) : null}
                  <StatusPill contract={attention} />
                </div>
                <p className="ws-pane__note">
                  Added {attention.created_at ? attention.created_at.slice(0, 10) : "—"}
                  {attention.latest_analysis?.completed_at
                    ? ` · Analyzed ${relativeTime(attention.latest_analysis.completed_at)}` : ""}
                </p>
                <FindingsCell contract={attention} />
                <span className="ws-doctend__go">
                  {(() => {
                    const counts = attention.latest_analysis?.classification_counts ?? {};
                    const n = Object.entries(counts)
                      .reduce((sum, [c, v]) => sum + (c !== "MATCH" ? v : 0), 0);
                    return `Review ${n} issue${n === 1 ? "" : "s"}`;
                  })()}
                  {" "}<IconChevronRight size={14} />
                </span>
            </Link>
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
                        <Link href={`/dashboard?id=${contract.id}`} className="ws-btn ws-btn--sm ws-btn--primary">
                          {bucket === "draft" ? "Analyze"
                            : bucket === "analyzing" ? "View Progress" : "Review"}
                        </Link>
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
                  <button
                    type="button"
                    className="ws-btn ws-btn--primary"
                    onClick={() => document
                      .getElementById("ws-upload-file")?.scrollIntoView({
                        behavior: "smooth", block: "center",
                      })}
                  >
                    Upload your first contract
                  </button>
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
      </div>
    </>
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

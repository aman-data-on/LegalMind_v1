"use client";

/**
 * Documents — the working inventory and the front door (2026-08-31 UX
 * correction, superseding the slice-4 create-form intake).
 *
 * The user's act is "here is a contract" — one upload control (drop or pick),
 * one confirm panel (name derived from the filename, type HUMAN-declared with
 * a filename hint — owner Q9 intact), one primary action that lands in the
 * workspace with analysis underway. The old create-empty-record-first flow was
 * the backend's object lifecycle leaking into the product; the record still
 * exists, the user just never meets it.
 *
 * Each row answers the legal user's actual question — what did analysis find —
 * through the list's permission-layered `latest_analysis` summary, instead of
 * echoing a contract lifecycle enum.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { documentTypeLabel } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Pagination } from "@/lib/types";

import { analysisCell, rowNeedsAttention } from "@/components/workspace/model";
import { UploadContract } from "@/components/workspace/UploadContract";

const PAGE_SIZE = 25;

const CALM_CLASSIFICATIONS = new Set(["MATCH"]);

/** Each count is a real link into that document's findings, pre-filtered to
 *  the classification it names — the drill starts on the landing page. */
function AnalysisSummary({ contract }: { contract: Contract }) {
  const cell = analysisCell(contract);
  if (cell.kind === "none") return <span className="ws-pane__note">No document yet</span>;
  if (cell.kind === "processing") return <span className="ws-pane__note">Processing…</span>;
  if (cell.kind === "unanalysed") return <span className="ws-pane__note">Not analysed yet</span>;
  if (cell.counts.length === 0) {
    return <span className="ws-chip">{cell.review_status}</span>;
  }
  return (
    <span className="ws-cell-chips">
      {cell.counts.map(({ classification, n }) => (
        <Link
          key={classification}
          href={`/workspace/${contract.id}?classification=${classification}`}
          className={`ws-chip ws-chip--link${CALM_CLASSIFICATIONS.has(classification) ? "" : " ws-chip--fill ws-chip--classify-fill"}`}
        >
          {classification} <b className="ws-mono">{n}</b>
        </Link>
      ))}
    </span>
  );
}

export default function DocumentsPage() {
  const { can } = useSession();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.contracts(page, PAGE_SIZE);
      setContracts(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.CONTRACT_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include document access.</p>
      </div>
    );
  }

  const firstRun = contracts !== null && contracts.length === 0 && page === 1;

  return (
    <>
      <div className="ws-context">
        <h1>Documents</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total</span>
        ) : null}
      </div>
      <div className="ws-docs">
        <UploadContract firstRun={firstRun} />

        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>Documents could not be loaded.</h2>
            <p>{describeError(error)}</p>
          </div>
        ) : null}

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

        {contracts && contracts.some(rowNeedsAttention) ? (
          // The work-dashboard question first: "what needs my attention?"
          // Grouping is by the server's own analysis counts (any non-MATCH),
          // never a client-side re-derivation, and never a severity ranking.
          <section className="ws-attend" aria-label="Needs attention">
            <h2 className="ws-attend__title">Needs attention</h2>
            <ul className="ws-attend__list">
              {contracts.filter(rowNeedsAttention).map((contract) => (
                <li key={contract.id} className="ws-attend__row">
                  <Link href={`/workspace/${contract.id}`} className="ws-attend__name">
                    {contract.name}
                  </Link>
                  {contract.contract_type ? (
                    <span className="ws-chip ws-chip--type">{contract.contract_type}</span>
                  ) : null}
                  <AnalysisSummary contract={contract} />
                  <Link href={`/workspace/${contract.id}`} className="ws-btn ws-btn--sm ws-attend__go">
                    Review
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {contracts && contracts.length > 0 ? (
          <div className="ws-docs__table">
            <h2 className="ws-attend__title">All documents</h2>
            <table>
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Type</th>
                  <th scope="col">Analysis</th>
                  <th scope="col">Added</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((contract) => (
                  <tr key={contract.id}>
                    <td>
                      <Link href={`/workspace/${contract.id}`}>{contract.name}</Link>
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
                    <td>
                      <AnalysisSummary contract={contract} />
                    </td>
                    <td className="ws-mono">{contract.created_at ? contract.created_at.slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {pagination && pagination.total > pagination.page_size ? (
          <nav className="ws-pager" aria-label="Pagination">
            <button type="button" className="ws-btn" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="ws-mono">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)}
            </span>
            <button
              type="button"
              className="ws-btn"
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

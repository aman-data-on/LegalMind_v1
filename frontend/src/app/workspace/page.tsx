"use client";

/**
 * Documents — the new UI's landing and intake screen (PRODUCT_UX_ROADMAP §C/§E
 * screens 2–3; slice 4, 2026-08-30). Replaces the minimal stand-in that the
 * strict cleanup put here so the new application had a front door.
 *
 * The intake's one prominent required choice is the document TYPE — declared,
 * never inferred (owner Q9). Creating a document lands directly in its workspace,
 * where the upload already lives (slice 1's empty state), so intake is one
 * continuous act: name and type here → upload there → findings and questions in
 * the same place.
 *
 * The list stays lean on purpose: name, type, status, created. A per-row "review
 * state" would need a list-level summary the contract does not carry (decision
 * #187 keeps `GET /contracts` free of per-row version joins); the workspace
 * itself shows document, findings and ask state the moment a row is opened.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { DOCUMENT_TYPES, documentTypeLabel } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Pagination } from "@/lib/types";

const PAGE_SIZE = 25;

export default function DocumentsPage() {
  const { can } = useSession();
  const router = useRouter();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);

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

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!contractType) return;
    setCreating(true);
    setCreateError(null);
    try {
      const contract = await api.createContract(name.trim(), contractType);
      // Intake continues in the workspace, where the upload lives.
      router.push(`/workspace/${contract.id}`);
    } catch (cause) {
      setCreateError(cause);
      setCreating(false);
    }
  }

  const canCreate = can(P.CONTRACT_CREATE);
  const firstRun = contracts !== null && contracts.length === 0 && page === 1;

  const intake = canCreate ? (
    <form className="ws-intake" onSubmit={create} aria-labelledby="ws-intake-title">
      <h2 id="ws-intake-title" className="ws-intake__title">
        {firstRun ? "Add your first document" : "Add a document"}
      </h2>
      <div className="ws-intake__fields">
        <label className="ws-field">
          <span className="ws-field__label">
            Name <span className="ws-field__req">(required)</span>
          </span>
          <input required value={name} onChange={(event) => setName(event.target.value)} disabled={creating} />
        </label>
        <label className="ws-field ws-field--type">
          <span className="ws-field__label">
            Document type <span className="ws-field__req">(required)</span>
          </span>
          <select required value={contractType} onChange={(event) => setContractType(event.target.value)} disabled={creating}>
            <option value="">Choose the type…</option>
            {DOCUMENT_TYPES.map((type) => (
              <option key={type.code} value={type.code}>
                {type.label} ({type.code})
              </option>
            ))}
          </select>
          <span className="ws-field__help">
            You declare the type; LegalMind never guesses it. Analysis compares the document
            only against the standards for this type.
          </span>
        </label>
        <button type="submit" className="ws-btn ws-btn--primary" disabled={creating || !name.trim() || !contractType}>
          {creating ? "Adding…" : "Add and open"}
        </button>
      </div>
      {createError ? (
        <p className="ws-field__error" role="alert">
          {createError instanceof ApiError ? describeError(createError) : "The document could not be added."}
        </p>
      ) : null}
    </form>
  ) : null;

  return (
    <>
      <div className="ws-context">
        <h1>Documents</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total</span>
        ) : null}
      </div>
      <div className="ws-docs">
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

        {firstRun ? (
          <div className="ws-docs__first">
            <p className="ws-docs__lede">
              LegalMind works on documents. Add one — the workspace then shows the text,
              the findings against your approved positions, and lets you ask questions,
              all in one place.
            </p>
            {intake ?? <p className="ws-pane__note">Your account does not include document creation.</p>}
          </div>
        ) : (
          <>
            {intake}
            {contracts && contracts.length > 0 ? (
              <div className="ws-docs__table">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Name</th>
                      <th scope="col">Type</th>
                      <th scope="col">Status</th>
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
                          <span className="ws-chip">{contract.status}</span>
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
          </>
        )}
      </div>
    </>
  );
}

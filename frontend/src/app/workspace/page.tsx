"use client";

/**
 * Documents — the new UI's entry point (2026-08-30 cleanup, PRODUCT_UX_ROADMAP §C:
 * "land on Documents, not a dashboard"). Root `/` and post-login both land here now,
 * closing the last gap where a fresh session had no new-UI screen to reach without
 * a contract id already in hand.
 *
 * A minimal, faithful analog of the legacy list-and-create screen (same two API
 * calls, `GET`/`POST /contracts`) rebuilt on the new shell — not the roadmap's full
 * P0 intake screen (that also owns type declaration prominence, upload, etc., and
 * is sequenced later); this exists so the new application has a real front door
 * today instead of a placeholder.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Pagination } from "@/lib/types";

export default function DocumentsPage() {
  const { can } = useSession();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.contracts(page);
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
    setCreating(true);
    setError(null);
    try {
      await api.createContract(name, contractType || undefined);
      setName("");
      setContractType("");
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <div className="ws-context">
        <h1>Documents</h1>
      </div>
      <div className="ws-state" style={{ maxWidth: "none" }}>
        <ErrorBanner error={error} />

        {can(P.CONTRACT_CREATE) ? (
          <form
            onSubmit={create}
            style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap", marginBottom: "24px" }}
          >
            <label>
              <span style={{ display: "block", fontSize: "13px", marginBottom: "4px" }}>Name</span>
              <input required value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              <span style={{ display: "block", fontSize: "13px", marginBottom: "4px" }}>Type (optional)</span>
              <input
                value={contractType}
                onChange={(event) => setContractType(event.target.value)}
              />
            </label>
            <button type="submit" className="ws-btn ws-btn--primary" disabled={creating}>
              {creating ? "Adding…" : "Add"}
            </button>
          </form>
        ) : null}

        {contracts === null ? (
          <p role="status" aria-live="polite">
            Loading documents…
          </p>
        ) : contracts.length === 0 ? (
          <p>No documents yet. Add one above to open its workspace.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>Name</th>
                <th style={{ textAlign: "left" }}>Type</th>
                <th style={{ textAlign: "left" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((contract) => (
                <tr key={contract.id}>
                  <td>
                    <Link href={`/workspace/${contract.id}`}>{contract.name}</Link>
                  </td>
                  <td>{contract.contract_type ?? "—"}</td>
                  <td className="ws-mono">{contract.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {pagination && pagination.total > pagination.page_size ? (
          <p className="ws-pane__note" style={{ marginTop: "12px" }}>
            Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)} ·{" "}
            {pagination.total} total
            {pagination.page > 1 ? (
              <button type="button" className="ws-btn" onClick={() => setPage((p) => p - 1)} style={{ marginLeft: "8px" }}>
                Previous
              </button>
            ) : null}
            {pagination.page * pagination.page_size < pagination.total ? (
              <button type="button" className="ws-btn" onClick={() => setPage((p) => p + 1)} style={{ marginLeft: "8px" }}>
                Next
              </button>
            ) : null}
          </p>
        ) : null}
      </div>
    </>
  );
}

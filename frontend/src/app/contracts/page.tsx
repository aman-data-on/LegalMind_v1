"use client";

/**
 * Contract list and creation — locked 52.6 (Steps 2, 34), 49.3, 49.6.
 *
 * The list shows only what the API returns, which is scoped to the caller's own
 * contracts (41.24). There is no client-side filtering that could reveal anything
 * the server withheld, because there is nothing withheld to reveal.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading, Pager } from "@/components/Feedback";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Pagination } from "@/lib/types";

export default function ContractsPage() {
  const { can } = useSession();
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");

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

  // 52.3 — a section the user cannot view renders an explicit restricted state
  // rather than an empty or broken view.
  if (!can(P.CONTRACT_VIEW)) return <AccessRestricted what="contracts" />;

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.createContract(name, contractType || undefined);
      setName("");
      setContractType("");
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  return (
    <>
      <h1>Contracts</h1>
      <ErrorBanner error={error} />

      <PermissionGate granted={can(P.CONTRACT_CREATE)}>
        <form className="card form-row" onSubmit={create}>
          <div className="field">
            <label className="field__label" htmlFor="contract-name">
              Contract name
            </label>
            <input
              id="contract-name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="contract-type">
              Type (optional)
            </label>
            <input
              id="contract-type"
              value={contractType}
              onChange={(event) => setContractType(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn--primary">
            Add contract
          </button>
        </form>
      </PermissionGate>

      {contracts === null ? (
        <Loading what="contracts" />
      ) : contracts.length === 0 ? (
        <EmptyState>No contracts yet.</EmptyState>
      ) : (
        <>
          <div className="table-card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((contract) => (
                  <tr key={contract.id}>
                    <td>
                      <Link href={`/contracts/${contract.id}`}>{contract.name}</Link>
                    </td>
                    <td>{contract.contract_type ?? "—"}</td>
                    <td>
                      {/* Rendered as received (52.7); the pill is presentation only. */}
                      <span className={`status status--${contract.status.toLowerCase()}`}>
                        {contract.status}
                      </span>
                    </td>
                    <td>{contract.created_at ? contract.created_at.slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pagination ? (
            <Pager
              page={pagination.page}
              pageSize={pagination.page_size}
              total={pagination.total}
              onPage={setPage}
            />
          ) : null}
        </>
      )}
    </>
  );
}

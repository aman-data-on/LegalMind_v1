"use client";

/**
 * Amendments (`AM-309`, design 11 §8 U7): a signed contract is changed by an amendment —
 * its own contract, governed by the signed one.
 *
 *   GovernedByLink   record header, on an amendment: "Amends <contract>", and a link to
 *                    the contract's terms in force (`AM-310`)
 *   AmendmentsPanel  Document tab, on the signed contract: its amendments and
 *                    "Start an amendment"
 *
 * The server decides who may start one and refuses with its reason; showing the button
 * is presentation only (rule 18). An amendment the reader may not open never arrives.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import { contractDisplayName } from "@/lib/labels";
import type { Contract } from "@/lib/types";

export function GovernedByLink({ contract }: { contract: Pick<Contract, "governed_by"> }) {
  const g = contract.governed_by;
  if (!g) return null;
  return (
    <span>
      Amends <Link href={`/contracts/${g.id}`}>{contractDisplayName(g.name)}</Link>
      {" "}(<Link href={`/contracts/${g.id}/terms`}>read its terms in force</Link>)
    </span>
  );
}

const said = (m: string) => m.charAt(0).toUpperCase() + m.slice(1).replace(/\.?$/, ".");

/** The server's refusal in plain words; a missing amendment template is not an error. */
export function amendmentError(cause: unknown): string {
  if (cause instanceof ApiError && cause.code === "NO_AMENDMENT_TEMPLATE") {
    return "No approved amendment template yet — Legal needs to approve one first.";
  }
  return said(describeError(cause));
}

export function AmendmentsPanel({ contract, canStart }: {
  contract: Pick<Contract, "id" | "amendments">;
  /** presentation only: signed, not itself an amendment, and the reader may create */
  canStart: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState<{ id: string; why: string } | null>(null);
  const list = contract.amendments ?? [];
  if (!list.length && !canStart) return null;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const made = await api.startAmendment(contract.id);
      if (made.starts_empty) setEmpty({ id: made.id, why: made.starts_empty });
      else router.push(`/contracts/${made.id}`);
    } catch (cause) {
      setError(amendmentError(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ws-replynote lm-amend" aria-labelledby="lm-amend-title">
      <div className="ws-replynote__text">
        <h2 id="lm-amend-title" className="ws-replynote__title">Amendments</h2>
        {list.length ? (
          <ul className="lm-amend__list">
            {list.map((a) => (
              <li key={a.id}>
                <Link href={`/contracts/${a.id}`}>{contractDisplayName(a.name)}</Link>
                <span>{a.signed ? "Signed" : a.archived ? "Archived" : "Being prepared"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="ws-replynote__sub">
            None yet. To change this signed contract, start an amendment: it begins from the contract as it stands.
          </p>
        )}
        {list.some((a) => a.signed) ? (
          <p className="ws-replynote__sub">
            <Link href={`/contracts/${contract.id}/terms`}>Read the terms in force</Link>: the contract
            with its signed amendments applied, each changed clause marked.
          </p>
        ) : null}
        {empty ? (
          <p className="ws-replynote__sub" role="status">
            The amendment was started. {said(empty.why)}{" "}
            <Link href={`/contracts/${empty.id}`}>Open the amendment</Link>
          </p>
        ) : null}
        {/* a refusal is the server's reason, said in ink — a way forward, not an alarm */}
        {error ? <p className="ws-replynote__sub" role="alert"><strong>{error}</strong></p> : null}
      </div>
      {canStart && !empty ? (
        <div className="ws-replynote__acts">
          <button type="button" className="ws-btn" disabled={busy} onClick={() => void start()}>
            {busy ? "Starting the amendment…" : "Start an amendment"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

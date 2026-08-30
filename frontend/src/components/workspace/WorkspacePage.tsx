"use client";

/**
 * The Review workspace for one contract — PRODUCT_UX_ROADMAP §C/§G, slice 1.
 *
 * Loads the contract (`GET /contracts/{id}`, which now lists its document
 * versions newest first), then the latest version (`GET /document-versions/{id}`,
 * carrying `assist_index`), and hands the version to the document pane. The
 * findings and ask regions are the next two slices and say so — without a link
 * back into the legacy application (2026-08-30 cleanup): the new UI carries no
 * navigation path into the old one, so an unbuilt pane states that plainly
 * rather than bouncing the user to a screen this product line is retiring.
 *
 * Denial semantics (49.5 / 52.4): an out-of-scope contract and a nonexistent one
 * are byte-identical on the wire and read identically here — "Not found." — never
 * "no access". A caller without contract.view sees the whole-section restricted
 * state, the one sanctioned disclosure level.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, DocumentVersion } from "@/lib/types";

import { DocumentPane } from "./DocumentPane";
import { FindingsPane } from "./FindingsPane";
import { HighlightProvider } from "./highlight";
import { NextSlice } from "./NextSlice";
import { UploadDocument } from "./UploadDocument";
import { WorkspaceLayout } from "./WorkspaceLayout";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; contract: Contract; version: DocumentVersion | null }
  | { kind: "error"; error: unknown };

export function WorkspacePage({ contractId }: { contractId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const contract = await api.contract(contractId);
      const latest = contract.document_versions?.[0];
      const version = latest ? await api.documentVersion(latest.id) : null;
      setState({ kind: "ready", contract, version });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [contractId]);

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

  if (state.kind === "loading") {
    return (
      <div className="ws-state" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the workspace…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "30%", height: "1.2rem" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "55%" }} aria-hidden="true" />
      </div>
    );
  }

  if (state.kind === "error") {
    const notFound = state.error instanceof ApiError && state.error.isNotFound;
    return (
      <div className={`ws-state${notFound ? "" : " ws-state--error"}`} role={notFound ? "note" : "alert"}>
        <h2>{notFound ? "Not found." : "The workspace could not be loaded."}</h2>
        {notFound ? (
          <p>
            <Link href="/workspace">Back to documents</Link>
          </p>
        ) : (
          <p>{describeError(state.error)}</p>
        )}
      </div>
    );
  }

  const { contract, version } = state;

  return (
    <HighlightProvider>
      <div className="ws-context">
        <h1>{contract.name}</h1>
        <div className="ws-context__meta">
          {contract.contract_type ? (
            <span className="ws-chip ws-chip--type">{contract.contract_type}</span>
          ) : (
            <span className="ws-chip">type not declared</span>
          )}
          <span className="ws-chip">{contract.status}</span>
          {version ? (
            <span className="ws-mono">
              {contract.document_versions?.length ?? 1} version
              {(contract.document_versions?.length ?? 1) === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
      </div>

      {version ? (
        <WorkspaceLayout
          document={<DocumentPane version={version} />}
          findings={<FindingsPane contractId={contract.id} version={version} />}
          ask={
            <NextSlice
              title="Ask"
              note="Ask still works in the current application while this pane is built."
            />
          }
        />
      ) : (
        <div className="ws-state">
          <h2>No document uploaded yet.</h2>
          <p>
            The workspace opens around a document. Upload one to this contract and the
            text, findings and questions all live here.
          </p>
          {can(P.DOCUMENT_UPLOAD) ? (
            <UploadDocument contractId={contract.id} onUploaded={() => void load()} />
          ) : (
            <p className="ws-pane__note">Your account does not include document upload.</p>
          )}
        </div>
      )}
    </HighlightProvider>
  );
}

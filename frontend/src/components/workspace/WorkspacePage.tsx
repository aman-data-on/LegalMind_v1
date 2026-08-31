"use client";

/**
 * The Review workspace for one contract — PRODUCT_UX_ROADMAP §C/§G, slice 1;
 * version lifecycle added 2026-08-31 (product-intent audit §§3–4/17).
 *
 * Loads the contract (`GET /contracts/{id}`, document versions newest first),
 * picks the version the URL asks for (`?version=`) or the latest, then loads it
 * (`GET /document-versions/{id}`, carrying `assist_index`) and hands it to the
 * panes. Uploading a revised version is a quiet, always-available act once a
 * document exists — re-uploading is OPTIONAL, never a gate — and lands on the
 * new version while every earlier version, Review and Finding stays reachable.
 *
 * Ask answers about the LATEST version only (the server resolves the
 * conversation's contract to its newest version — verified, not assumed). When
 * an OLDER version is open, the ask region says so plainly instead of rendering
 * a form whose answers would misattribute — the same honesty rule as every
 * other blocked surface (never fake, never silently misdirect).
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

import { AskPane } from "./AskPane";
import { DocumentPane } from "./DocumentPane";
import { FindingsPane } from "./FindingsPane";
import { HighlightProvider } from "./highlight";
import { pickVersion } from "./model";
import { UploadDocument } from "./UploadDocument";
import { WorkspaceLayout } from "./WorkspaceLayout";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; contract: Contract; version: DocumentVersion | null }
  | { kind: "error"; error: unknown };

/** The `?version=` param, read client-side (the house idiom — no useSearchParams). */
function requestedVersionId(): string | null {
  return new URLSearchParams(window.location.search).get("version");
}

export function WorkspacePage({ contractId }: { contractId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [reuploadOpen, setReuploadOpen] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const contract = await api.contract(contractId);
      const summary = pickVersion(contract.document_versions ?? [], requestedVersionId());
      const version = summary ? await api.documentVersion(summary.id) : null;
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
  const versions = contract.document_versions ?? [];
  const latest = versions[0] ?? null;
  const isLatest = version !== null && latest !== null && version.id === latest.id;

  /** Point the URL at a version and reload — `?evidence=` is dropped because an
   *  evidence row belongs to exactly one version's reading order. */
  function openVersion(versionId: string | null) {
    const url = new URL(window.location.href);
    url.searchParams.delete("evidence");
    if (versionId === null || versionId === latest?.id) url.searchParams.delete("version");
    else url.searchParams.set("version", versionId);
    window.history.replaceState(window.history.state, "", url);
    void load();
  }

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
          {versions.length > 1 && version ? (
            <label className="ws-version">
              <span className="ws-visually-hidden">Document version</span>
              <select value={version.id} onChange={(event) => openVersion(event.target.value)}>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number}
                    {v.id === latest?.id ? " (latest)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : version ? (
            <span className="ws-mono">1 version</span>
          ) : null}
          {version && can(P.DOCUMENT_UPLOAD) ? (
            <button
              type="button"
              className="ws-escalate__link"
              onClick={() => setReuploadOpen((open) => !open)}
            >
              {reuploadOpen ? "Cancel upload" : "Upload a revised version"}
            </button>
          ) : null}
        </div>
      </div>

      {reuploadOpen && version ? (
        <div className="ws-reupload">
          <p className="ws-pane__note">
            A revised document becomes a NEW version and is analyzed on its own. Every
            earlier version, Review and Finding stays exactly as it was.
          </p>
          <UploadDocument
            contractId={contract.id}
            onUploaded={() => {
              setReuploadOpen(false);
              openVersion(null); // land on the newest version
            }}
          />
        </div>
      ) : null}

      {version ? (
        <WorkspaceLayout
          document={<DocumentPane version={version} />}
          findings={<FindingsPane contractId={contract.id} version={version} />}
          ask={
            isLatest ? (
              <AskPane contractId={contract.id} />
            ) : (
              <>
                <div className="ws-pane__head">
                  <h2 className="ws-pane__title">Ask</h2>
                </div>
                <div className="ws-state" role="note">
                  <p>
                    Ask answers about the latest version of this document. You are
                    reading v{version.version_number}.
                  </p>
                  <p>
                    <button type="button" className="ws-escalate__link" onClick={() => openVersion(null)}>
                      Open the latest version
                    </button>
                  </p>
                </div>
              </>
            )
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

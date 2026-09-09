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
 * Ask answers about THE VERSION ON SCREEN (2026-09-02). It used to answer about
 * the newest version only — the server resolved the conversation's contract to
 * its newest version and offered no way to say otherwise — so a reader with an
 * older version open got a disabled input and a button to "open the latest
 * version". The ask endpoint now takes the version being asked about, so the
 * open version is simply passed down and Ask works on every one of them.
 *
 * Denial semantics (49.5 / 52.4): an out-of-scope contract and a nonexistent one
 * are byte-identical on the wire and read identically here — "Not found." — never
 * "no access". A caller without contract.view sees the whole-section restricted
 * state, the one sanctioned disclosure level.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { chainAnalysis } from "@/lib/analysisChain";
import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty, DocumentVersion } from "@/lib/types";
import { contractStatusLabel } from "@/lib/labels";
import { documentSourceChip } from "@/lib/documentTypes";

import { AnalysisPanel } from "./AnalysisPanel";
import { AskDock } from "./AskDock";
import { AskIntentProvider } from "./askIntent";
import { DocumentPane } from "./DocumentPane";
import { ExportControl } from "./ExportControl";
import { FindingsPane } from "./FindingsPane";
import { FindingsProvider, useFindingsState } from "./findingsState";
import { HighlightProvider } from "./highlight";
import { IconArrowLeft, IconLink } from "./icons";
import { pickVersion } from "./model";
import { UploadDocument } from "./UploadDocument";
import { VersionComparison } from "./VersionComparison";
import { WorkspaceLayout } from "./WorkspaceLayout";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; contract: Contract; version: DocumentVersion | null }
  | { kind: "error"; error: unknown };

/** How often, and for how long, a still-processing version is re-asked about.
 *  3s x 100 = five minutes — comfortably past the measured background OCR pass
 *  (~17s for a 30-page document), then it stops rather than polling forever. */
const PROCESSING_POLL_MS = 3000;
const PROCESSING_POLL_LIMIT = 100;

/** The `?version=` param, read client-side (the house idiom — no useSearchParams). */
function requestedVersionId(): string | null {
  return new URLSearchParams(window.location.search).get("version");
}

export function WorkspacePage({ contractId }: { contractId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [reuploadOpen, setReuploadOpen] = useState(false);
  /** AB-13 — the company this deal is with, and its other documents. */
  const [company, setCompany] = useState<Counterparty | null>(null);
  const [companyOpen, setCompanyOpen] = useState(false);
  // Read from `state`, not the destructured `contract`: that is unpacked after
  // an early return, and a hook may not live below one.
  const linkedCompanyId =
    state.kind === "ready" ? (state.contract.counterparty_id ?? null) : null;
  useEffect(() => {
    const id = linkedCompanyId;
    if (!id) { setCompany(null); return; }
    let cancelled = false;
    // Best-effort: a company that fails to load must not take the workspace
    // down — the header falls back to the version's declared text (r7).
    api.counterparty(id)
      .then((c) => { if (!cancelled) setCompany(c); })
      .catch(() => { if (!cancelled) setCompany(null); });
    return () => { cancelled = true; };
  }, [linkedCompanyId]);
  const [compareOpen, setCompareOpen] = useState(false);

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

  /**
   * A version whose processing has not concluded (the deferred-OCR path,
   * 2026-09-03) is watched: poll the version until PROCESSING resolves, then
   * complete the same in-flow analysis every upload gets (idempotent — 49.8
   * makes Review creation idempotent and a repeat analyze returns
   * `already_analysed`) and reload the workspace. Bounded, silent, and every
   * rendered state along the way is the server's own.
   */
  const watchedVersionId =
    state.kind === "ready" &&
    state.version !== null &&
    (state.version.processing_status === "PENDING" ||
      state.version.processing_status === "PROCESSING")
      ? state.version.id
      : null;
  useEffect(() => {
    if (!watchedVersionId) return;
    let polls = 0;
    let cancelled = false;
    const timer = window.setInterval(() => {
      polls += 1;
      if (polls > PROCESSING_POLL_LIMIT) {
        window.clearInterval(timer);
        return;
      }
      void api
        .documentVersion(watchedVersionId)
        .then(async (fresh) => {
          if (cancelled) return;
          if (fresh.processing_status === "PENDING" || fresh.processing_status === "PROCESSING") return;
          window.clearInterval(timer);
          await chainAnalysis(contractId, can(P.REVIEW_CREATE));
          if (!cancelled) void load();
        })
        .catch(() => {
          /* transient — the next tick asks again */
        });
    }, PROCESSING_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // `can` is stable for a session; deliberately keyed on the version watched.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchedVersionId, contractId, load]);

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
            <Link href="/dashboard">Back to documents</Link>
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
    <AskIntentProvider>
    <MaybeFindings contractId={contract.id} version={version}>
    {/* `.ws-workmain` gives the workspace the viewport below the shell and owns
        ALL scrolling (each panel scrolls itself; the page never does), so the
        context bar and Ask bar stay put while any panel scrolls. Only when a
        document exists — the empty state is an ordinary page. */}
    <div className={version ? "ws-workmain" : undefined}>
      <div className="ws-context">
        <Link className="ws-context__back" href="/dashboard" aria-label="Back to documents">
          <IconArrowLeft size={18} />
        </Link>
        <h1>{contract.name}</h1>
        <div className="ws-context__meta">
          {contract.contract_type ? (
            <span className="ws-chip ws-chip--type">{contract.contract_type}</span>
          ) : (
            <span className="ws-chip">type not declared</span>
          )}
          <span className="ws-chip">{contractStatusLabel(contract.status)}</span>
          {/*
            Whose paper this is, who it is with, and when it took effect — the
            manager's "document LeapSwitch ne banaya hai ya counterparty ne
            bheja hai" question, answered where the reviewer reads rather than
            only in the dialog that records it (2026-09-06). Each chip appears
            ONLY when that fact was declared: an absent declaration is a fact
            ("nobody said"), and a placeholder would invent one. Source is a
            property of the VERSION on screen, not of the contract — v1 ours,
            v2 theirs is exactly the workflow this exists to make visible.
          */}
          {version && documentSourceChip(version.source) ? (
            <span className={`ws-chip ws-chip--source-${version.source === "COUNTERPARTY" ? "their" : "our"}`}>
              {documentSourceChip(version.source)}
            </span>
          ) : null}
          {/*
            AB-13 r7 — the LINKED company wins, the frozen per-version
            declaration is the fallback. They answer different questions: the
            link is the live identity, the text is what someone typed for THIS
            version and can never change once reviewed. Linked, the chip is a
            real control: it opens every document for that company, which is the
            manager's "NDA → MSA → revisions should not sit isolated".
          */}
          {company ? (
            <button type="button" className="ws-chip ws-chip--company"
                    onClick={() => setCompanyOpen(true)}>
              {company.name}
            </button>
          ) : version?.counterparty ? (
            <span className="ws-chip" title="Counterparty, as declared for this version">
              {version.counterparty}
            </span>
          ) : null}
          {version?.effective_date ? (
            <span className="ws-chip ws-mono" title="Effective date, as declared">
              Effective {version.effective_date}
            </span>
          ) : null}
          {versions.length > 1 && version ? (
            <label className="ws-version">
              <span className="ws-visually-hidden">Document version</span>
              <select value={version.id} onChange={(event) => openVersion(event.target.value)}>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    Version {v.version_number}
                    {documentSourceChip(v.source) ? ` — ${documentSourceChip(v.source)}` : ""}
                    {v.id === latest?.id ? " (latest)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : version ? (
            <span className="ws-mono">Version 1</span>
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
          {/* Only with something to compare against. Locked PROD-04 puts
              `compare` in an ordinary User's hands, and the endpoint needs no
              permission beyond the one that reads the two versions. */}
          {versions.length > 1 ? (
            <button
              type="button"
              className="ws-escalate__link"
              aria-expanded={compareOpen}
              onClick={() => setCompareOpen((open) => !open)}
            >
              {compareOpen ? "Hide comparison" : "Compare versions"}
            </button>
          ) : null}
        </div>
        <span className="ws-context__spacer" />
        <div className="ws-context__acts">
          {version ? <HeaderDownload /> : null}
          <ShareControl />
        </div>
      </div>

      {compareOpen ? (
        <VersionComparison contractId={contract.id} versions={versions} />
      ) : null}

      {companyOpen && company ? (
        <CompanyDocuments company={company} currentId={contract.id}
                          onClose={() => setCompanyOpen(false)} />
      ) : null}

      {reuploadOpen && version ? (
        <div className="ws-reupload">
          <p className="ws-pane__note">
            A revised document becomes a NEW version and is analyzed on its own. Every
            earlier version, Review and Finding stays exactly as it was.
          </p>
          <UploadDocument
            contractId={contract.id}
            onUploaded={async () => {
              // The revised version gets the same in-flow analysis as a first
              // upload (one loop, not two journeys) — best-effort, the findings
              // pane explains any real blocker.
              await chainAnalysis(contract.id, can(P.REVIEW_CREATE));
              setReuploadOpen(false);
              openVersion(null); // land on the newest version
            }}
          />
        </div>
      ) : null}

      {version ? (
        <>
          <WorkspaceLayout
            document={<DocumentPane version={version} />}
            findings={<FindingsPane version={version} />}
            analysis={<AnalysisPanel documentVersionId={version.id} />}
          />
          {/* A floating launcher, not a layout row (DD-15): it reserves no
              workspace height, is mounted at every breakpoint, and opens over
              the canvas without replacing the document. It asks about the
              version on screen, whichever that is. */}
          <AskDock
            contractId={contract.id}
            documentVersionId={version.id}
            versionNumber={version.version_number}
            isLatest={isLatest}
            onOpenVersion={(id) => openVersion(id)}
          />
        </>
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
    </div>
    </MaybeFindings>
    </AskIntentProvider>
    </HighlightProvider>
  );
}

/** The findings state machine wraps the whole page when a version exists (the
 *  header's Download needs the resolved Review); without a document there is
 *  nothing to analyse, and the children render provider-less. */
function MaybeFindings({
  contractId,
  version,
  children,
}: {
  contractId: string;
  version: DocumentVersion | null;
  children: React.ReactNode;
}) {
  if (!version) return <>{children}</>;
  return (
    <FindingsProvider contractId={contractId} version={version}>
      {children}
    </FindingsProvider>
  );
}

/** The header's Download — the existing export control, aimed at the version's
 *  resolved Review. Renders nothing until the Review exists (no fake control). */
function HeaderDownload() {
  const { state } = useFindingsState();
  if (state.kind !== "ready" && state.kind !== "in-flight" && state.kind !== "failed") return null;
  return <ExportControl reviewId={state.review.id} />;
}

/** Share = copy the current deep-linkable URL (the highlight gesture's own
 *  durable form). Nothing is published anywhere — it is the address bar. */
function ShareControl() {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <button
      type="button"
      className="ws-btn ws-btn--primary ws-btn--share"
      onClick={() => {
        void navigator.clipboard.writeText(window.location.href).then(
          () => {
            setFailed(false);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
          },
          // Clipboard access can be denied (permissions, an insecure context) —
          // without this the button did nothing at all and looked broken.
          () => {
            setCopied(false);
            setFailed(true);
            window.setTimeout(() => setFailed(false), 1600);
          },
        );
      }}
    >
      <IconLink size={15} /> {copied ? "Link copied" : failed ? "Couldn't copy — copy from the address bar" : "Share"}
    </button>
  );
}

/**
 * Every document for one company — AB-13 r3, the manager's "related documents".
 *
 * The list is DERIVED from the counterparty link, not from any document-to-
 * document relationship: the server returns the contracts this caller may
 * already see, so nothing here widens disclosure. Archived deals are included
 * and SAID to be archived, because a company's history is not a working list
 * and AB-12 r6 destroys nothing.
 */
function CompanyDocuments({
  company, currentId, onClose,
}: { company: Counterparty; currentId: string; onClose: () => void }) {
  const contracts = company.contracts ?? [];
  return (
    <div className="ws-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div className="ws-modal__box" role="dialog" aria-modal="true"
           aria-labelledby="ws-company-title"
           onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
        <h2 id="ws-company-title">{company.name}</h2>
        {company.industry ? <p className="ws-pane__note">{company.industry}</p> : null}
        {company.relationship_notes ? (
          <p className="ws-pane__note">{company.relationship_notes}</p>
        ) : null}
        {contracts.length === 0 ? (
          <p className="ws-pane__note">
            No other documents are linked to this company yet.
          </p>
        ) : (
          <ul className="ws-companydocs">
            {contracts.map((c) => (
              <li key={c.id}>
                <Link href={`/dashboard?id=${c.id}`} onClick={onClose}>{c.name}</Link>
                {c.contract_type ? (
                  <span className="ws-chip ws-chip--type">{c.contract_type}</span>
                ) : null}
                {c.archived_at ? <span className="ws-chip">Archived</span> : null}
                {c.id === currentId ? (
                  <span className="ws-pane__note">open now</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

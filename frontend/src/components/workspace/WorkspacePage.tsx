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
import { useCallback, useEffect, useRef, useState } from "react";

import { chainAnalysis } from "@/lib/analysisChain";
import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty, DocumentVersion, ReviewAssignments } from "@/lib/types";
import { ACTION, contractDisplayName, contractStatusLabel, type StageViewer } from "@/lib/labels";
import { nextStep, runStep, useStep, type StepKind } from "@/lib/nextStep";
import { PageHeader } from "@/components/page/PageHeader";
import { documentSourceChip } from "@/lib/documentTypes";

import { Dialog } from "@/components/Dialog";

import { AnalysisPanel } from "./AnalysisPanel";
import { AskDockLazy } from "./AskDockLazy";
import { AskIntentProvider } from "./askIntent";
import { ChangesPane, ReplyNotice, SendOut, useClientChanges } from "./ChangesPane";
import { PackageBar, PackageCard, usePackagePlan, usePreparedEntries } from "./Package";
import { AmendmentsPanel, GovernedByLink } from "./Amendments";
import { AMENDMENT_PLACE, packageLine } from "@/lib/package";
import { ClientMenu } from "@/components/clients/ClientWorkspace";
import { CollaboratorsControl } from "./CollaboratorsControl";
import { WEBSITE_KEY_BY_TYPE } from "@/components/diff-talk/text";
import { DocumentPane } from "./DocumentPane";
import { FindingsPane } from "./FindingsPane";
import { FindingsProvider, primeReviews, useFindingsState, useFindingsStateOptional } from "./findingsState";
import { HighlightProvider } from "./highlight";
import { contractHref, contractTabFromPath, pickVersion, shortDate, stageViewer, versionRoleLabel } from "./model";
import { RecordSigning } from "./SigningSheet";
import { StageBadge } from "./StageBadge";
import { UploadDocument } from "./UploadDocument";
import { VersionComparison } from "./VersionComparison";
import { PaneBoundary } from "./PaneBoundary";
import { PhoneBar, WorkspaceLayout, useMinWidth, type PhoneView, type Region } from "./WorkspaceLayout";

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

/**
 * `?compare=1` opens the comparison already expanded (2026-09-10).
 *
 * Added so the Client Profile's "Compare" can hand the reader straight to the
 * comparison that lives HERE, rather than growing a second one of its own.
 * The alternative was a Client Profiles button that navigated to a workspace
 * with the panel closed — a control that does nothing, which is exactly what
 * the owner's instruction rules out ("Do not create fake buttons").
 *
 * Read once, at mount, as the initial state: the panel stays a plain toggle
 * afterwards, so opening it from a link and then closing it does not fight the
 * URL. Guarded for the server pass, where `window` does not exist.
 */
function comparisonRequested(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("compare") === "1";
}

/** `/contracts/{id}/changes` (`AM-263`) — or the older `?tab=changes` — opens the
 *  client's changes (CLM Phase 1, UX §3.4). */
function initialView(): "document" | "changes" {
  if (typeof window === "undefined") return "document";
  return contractTabFromPath(window.location.pathname).tab === "changes"
    || new URLSearchParams(window.location.search).get("tab") === "changes" ? "changes" : "document";
}

export function WorkspacePage({ contractId }: { contractId: string }) {
  const { can, identity } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [view, setView] = useState(initialView);
  const changesFeed = useClientChanges(
    contractId, state.kind === "ready" ? (state.contract.document_versions ?? []) : []);
  // AM-307: the final contract's dry run — only while the client's returned copy is the
  // latest version; read again after each recorded answer
  const returned = state.kind === "ready" && state.contract.negotiation_stage?.stage === "CLIENT_RETURNED"
    && state.contract.document_versions?.[0]?.version_role === "CLIENT_MODIFIED";
  const pkg = usePackagePlan(contractId, returned,
                             changesFeed.state.kind === "ready" ? changesFeed.state.list : null);
  const prepared = usePreparedEntries(state.kind === "ready" ? state.contract.document_versions?.[0] ?? null : null);
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
  // `AM-291`: an answer on the Changes tab changes the server's counts — re-read them (and
  // the stage) so the header, the badge and the Summary say the new numbers, never a guess
  const listed = changesFeed.state.kind === "ready" ? changesFeed.state.list : null;
  const firstList = useRef<unknown>(null);
  useEffect(() => {
    if (!listed) return;
    if (firstList.current === null) { firstList.current = listed; return; }
    let cancelled = false;
    api.contract(contractId).then((fresh) => {
      if (cancelled) return;
      setState((prev) => prev.kind === "ready" ? { ...prev, contract: { ...prev.contract,
        counts: fresh.counts, negotiation_stage: fresh.negotiation_stage } } as Load : prev);
    }).catch(() => { /* the last counts stand until the next load */ });
    return () => { cancelled = true; };
  }, [listed, contractId]);
  const [compareOpen, setCompareOpen] = useState(comparisonRequested);
  const [copied, setCopied] = useState<string | null>(null);
  /* The phone's one tab row (polish batch): which region it shows and whether Ask's sheet
     is open live here, since the bar spans both the Document and the Changes views. */
  const phone = useMinWidth(900) === false;
  const [phoneTab, setPhoneTab] = useState<Region>("document");
  const [phoneAsk, setPhoneAsk] = useState(false);
  const [phoneAskSeq, setPhoneAskSeq] = useState(0);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      primeReviews(contractId);       // with the contract, not after its version (the findings' first read)
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

  /** The tab is the address (`AM-263`): /contracts/{id}/changes. */
  function chooseView(which: "document" | "changes") {
    setView(which);
    const url = new URL(window.location.href);
    url.searchParams.delete("tab");
    if (url.pathname.startsWith("/contracts/")) {
      url.pathname = contractHref(contract.id, which === "changes" ? "changes" : undefined);
    } else if (which === "changes") url.searchParams.set("tab", "changes");
    window.history.replaceState(window.history.state, "", url);
  }

  // The header's ONE primary action is the next step at this stage (CLM UI pass 2);
  // whatever it does not take is a quiet item under "More". Every control here is
  // shown only to someone who may use it — the server checks each write again.
  const changeList = changesFeed.state.kind === "ready" ? changesFeed.state.list : null;
  const stageCode = contract.negotiation_stage?.stage;
  const amendment = contract.contract_type === "AMENDMENT";        // AM-310
  const canUpload = !!version && can(P.DOCUMENT_UPLOAD) && contract.owner_id === identity?.user_id;
  const uploadToggle = () => setReuploadOpen((open) => !open);
  /** Share = copy the current deep-linkable URL (the address bar's own durable form);
   *  nothing is published anywhere. Said in a status line, since the menu closes. */
  const copyLink = () => {
    void navigator.clipboard.writeText(window.location.href).then(
      () => setCopied("Link copied"),
      () => setCopied("Couldn't copy — copy it from the address bar"),
    ).finally(() => window.setTimeout(() => setCopied(null), 2400));
  };
  const isOwner = contract.owner_id === identity?.user_id;
  const viewer = stageViewer(can, isOwner);
  const canAnswer = changeList ? !!(changeList.can_answer || changeList.can_send) : isOwner;
  const overflow: React.ReactNode[] = [];
  if (canUpload) {
    overflow.push(<button key="up" type="button" role="menuitem" className="ws-menu__item"
                          onClick={uploadToggle}>Upload new version</button>);
  }
  if (versions.length > 1) {
    overflow.push(<button key="cmp" type="button" role="menuitem" className="ws-menu__item"
                          onClick={() => setCompareOpen((open) => !open)}>
      {compareOpen ? "Hide version comparison" : "Compare versions"}</button>);
  }
  if (phone && version && versions.length > 1) {
    // the phone's version choice: one group in ⋯ instead of a select row above the document
    overflow.unshift(<div key="vers" role="group" aria-label="Version" className="ws-menu__group">
      {versions.map((v) => (
        <button key={v.id} type="button" role="menuitemradio" aria-checked={v.id === version.id}
                className="ws-menu__item" onClick={() => openVersion(v.id)}>
          Version {versionOption(v.version_number,
                                 versionRoleLabel(v, versions) ?? documentSourceChip(v.source),
                                 v.id === latest?.id)}
        </button>
      ))}
    </div>);
  }
  if (version) overflow.push(<ReportMenuItem key="rep" />);
  overflow.push(<button key="link" type="button" role="menuitem" className="ws-menu__item"
                        onClick={copyLink}>Copy link</button>);
  if (version) {
    // Diff-Talk (owner, 2026-10-12): this document on the right; on the left its
    // type's website document when there is one.
    overflow.push(<Link key="dt" role="menuitem" className="ws-menu__item" href={`/dashboard/diff?${new URLSearchParams({
      left: WEBSITE_KEY_BY_TYPE[contract.contract_type ?? ""] ?? "", right: version.id })}`}>
      Compare in Diff-Talk</Link>);
  }

  /** One tap on the phone's bar: a region, the Changes view, or Ask's sheet. */
  const choosePhone = (which: PhoneView) => {
    setPhoneAsk(false);
    if (which === "changes") { chooseView("changes"); return; }
    if (view === "changes") chooseView("document");
    setPhoneTab(which);
    window.scrollTo({ top: 0 });
  };
  const openPhoneAsk = () => {
    if (view === "changes") chooseView("document");
    setPhoneAsk(true);
    setPhoneAskSeq((n) => n + 1);
  };

  return (
    <HighlightProvider>
    <AskIntentProvider>
    <MaybeFindings contractId={contract.id} ownerId={contract.owner_id} version={version}
                   signed={contract.negotiation_stage?.stage === "SIGNED"
                     || !!contract.document_versions?.some((v) => v.version_role === "FINAL_SIGNED")}>
    {/* `.ws-workmain` gives the workspace the viewport below the shell and owns
        ALL scrolling (each panel scrolls itself; the page never does), so the
        context bar and Ask bar stay put while any panel scrolls. Only when a
        document exists — the empty state is an ordinary page. */}
    <div className={version ? "ws-workmain ws-recordpage" : "ws-recordpage"}
         data-phone={phone && version ? "" : undefined}>
      {/* One record header on both tabs (CLM UI pass 2, owner 2026-11-02): what the
          contract is and where the deal stands, then ONE primary action for that stage,
          the rest as quiet buttons and a "More" menu — in place of a row of underlined
          links beside a version select. */}
      {/* ONE page header (cross-page pass): back, the title, where the deal stands and who
          owns it, quiet actions, and the ONE primary step for this person at this stage. */}
      <div className="ws-record">
      <RecordHeader contract={contract} latest={latest} version={version} view={view}
                    viewer={viewer} canAnswer={canAnswer} company={company} packageReady={!!pkg.plan?.available}
                    onCompany={() => setCompanyOpen(true)} onView={chooseView} onReload={() => void load()}
                    secondary={<>
                      {copied ? <span className="ws-record__copied" role="status">{copied}</span> : null}
                      <ClientMenu label="More actions">{overflow}</ClientMenu>
                    </>}>
      {version && !phone ? (
        <div className="ws-record__bar">
          {changesFeed.enabled ? (
            <div className="ws-record__tabs" role="tablist" aria-label="Contract views">
              {(["document", "changes"] as const).map((which) => {
                // the badge is what is left for THIS reader (`counts`), never the total
                const mine = which === "changes" ? contract.counts?.changes_left_for_me : undefined;
                return (
                  <button key={which} type="button" role="tab" aria-selected={view === which}
                          onClick={() => chooseView(which)}>
                    {which === "document" ? "Document" : "Changes"}
                    {mine ? <span className="ws-filter__n" aria-label={`${mine} yours`}>{mine}</span> : null}
                  </button>
                );
              })}
            </div>
          ) : null}
          {versions.length > 1 ? (
            <label className="ws-version">
              <span className="ws-version__label">Version</span>
              <select value={version.id} onChange={(event) => openVersion(event.target.value)}>
                {versions.map((v) => {
                  const role = versionRoleLabel(v, versions) ?? documentSourceChip(v.source);
                  return (
                    <option key={v.id} value={v.id}>
                      {versionOption(v.version_number, role, v.id === latest?.id)}
                    </option>
                  );
                })}
              </select>
            </label>
          ) : (
            <span className="ws-version">
              <span className="ws-version__label">Version</span>{" "}
              {versionOption(1, versionRoleLabel(version, versions)
                ?? documentSourceChip(version.source), false)}
            </span>
          )}
        </div>
      ) : null}
      </RecordHeader>
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
            A revised document becomes a new version and is analysed on its own. Earlier versions and their reviews are kept.
          </p>
          <UploadDocument
            contractId={contract.id}
            // with the client, what comes back is theirs; otherwise the reader says
            roleDefault={stageCode === "WITH_CLIENT" ? "CLIENT_MODIFIED" : ""}
            onUploaded={async () => {
              // The revised version gets the same in-flow analysis as a first
              // upload (one loop, not two journeys) — best-effort, the findings
              // pane explains any real blocker.
              await chainAnalysis(contract.id, can(P.REVIEW_CREATE));
              setReuploadOpen(false);
              openVersion(null); // land on the newest version
            }}
          />
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => setReuploadOpen(false)}>
            Cancel upload
          </button>
        </div>
      ) : null}

      {/* AM-293: the reply's banner (its files, "send it") only once nothing is open —
          at Ready to send, or once it went out. While a point is open the stage reads
          With Legal and nothing here offers it as sendable. */}
      {version && view === "document" && version.reply
        && (version.sent_at || stageCode === "READY_TO_SEND") ? (
        <ReplyNotice version={version} versions={versions} canSend={!!changeList?.can_send} />
      ) : null}
      {version && view === "document" && version.package ? (
        <PackageCard version={version} versions={versions}
                     filesOpen={stageCode === "READY_TO_SEND" || stageCode === "READY_TO_SIGN" || stageCode === "SIGNED"} />
      ) : null}
      {view === "document" ? (
        <AmendmentsPanel contract={contract}
                         canStart={stageCode === "SIGNED" && contract.contract_type !== "AMENDMENT" && !contract.governed_by
                                   && !contract.archived_at && can(P.CONTRACT_CREATE) && can(P.CONTRACT_UPDATE)} />
      ) : null}

      {version && changesFeed.enabled && view === "changes" ? (
        <ChangesPane contractId={contract.id} versions={versions} changes={changesFeed}
                     onVersionCreated={() => { setView("document"); openVersion(null); }}
                     packageBar={pkg.plan ? (onPick: (rowKey: string) => void) => (
                       <PackageBar contractId={contract.id} plan={pkg.plan!} onReload={pkg.reload}
                                   canPrepare={!!changeList?.can_answer} onPick={onPick}
                                   canRestate={can(P.LEGAL_APPROVE_CUSTOMIZATION)}
                                   nextVersion={(latest?.version_number ?? 0) + 1}
                                   onPrepared={() => { setView("document"); openVersion(null); }} />
                     ) : undefined}
                     place={amendment ? AMENDMENT_PLACE : undefined}
                     packageLine={pkg.plan || prepared ? (c) => packageLine(c, pkg.plan?.entries ?? prepared ?? [],
                                                                             pkg.plan?.blockers,
                                                                             amendment ? AMENDMENT_PLACE : undefined)
                       : undefined} />
      ) : version ? (
        <>
          {/* Ask is DOCKED into the right column (owner, 2026-09-09,
              superseding DD-15's floating dock): it reserves space in that
              column only while open, so it never comes to rest over the
              document or a finding. Closed it is the launcher at the foot of
              the column. It asks about the version on screen, whichever that
              is. Below 900px there is only one column, so it keeps DD-15's
              overlay sheet — see the layout's narrow branch. */}
          <WorkspaceLayout
            document={<PaneBoundary what="The document"><DocumentPane version={version} /></PaneBoundary>}
            findings={<PaneBoundary what="The points"><FindingsPane version={version} /></PaneBoundary>}
            analysis={<PaneBoundary what="The summary"><AnalysisPanel documentVersionId={version.id}
                                     stage={contract.negotiation_stage ?? null}
                                     viewer={stageViewer(can, contract.owner_id === identity?.user_id)}
                                     counts={contract.counts} /></PaneBoundary>}
            phone={phone ? { tab: phoneTab, setTab: setPhoneTab, askOpen: phoneAsk,
                             setAskOpen: setPhoneAsk, askFocusSeq: phoneAskSeq } : undefined}
            ask={<PaneBoundary what="Ask">
              <AskDockLazy
                contractId={contract.id}
                documentVersionId={version.id}
                versionNumber={version.version_number}
                isLatest={isLatest}
                onOpenVersion={(id) => openVersion(id)}
              />
            </PaneBoundary>}
          />
        </>
      ) : (
        <div className="ws-state">
          <h2>No document uploaded yet.</h2>
          <p>
            Upload one to see its text, findings and questions here.
          </p>
          {can(P.DOCUMENT_UPLOAD) && contract.owner_id === identity?.user_id ? (
            <UploadDocument contractId={contract.id} onUploaded={() => void load()} />
          ) : (
            <p className="ws-pane__note">Only the contract&rsquo;s owner can upload a document to it.</p>
          )}
        </div>
      )}
      {phone && version ? (
        <PhoneBar view={view === "changes" ? "changes" : phoneTab} onView={choosePhone}
                  changesBadge={changesFeed.enabled ? (contract.counts?.changes_left_for_me ?? null) : undefined}
                  askOpen={phoneAsk && view !== "changes"} onAsk={openPhoneAsk} />
      ) : null}
    </div>
    </MaybeFindings>
    </AskIntentProvider>
    </HighlightProvider>
  );
}

/** A version as the switcher names it: "2 (client's, latest)" — no middot (page 2). */
function versionOption(n: number, role: string | null | undefined, latest: boolean): string {
  const said = [role ? role.charAt(0).toLowerCase() + role.slice(1) : null,
                latest ? "latest" : null].filter(Boolean).join(", ");
  return said ? `${n} (${said})` : String(n);
}

/** The findings state machine wraps the whole page when a version exists (the
 *  header's Download needs the resolved Review); without a document there is
 *  nothing to analyse, and the children render provider-less. */
function MaybeFindings({
  contractId,
  ownerId,
  version,
  signed,
  children,
}: {
  contractId: string;
  ownerId: string;
  version: DocumentVersion | null;
  signed: boolean;
  children: React.ReactNode;
}) {
  if (!version) return <>{children}</>;
  return (
    <FindingsProvider contractId={contractId} ownerId={ownerId} version={version} signed={signed}>
      {children}
    </FindingsProvider>
  );
}

/** The report, under ⋯: it opens the report view, where PDF and Word download beside the
 *  preview (owner, 2026-10-22). Absent until the Review exists (no fake control). */
function ReportMenuItem() {
  const { state } = useFindingsState();
  const { can } = useSession();
  if (state.kind !== "ready" && state.kind !== "in-flight" && state.kind !== "failed") return null;
  if (!can(P.REPORT_VIEW)) return null;
  return (
    <Link role="menuitem" className="ws-menu__item" href={`/dashboard/reviews?id=${state.review.id}`}>
      View report
    </Link>
  );
}

/** The contract page's header (cross-page pass): `PageHeader` with the deal's facts and the
 *  ONE primary step `nextStep` resolves for this reader from the server's stage, counts
 *  and permissions. The pane that owns each act does it (`useStep`); this only asks. */
function RecordHeader({
  contract, latest, version, view, viewer, canAnswer, company, onCompany, onView, onReload, secondary, children,
  packageReady = false,
}: {
  packageReady?: boolean;
  contract: Contract; latest: DocumentVersion | null; version: DocumentVersion | null;
  view: "document" | "changes"; viewer: StageViewer; canAnswer: boolean; company: Counterparty | null;
  onCompany: () => void; onView: (which: "document" | "changes") => void; onReload: () => void;
  secondary: React.ReactNode; children: React.ReactNode;
}) {
  const { identity } = useSession();
  const findings = useFindingsStateOptional();
  const reviewId = findings && findings.state.kind === "ready" ? findings.state.review.id : null;
  const [assign, setAssign] = useState<ReviewAssignments | null>(null);
  useEffect(() => {
    if (!reviewId) return;
    let cancelled = false;
    api.reviewAssignments(reviewId).then((got) => { if (!cancelled) setAssign(got); })
      .catch(() => { /* nothing to show: the control stays absent */ });
    return () => { cancelled = true; };
  }, [reviewId]);
  const signedAt = contract.negotiation_stage?.stage === "SIGNED" ? contract.negotiation_stage.since : null;
  // signed: the review is for reference, so who holds it and "Send to Legal" are not shown
  const holder = signedAt ? undefined : assign?.assigned[0];
  const canSendToLegal = !signedAt && !!assign?.can_send && !holder && assign.eligible.length > 0;
  const ours = !!latest && latest.version_role !== "CLIENT_MODIFIED" && latest.version_role !== "FINAL_SIGNED";
  const step = findings?.reference ? null : nextStep({
    stage: contract.negotiation_stage?.stage, counts: contract.counts, viewer, canAnswer, canSendToLegal,
    replyReady: !!latest?.reply && !latest.sent_at,
    draftUnsent: ours && !latest?.reply && !latest?.package && !latest?.sent_at,
    packageReady, packageUnsent: !!latest?.package && !latest.sent_at, amendment: contract.contract_type === "AMENDMENT",
  });
  /** Where the act lives: switch to its tab first, then ask its pane. */
  const go = (kind: StepKind, tab: "document" | "changes") => {
    if (view !== tab) { onView(tab); window.setTimeout(() => runStep(kind), 60); } else runStep(kind);
  };
  let primary: React.ReactNode = null;
  if (step && reviewId && assign && step.kind === "sendToLegal") {
    primary = <SendToLegal reviewId={reviewId} data={assign} onChange={setAssign} label={step.label} primary />;
  } else if (step && step.kind === "recordSigning") {
    primary = <RecordSigning contractId={contract.id} label={step.label} primary onSigned={onReload}
                             versions={contract.document_versions} />;
  } else if (step && latest && (step.kind === "sendReply" || step.kind === "sendToClient"
                                 || step.kind === "sendForSignature")) {
    primary = <SendOut version={latest} label={step.label} onSent={onReload} />;
  } else if (step) {
    const tab = step.kind === "decide" ? "document" : "changes";   // preparePackage: Changes
    primary = (
      <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => go(step.kind, tab)}>
        {step.label}
      </button>
    );
  }
  const owned = contract.owner_id === identity?.user_id;
  return (
    <PageHeader wide title={contractDisplayName(contract.name)} back={{ href: "/contracts", label: "Contracts" }}
      meta={<>
        {contract.negotiation_stage ? (
          <StageBadge stage={contract.negotiation_stage} counts={contract.counts} viewer={viewer} />
        ) : null}
        {/* P-1: the contract's own declared state (Draft / Active / Superseded), read back in
            words beside the deal stage (restored 2026-11-05). Once signed, the stage says it
            and a declared "Draft" beside "Signed" would contradict it, so it is not shown. */}
        {signedAt ? null : (
          <span className="ws-record__status" title="Contract status, as declared">
            {contractStatusLabel(contract.status)}
          </span>
        )}
        <GovernedByLink contract={contract} />
        {/* AB-13 r7 — the LINKED company wins; linked, it opens every document for it */}
        {company ? (
          <button type="button" className="ws-linkbtn" onClick={onCompany}>{company.name}</button>
        ) : version?.counterparty ? (
          <span title="Client, as declared for this version">{version.counterparty}</span>
        ) : null}
        {/* AB-13: the declared effective date, said where the reader reads (absent when undeclared) */}
        {version?.effective_date ? (
          <span title="Effective date, as declared">Effective {shortDate(version.effective_date)}</span>
        ) : null}
        <span className="ws-record__owner">Owned by <strong>{owned ? "you" : contract.owner_name ?? "—"}</strong></span>
        {holder ? (
          <span className="ws-send">
            With <strong>{holder.name || holder.email}</strong> since {shortDate(holder.assigned_at)}
            {assign?.can_send && reviewId ? (
              <button type="button" className="ws-linkbtn"
                      onClick={() => void api.withdrawReview(reviewId, holder.user_id)
                        .then(({ assigned }) => setAssign({ ...assign, assigned })).catch(() => undefined)}>
                Withdraw
              </button>
            ) : null}
          </span>
        ) : null}
        {signedAt ? <span className="lm-signed-on">Signed on {shortDate(signedAt)}</span> : null}
      </>}
      secondary={<>
        {secondary}
        {/* in the actions row, not the meta line: it arrives after its own fetch, and on a
            phone the meta line wrapped it onto a new row — the page jumped (CLS) */}
        <CollaboratorsControl contractId={contract.id} />
        {signedAt ? <RecordSigning contractId={contract.id} label="Signing record" onSigned={onReload}
                                   versions={contract.document_versions} /> : null}
        {canSendToLegal && reviewId && assign && step?.kind !== "sendToLegal" ? (
          <SendToLegal reviewId={reviewId} data={assign} onChange={setAssign} label={ACTION.sendToLegal} />
        ) : null}
      </>}
      primary={primary}>
      {children}
    </PageHeader>
  );
}

/** Send to Legal (AB-100): a button that opens a picker of the people who may review —
 *  never a styled native select (MED 8). The list is the server's (only people holding
 *  both legal roles, never the owner); the server checks the send again. */
function SendToLegal({ reviewId, data, onChange, label, primary = false }: {
  reviewId: string; data: ReviewAssignments; onChange: (next: ReviewAssignments) => void;
  label: string; primary?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState(data.eligible[0]?.user_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useStep("sendToLegal", useCallback(() => setOpen(true), []));
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const { assigned } = await api.sendForReview(reviewId, pick);
      onChange({ ...data, assigned });
      setOpen(false);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="lm-sendlegal"
          onKeyDown={(event) => { if (event.key === "Escape" && open) { event.stopPropagation(); setOpen(false); } }}>
      <button type="button" className={`ws-btn ws-btn--sm${primary ? " ws-btn--primary" : ""}`}
              aria-expanded={open} aria-controls="lm-sendlegal" onClick={() => setOpen((v) => !v)}>
        {label}
      </button>
      {open ? (
        <div className="lm-sendlegal__pop" id="lm-sendlegal" role="dialog" aria-label={label}>
          <fieldset>
            <legend>Who reviews it</legend>
            {data.eligible.map((person, i) => (
              <label key={person.user_id}>
                <input type="radio" name="lm-sendlegal" value={person.user_id} checked={pick === person.user_id}
                       autoFocus={i === 0} onChange={() => setPick(person.user_id)} />
                <span className="lm-sendlegal__who">
                  {person.name || person.email}
                  {person.name ? <small>{person.email}</small> : null}
                </span>
              </label>
            ))}
          </fieldset>
          {error ? <p className="cx-error" role="alert">{error}</p> : null}
          <div className="lm-sendlegal__foot">
            <button type="button" className="ws-btn ws-btn--sm" onClick={() => setOpen(false)}>Cancel</button>
            <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" disabled={busy || !pick}
                    onClick={() => void send()}>
              {busy ? "Sending…" : label}
            </button>
          </div>
        </div>
      ) : null}
    </span>
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
    <Dialog onClose={onClose} titleId="ws-company-title">
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
                <Link href={`/dashboard?id=${c.id}`} onClick={onClose}>{contractDisplayName(c.name)}</Link>
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
    </Dialog>
  );
}

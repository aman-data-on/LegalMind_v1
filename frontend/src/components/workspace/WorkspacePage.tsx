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
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { chainAnalysis } from "@/lib/analysisChain";
import { ApiError, api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty, DocumentVersion } from "@/lib/types";
import { ACTION, MENU_COPY, READER_OUTDATED } from "@/lib/labels";
import { runStep } from "@/lib/nextStep";
import { documentSourceChip, isOurs } from "@/lib/documentTypes";

import { Dialog } from "@/components/Dialog";

import { AnalysisPanel } from "./AnalysisPanel";
import { AskDockLazy } from "./AskDockLazy";
import { AskIntentProvider } from "./askIntent";
import { ChangesPane, ReplyNotice, useClientChanges } from "./ChangesPane";
import { ConvertPaper } from "./ConvertPaper";
import { PackageBar, PackageCard, usePackagePlan, usePreparedEntries } from "./Package";
import { FillInFields } from "./FillInFields";
import { AmendmentsPanel } from "./Amendments";
import { AMENDMENT_PLACE, convertOffered, packageLine } from "@/lib/package";
import { WEBSITE_KEY_BY_TYPE } from "@/components/diff-talk/text";
import { DocumentPane } from "./DocumentPane";
import { FindingsPane } from "./FindingsPane";
import { FindingsProvider, primeReviews } from "./findingsState";
import { HighlightProvider } from "./highlight";
import { contractHref, contractTabFromPath, phoneView, pickVersion, stageViewer, versionRoleLabel } from "./model";
import { CompanyDocuments, RecordHeader, ReportMenuItem, ReportTabGate, ReportView, versionOption,
         type View } from "./WorkspaceHeader";
import { DealBrief } from "./DealBrief";
import { FinalCard, FinalCheckFailed, PrepareFinal, ClosedPanel } from "./FinalCopy";
import { UploadDocument } from "./UploadDocument";
import { VersionComparison } from "./VersionComparison";
import { PaneBoundary } from "./PaneBoundary";
import { IconUploadCloud, IconX } from "./icons";
import { PhoneBar, WorkspaceLayout, arrowTab, useMinWidth, type PhoneView, type Region } from "./WorkspaceLayout";
import { EmptyState, ErrorState, NoticeState } from "@/components/Feedback";

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

/** `/contracts/{id}/changes` (`AM-263`) — or the older `?tab=changes` — opens the client's changes
 *  (CLM Phase 1, UX §3.4). The router's path, not `window.location`: an in-app navigation renders
 *  the page before the address bar changes (batch 5: "Upload and compare" landed on Document). */
function initialView(path: string, params: { get: (key: string) => string | null }): View {
  const tab = contractTabFromPath(path).tab;
  return tab === "changes" || tab === "report" ? tab : params.get("tab") === "changes" ? "changes" : "document";
}

export function WorkspacePage({ contractId }: { contractId: string }) {
  const params = useSearchParams(), path = usePathname();   // S5: ?convert_draft= back from New contract
  const { can, identity } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [view, setView] = useState(() => initialView(path, params));
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
  const uploadReturn = useRef<HTMLElement | null>(null);
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
  // B6: the same silent re-read after every other write on this page (Send to Legal,
  // Withdraw, a Legal Decision) — the server's numbers, never an optimistic guess
  const refreshSeq = useRef(0);
  const refresh = useCallback(() => {
    const mine = ++refreshSeq.current;
    return api.contract(contractId).then((fresh) => {
      if (mine !== refreshSeq.current) return;          // a later re-read wins
      setState((prev) => prev.kind === "ready" ? { ...prev, contract: { ...prev.contract,
        counts: fresh.counts, negotiation_stage: fresh.negotiation_stage } } as Load : prev);
    }).catch(() => { /* the last counts stand until the next load */ });
  }, [contractId]);
  const listed = changesFeed.state.kind === "ready" ? changesFeed.state.list : null;
  const firstList = useRef<unknown>(null);
  useEffect(() => {
    if (!listed) return;
    if (firstList.current === null) { firstList.current = listed; return; }
    refresh();
  }, [listed, refresh]);
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
      // 49.5 r1 / 52.4: "Not found" is the one answer for every cause; the way back is the
      // nav word (Contracts). A failure offers Try again and the same way back.
      <div className="lm-page">
        {notFound ? (
          <EmptyState heading="h1" title="Not found" body="Go back to your contracts to find the one you need."
                      action={<Link className="ws-btn ws-btn--primary" href="/contracts">Go to Contracts</Link>} />
        ) : (
          <ErrorState heading="h1" title="This contract could not be opened" error={state.error}
                      onRetry={() => void load()} back={{ href: "/contracts", label: "Go to Contracts" }} />
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
  function chooseView(which: View) {
    setView(which);
    const url = new URL(window.location.href);
    url.searchParams.delete("tab");
    if (which !== "document") url.searchParams.delete("evidence");   // a document-view focus only
    if (url.pathname.startsWith("/contracts/")) {
      url.pathname = contractHref(contract.id, which === "document" ? undefined : which);
    } else if (which === "changes") url.searchParams.set("tab", "changes");
    window.history.replaceState(window.history.state, "", url);
  }

  // The header's ONE primary action is the next step at this stage (CLM UI pass 2);
  // whatever it does not take is a quiet item under "More". Every control here is
  // shown only to someone who may use it — the server checks each write again.
  const changeList = changesFeed.state.kind === "ready" ? changesFeed.state.list : null;
  const stageCode = contract.negotiation_stage?.stage;
  const amendment = contract.contract_type === "AMENDMENT";        // AM-310
  // a signed contract takes no new version — the server refuses it (409); changes go in an amendment
  const signed = stageCode === "SIGNED" || versions.some((v) => v.version_role === "FINAL_SIGNED");
  /** what a version IS, in the header's and the version menu's words */
  const roleOf = (v: DocumentVersion) => versionRoleLabel(v, versions) ?? documentSourceChip(v.source);
  const canUpload = !!version && !signed && can(P.DOCUMENT_UPLOAD) && contract.owner_id === identity?.user_id;
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
  // U2 r4: the ⋯ menu in groups — the file, comparing, sharing (the header adds the rest)
  const files: React.ReactNode[] = [], comparing: React.ReactNode[] = [], sharing: React.ReactNode[] = [];
  if (canUpload) {
    files.push(<button key="up" type="button" role="menuitem" className="ws-menu__item"
                          onClick={(event) => {
                            // the item unmounts with the menu: the dialog hands focus back to ⋯
                            uploadReturn.current = event.currentTarget.closest(".ws-menu")
                              ?.querySelector<HTMLElement>(".ws-menu__toggle") ?? null;
                            uploadToggle();
                          }}>Upload new version</button>);
  }
  if (versions.length > 1) {
    comparing.push(<button key="cmp" type="button" role="menuitem" className="ws-menu__item"
                          onClick={() => setCompareOpen((open) => !open)}>
      {compareOpen ? MENU_COPY.hideCompare : MENU_COPY.compare}</button>);
  }
  // B3 p7: the phone chooses a version in the header select, not in ⋯
  // N5: our own version downloads from ⋯ at any stage — said to be a draft while a point
  // is open; the server still gates a reply or final contract with an open point (AM-293)
  if (version && can(P.DOCUMENT_DOWNLOAD) && !version.reply && !version.package && !version.final_copy) {
    const draft = (contract.counts?.points_open ?? 0) > 0 && isOurs(version);
    files.push(<a key="dl" role="menuitem" className="ws-menu__item"
                     href={`/api/v1/document-versions/${encodeURIComponent(version.id)}/content`} download>
      {MENU_COPY.download(version.version_number, version.mime_type, draft)}</a>);
  }
  // AM-318 A4: the client accepted our version as it was — its final copy
  const ourLatest = !!latest && latest.version_role === "COMPANY_DRAFT" && !latest.package && !latest.final_copy;
  if (ourLatest && canAnswer && (stageCode === "WITH_CLIENT" || stageCode === "READY_TO_SEND"
                                     || stageCode === "DRAFTING")) {
    files.push(<button key="fin" type="button" role="menuitem" className="ws-menu__item"
                          onClick={() => runStep("prepareFinal")}>
      Prepare final contract (client accepted version {latest!.version_number})</button>);
  }
  const canAmend = (stageCode === "FINAL" || stageCode === "SIGNED") && contract.contract_type !== "AMENDMENT"
    && !contract.governed_by && !contract.archived_at && can(P.CONTRACT_CREATE) && can(P.CONTRACT_UPDATE);
  if (canAmend && view === "document") {
    files.push(<button key="amd" type="button" role="menuitem" className="ws-menu__item"
                          onClick={() => runStep("startAmendment")}>{ACTION.startAmendment}</button>);
  }
  if (stageCode === "FINAL" || stageCode === "SIGNED") {
    files.push(<Link key="terms" role="menuitem" className="ws-menu__item"
                        href={`/contracts/${contract.id}/terms`}>Terms in force</Link>);
  }
  // U2 (UI-13): the report is the third tab wherever the tabs show; else (a phone's bar, a
  // contract with no Changes tab) it stays under ⋯
  if (version && (phone || !changesFeed.enabled)) sharing.push(<ReportMenuItem key="rep" onOpen={() => chooseView("report")} />);
  sharing.push(<button key="link" type="button" role="menuitem" className="ws-menu__item"
                        onClick={copyLink}>Copy link</button>);
  if (version) {
    // Diff-Talk (owner, 2026-10-12): this document on the right; on the left its
    // type's website document when there is one.
    comparing.push(<Link key="dt" role="menuitem" className="ws-menu__item" href={`/dashboard/diff?${new URLSearchParams({
      left: WEBSITE_KEY_BY_TYPE[contract.contract_type ?? ""] ?? "", right: version.id })}`}>
      {MENU_COPY.compareTemplate}</Link>);
  }

  const overflow = [files, comparing, sharing].filter((g) => g.length)
    .flatMap((g, i) => i ? [<div key={`sep${i}`} role="separator" className="ws-menu__sep" />, ...g] : g);

  const fillIn = <FillInFields contractId={contract.id} onSaved={() => { openVersion(null); void load(); }} />;

  /** One tap on the phone's bar: a region, the Changes view, or Ask's sheet. */
  const choosePhone = (which: PhoneView) => {
    setPhoneAsk(false);
    // U2 r2: Changes is its own view; every region (and Ask) lives on Document — so a tap
    // leaves the Report view too, never only the Changes one
    const next = phoneView(which);
    if (view !== next) chooseView(next);
    if (which === "changes") return;
    setPhoneTab(which);
    window.scrollTo({ top: 0 });
  };
  const openPhoneAsk = () => {
    if (view !== phoneView("ask")) chooseView("document");
    setPhoneAsk(true);
    setPhoneAskSeq((n) => n + 1);
  };

  return (
    <HighlightProvider>
    <AskIntentProvider>
    <MaybeFindings contractId={contract.id} ownerId={contract.owner_id} version={version}
                   signed={signed} onChanged={refresh}>
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
                    versionMeta={version && (!phone || versions.length > 1) ? (versions.length > 1 ? (
                      <select className="ws-version" aria-label="Version" value={version.id}
                              onChange={(event) => openVersion(event.target.value)}>
                        {versions.map((v) => (
                          <option key={v.id} value={v.id}>
                            {versionOption(v.version_number,
                                           roleOf(v),
                                           v.id === latest?.id, versions.length)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="ws-version">
                        {versionOption(version.version_number, roleOf(version), false)}
                      </span>
                    )) : null}
                    onCompany={() => setCompanyOpen(true)} onView={chooseView} onReload={() => void load()} onRefresh={refresh}
                    secondary={<>
                      {copied ? <span className="ws-record__copied" role="status">{copied}</span> : null}
                      {/* prelaunch U2: while the paper is with the client, the owner's next act
                          (their reply) is in sight, never only under ⋯; not primary — it is
                          the client's turn */}
                      {canUpload && stageCode === "WITH_CLIENT" ? (
                        <button type="button" className="ws-btn ws-btn--sm" onClick={uploadToggle}>
                          Upload the client&rsquo;s reply</button>
                      ) : null}
                    </>} overflow={overflow}
                    brief={version ? (who) => (
                      <DealBrief contractId={contract.id} stage={contract.negotiation_stage ?? null} viewer={viewer}
                                 refreshKey={`${JSON.stringify(contract.counts ?? {})}${stageCode ?? ""}${
                                   changeList?.changes.map((c) => c.told?.tie ?? "").join() ?? ""}`}
                                 who={who} onChanges={() => chooseView("changes")}
                                 onOpen={() => chooseView("changes")} onChanged={changesFeed.reload} />) : undefined}>
      {version && !phone && changesFeed.enabled ? (
        <div className="ws-record__bar">
          <ReportTabGate>{(reportTab) => (
          <div className="ws-record__tabs" role="tablist" aria-label="Contract views">
            {(reportTab ? ["document", "changes", "report"] as const : ["document", "changes"] as const).map((which, index, all) => {
              // the badge is what is left for THIS reader (`counts`), never the total
              const mine = which === "changes" ? contract.counts?.changes_left_for_me : undefined;
              return (
                <button key={which} type="button" role="tab" id={`ws-viewtab-${which}`}
                        aria-selected={view === which} aria-controls={`ws-view-${which}`}
                        tabIndex={view === which ? 0 : -1}
                        onClick={() => chooseView(which)}
                        onKeyDown={(event) => arrowTab(event, index, all.length, (i) => chooseView(all[i]!))}>
                  {which === "document" ? "Contract" : which === "changes" ? "Changes" : "Report"}
                  {mine ? <span className="ws-filter__n" aria-label={`${mine} yours`}>{mine}</span> : null}
                </button>
              );
            })}
          </div>)}</ReportTabGate>
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

      {reuploadOpen && version && !signed ? (
        <Dialog onClose={() => setReuploadOpen(false)} titleId="ws-reupload-title"
                returnFocus={() => uploadReturn.current}>
          <div className="ws-upload-dialog">
            <div className="ws-upload-dialog__head">
              <span className="ws-upload-dialog__icon" aria-hidden="true"><IconUploadCloud size={22} /></span>
              <div className="ws-upload-dialog__headtext">
                <h2 id="ws-reupload-title">Upload a new version</h2>
                <p className="ws-modal__body">
                  It becomes version {(latest?.version_number ?? version.version_number) + 1} and is reviewed on its own. Earlier versions don&rsquo;t change.
                </p>
              </div>
              <button type="button" className="ws-upload-dialog__close" aria-label="Close"
                      onClick={() => setReuploadOpen(false)}>
                <IconX size={18} />
              </button>
            </div>
            <UploadDocument
              contractId={contract.id}
              // with the client, what comes back is theirs; otherwise the reader says
              roleDefault={stageCode === "WITH_CLIENT" || stageCode === "FINAL" ? "CLIENT_MODIFIED" : ""}
              submitLabel={`Upload version ${(latest?.version_number ?? version.version_number) + 1}`}
              onUploaded={async () => {
                // The revised version gets the same in-flow analysis as a first
                // upload (one loop, not two journeys) — best-effort, the findings
                // pane explains any real blocker.
                await chainAnalysis(contract.id, can(P.REVIEW_CREATE));
                setReuploadOpen(false);
                openVersion(null); // land on the newest version
              }}
              onCancel={() => setReuploadOpen(false)}
            />
          </div>
        </Dialog>
      ) : null}

      {/* the view the record's tabs choose (WAI-ARIA tabpanel; `display: contents`, so the
          workspace's own layout is untouched) */}
      {/* #9: the unselected tab's panel stays in the DOM, hidden, so its aria-controls resolves */}
      {version && !phone && changesFeed.enabled ? (["document", "changes", "report"] as const).filter((w) => w !== view).map((w) => (
        <div key={w} role="tabpanel" hidden id={`ws-view-${w}`} aria-labelledby={`ws-viewtab-${w}`} />
      )) : null}
      <div className="ws-viewpanel" {...(version && !phone && changesFeed.enabled
        ? { role: "tabpanel", id: `ws-view-${view}`, "aria-labelledby": `ws-viewtab-${view}` } : {})}>
      {/* AM-293: the reply's banner (its files, "send it") only once nothing is open —
          at Ready to send, or once it went out. While a point is open the stage reads
          With Legal and nothing here offers it as sendable. */}
      {/* U2 (UI-03c): the version's banner and the fill-in fields are ONE strip over the panes */}
      <div className="ws-docstrip">
      {version && view === "document" && version.reply
        && (version.sent_at || stageCode === "READY_TO_SEND") ? (
        <ReplyNotice version={version} versions={versions} canSend={!!changeList?.can_send && viewer !== "legal"} />
      ) : null}
      {version && view === "document" && stageCode === "FINAL" && isLatest ? (
        <FinalCard version={version} versions={versions} since={contract.negotiation_stage!.since}
                   owner={viewer !== "legal" && canAnswer} />
      ) : version && view === "document" && version.package ? (
        <PackageCard version={version} versions={versions}
                     filesOpen={stageCode === "READY_TO_SEND" || stageCode === "READY_TO_SIGN" || stageCode === "SIGNED"} />
      ) : null}
      {/* r4 (owner: one strip): the fill-in fields stay in the strip on a phone too, one row */}
      {view === "document" ? fillIn : null}
      </div>
      {version && view === "document" && isLatest ? <FinalCheckFailed version={version} /> : null}
      {view === "document" ? <AmendmentsPanel contract={contract} canStart={canAmend} /> : null}
      {/* B3 page 1: an old Markdown reading keeps its marks; a pinned reading is never re-read
          (rules 16/17), so the way out is the same file as a new version */}
      {version && versions.find((v) => v.id === version.id)?.reader_outdated ? (
        <NoticeState title={READER_OUTDATED.title} body={READER_OUTDATED.body}>
          {canUpload ? (
            <button type="button" className="ws-btn" onClick={uploadToggle}>Upload new version</button>
          ) : null}
        </NoticeState>
      ) : null}
      {version ? (
        <PrepareFinal contractId={contract.id} nextVersion={(latest?.version_number ?? 0) + 1}
                      onPrepared={() => { setView("document"); openVersion(null); }} />
      ) : null}

      {version && view === "report" ? (
        <ReportView />
      ) : version && changesFeed.enabled && view === "changes" && stageCode === "FINAL" ? (
        <ClosedPanel what="changes" />
      ) : version && changesFeed.enabled && view === "changes" ? (
        <ChangesPane contractId={contract.id} versions={versions} changes={changesFeed}
                     onVersionCreated={() => { setView("document"); openVersion(null); }}
                     packageBar={changeList && convertOffered(changeList)
                       ? (onPick: (rowKey: string) => void) => (   // S5: client paper → ours
                         <ConvertPaper contractId={contract.id} draftId={params.get("convert_draft")} onPick={onPick}
                                       onConverted={() => { setView("document"); openVersion(null); }} />)
                       : pkg.plan ? (onPick: (rowKey: string) => void) => (
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
            findings={<PaneBoundary what="The points">{stageCode === "FINAL" && isLatest
              ? <ClosedPanel what="points"><FindingsPane version={version} /></ClosedPanel>
              : <FindingsPane version={version} />}</PaneBoundary>}
            analysis={<PaneBoundary what="The summary"><AnalysisPanel documentVersionId={version.id}
                                     signedCopy={version.version_role === "FINAL_SIGNED"}
                                     referenceCopy={!!version.reference_copy_of}
                                     stage={contract.negotiation_stage ?? null}
                                     viewer={stageViewer(can, contract.owner_id === identity?.user_id)}
                                     isOwner={contract.owner_id === identity?.user_id}
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
      </div>
      {phone && version ? (
        <PhoneBar view={view === "changes" ? "changes" : view === "report" ? null : phoneTab} onView={choosePhone}
                  changesBadge={changesFeed.enabled ? (contract.counts?.changes_left_for_me ?? null) : undefined}
                  askOpen={phoneAsk && view !== "changes"} onAsk={openPhoneAsk} />
      ) : null}
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
  ownerId,
  version,
  signed,
  onChanged,
  children,
}: {
  contractId: string;
  ownerId: string;
  version: DocumentVersion | null;
  signed: boolean;
  onChanged: () => void;
  children: React.ReactNode;
}) {
  if (!version) return <>{children}</>;
  return (
    <FindingsProvider contractId={contractId} ownerId={ownerId} version={version} signed={signed} onChanged={onChanged}>
      {children}
    </FindingsProvider>
  );
}

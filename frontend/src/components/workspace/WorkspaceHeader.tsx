"use client";

/**
 * The contract page's header and its parts (U2, 2026-11-24 — split out of
 * `WorkspacePage.tsx`, UI-34): the record header with its ONE meta row, the deal brief's
 * "who has it", the ⋯ menu with "Take back from Legal", the phone's folded bar, the
 * Report tab, and the company's documents. Presentation only; every write checks again
 * server-side (rule 18).
 */

import dynamic from "next/dynamic";
import { loadReport } from "./paneLoaders";
import Link from "@/components/AppLink";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty, DocumentVersion, ReviewAssignments, SentNote } from "@/lib/types";
import { ACTION, BRIEF_COPY, MENU_COPY, REPORT_VIEW_COPY, TAKE_BACK_COPY, contractStatusLabel,
         type StageViewer } from "@/lib/labels";
import { canSendToLegalFor, nextStep, runStep, type StepKind } from "@/lib/nextStep";
import { PageHeader } from "@/components/page/PageHeader";
import { isOurs } from "@/lib/documentTypes";
import { Dialog } from "@/components/Dialog";
import { Disclosure } from "@/components/Disclosure";
import { EmptyState, ErrorState, LoadingState } from "@/components/Feedback";
import { templateName } from "@/lib/templates";
import { ClientMenu } from "@/components/clients/ClientWorkspace";

import { GovernedByLink } from "./Amendments";
import { SendOut } from "./changesFeed";
import { CollaboratorsControl } from "./CollaboratorsControl";
import { ExportControl } from "./ExportControl";
import { useFindingsState, useFindingsStateOptional } from "./findingsState";
import { shortDate } from "./model";
import { RecordSigning } from "./SigningSheet";
import { SendToLegal } from "./SendToLegal";
import { StageBadge } from "./StageBadge";
import { TakeBackFromLegal } from "./TakeBackFromLegal";
import { IconCheck } from "./icons";
import { useMinWidth } from "./WorkspaceLayout";

export type View = "document" | "changes" | "report";

/** The steps whose own control (dialog or picker) registers with `useStep` and opens itself. */
const SELF_OPENING = new Set<StepKind>(["sendToLegal", "sendReply", "sendToClient", "downloadFinal"]);

/** A version as the header names it: "Version 2 of 3, client's markup (latest)" — no
 *  middot (page 2). `of` only where versions are chosen between. */
export function versionOption(n: number, role: string | null | undefined, latest: boolean, of?: number): string {
  return `Version ${n}${of ? ` of ${of}` : ""}${role ? `, ${role.charAt(0).toLowerCase()}${role.slice(1)}` : ""}`
    + (latest ? " (latest)" : "");
}

/** The report, under ⋯: it opens the report view, where PDF and Word download beside the
 *  preview (owner, 2026-10-22). Absent until the Review exists (no fake control). */
export function ReportMenuItem({ onOpen }: { onOpen: () => void }) {
  const { state } = useFindingsState();
  const { can } = useSession();
  if (state.kind !== "ready") return null;
  if (!can(P.REPORT_VIEW)) return null;
  // U2 r4: the report view of this page (/contracts/{id}/report), the same as the tab
  return <button type="button" role="menuitem" className="ws-menu__item" onClick={onOpen}>{MENU_COPY.report}</button>;
}

/** U2 (UI-13): "Report" is the third view once the Review exists and the reader may see it
 *  (the same test the old menu item made — no tab that opens nothing). */
export function ReportTabGate({ children }: { children: (shown: boolean) => React.ReactNode }) {
  const findings = useFindingsStateOptional();
  const { can } = useSession();
  const kind = findings?.state.kind;
  // r4: the tab shows once the report is ready — never a tab that opens nothing
  return <>{children(can(P.REPORT_VIEW) && kind === "ready")}</>;
}

/** The Report tab: the report a reader downloads, shown before it is downloaded (AB-103),
 *  under the workspace's own header; read-only. */
// W2-3: the report loads when the Report tab first opens
// …with the report's own first state as its placeholder: one skeleton, the same height (W2 r2)
const ReportDocument = dynamic(() => loadReport().then((m) => m.ReportDocument),
                               { loading: () => <LoadingState label={REPORT_VIEW_COPY.preparing} rows={6} /> });

export function ReportView() {
  const { state } = useFindingsState();
  // r4: the address works before the report does — each state says what is true
  if (state.kind === "loading") return <LoadingState label={REPORT_VIEW_COPY.loading} rows={6} />;
  if (state.kind === "in-flight" || state.kind === "not-started") {
    return <LoadingState label={REPORT_VIEW_COPY.checking} rows={6} />;
  }
  if (state.kind === "failed" || state.kind === "error") {
    return <div className="ws-reportview"><ErrorState heading="h2" title={REPORT_VIEW_COPY.failedTitle}
                                                      fix={REPORT_VIEW_COPY.failedBody} /></div>;
  }
  if (state.kind !== "ready") {
    return <div className="ws-reportview"><EmptyState heading="h2" title={REPORT_VIEW_COPY.noneTitle}
                                                      body={REPORT_VIEW_COPY.noneBody} /></div>;
  }
  return (
    <div className="ws-reportview">
      <div className="ws-reportview__bar"><ExportControl reviewId={state.review.id} /></div>
      <ReportDocument reviewId={state.review.id} />
    </div>
  );
}

/** The contract page's header (cross-page pass): `PageHeader` with the deal's facts and the
 *  ONE primary step `nextStep` resolves for this reader from the server's stage, counts
 *  and permissions. The pane that owns each act does it (`useStep`); this only asks. */
export function RecordHeader({
  contract, latest, version, view, viewer, canAnswer, company, onCompany, onView, onReload, onRefresh, secondary, children,
  packageReady = false, versionMeta, overflow, brief,
}: {
  /** the ⋯ menu's items; the header adds "Take back from Legal" (U2, UI-13) */
  overflow: React.ReactNode[];
  /** the deal brief, handed who has it and the note (U2, UI-03: out of the meta line) */
  brief?: ((who: React.ReactNode) => React.ReactNode) | undefined;
  packageReady?: boolean;
  /** which version is on screen (and, with more than one, the choice between them) */
  versionMeta?: React.ReactNode;
  contract: Contract; latest: DocumentVersion | null; version: DocumentVersion | null;
  view: View; viewer: StageViewer; canAnswer: boolean; company: Counterparty | null;
  onCompany: () => void; onView: (which: View) => void; onReload: () => void; onRefresh: () => Promise<void>;
  secondary: React.ReactNode; children: React.ReactNode;
}) {
  const { identity } = useSession();
  const findings = useFindingsStateOptional();
  const reviewId = findings && findings.state.kind === "ready" ? findings.state.review.id : null;
  const [assign, setAssign] = useState<ReviewAssignments | null>(null);
  // r4: a failed read says so, with Try again — never a silent absence of "Send to Legal"
  const [assignFailed, setAssignFailed] = useState(false);
  const [assignSeq, setAssignSeq] = useState(0);
  useEffect(() => {
    if (!reviewId) return;
    let cancelled = false;
    api.reviewAssignments(reviewId).then((got) => { if (!cancelled) { setAssign(got); setAssignFailed(false); } },
                                         () => { if (!cancelled) setAssignFailed(true); });
    return () => { cancelled = true; };
  }, [reviewId, assignSeq]);
  /** B6: who holds the review changed — the stage, the counts and the Summary are read
   *  again from the server, so "Send to client" or "not sent yet" never wait for a reload */
  const assigned = (next: ReviewAssignments) => {
    setAssign(next);
    findings?.refresh();
  };
  const signedAt = contract.negotiation_stage?.stage === "SIGNED" ? contract.negotiation_stage.since : null;
  const stageNow = contract.negotiation_stage?.stage;
  // N15: who holds the review is said only while it is with them — never once Legal
  // finished or the deal moved on
  const holder = stageNow === "INTERNAL_REVIEW" ? assign?.assigned[0] : undefined;
  // AM-318: the final contract waits on Legal's decision on the contract
  const finalLatest = !!latest && !!(latest.package || latest.final_copy);
  // only with something for Legal to decide, and never while the paper is with the client
  // D1: "already with Legal" holds at every stage, from the server's one fact
  const canSendToLegal = canSendToLegalFor({ stage: stageNow, counts: contract.counts, finalLatest, assign });
  const ours = isOurs(latest);
  const owned = contract.owner_id === identity?.user_id;
  const changesForMe = contract.counts?.changes_left_for_me ?? 0;
  // LA-18: "Answer changes" leads only for whoever the To-do gives the changes to — the
  // owner or a collaborator (`AM-259`); asked only when it can matter
  const [collaborator, setCollaborator] = useState(false);
  useEffect(() => {
    if (owned || !changesForMe || !identity) return;
    let cancelled = false;
    api.collaborators(contract.id)
      .then((got) => { if (!cancelled) setCollaborator(got.collaborators.some((p) => p.id === identity.user_id)); })
      .catch(() => { /* not one: the step stays secondary */ });
    return () => { cancelled = true; };
  }, [owned, changesForMe, identity, contract.id]);
  const stepWith = (sendToLegal: boolean) => findings?.reference ? null : nextStep({
    stage: contract.negotiation_stage?.stage, counts: contract.counts, viewer, canAnswer, canSendToLegal: sendToLegal,
    replyReady: !!latest?.reply && !latest.sent_at,
    draftUnsent: ours && !latest?.reply && !latest?.package && !latest?.sent_at,
    packageReady, packageUnsent: !!latest?.package && !latest.sent_at, amendment: contract.contract_type === "AMENDMENT",
    finalLatest, answersChanges: owned || collaborator,
  });
  const step = stepWith(canSendToLegal);
  // preparePackage: Changes; prepareFinal: the dialog on either tab
  const stepTab: "document" | "changes" = !step || step.kind === "decide" || step.kind === "recordDecision" ? "document"
    : step.kind === "prepareFinal" ? (view === "changes" ? "changes" : "document") : "changes";
  /** Where the act lives: switch to its tab first, then ask its pane. */
  const go = (kind: StepKind, tab: "document" | "changes") => {
    if (view !== tab) { onView(tab); window.setTimeout(() => runStep(kind), 60); } else runStep(kind);
  };
  let primary: React.ReactNode = null;
  if (step && reviewId && assign && step.kind === "sendToLegal") {
    primary = <SendToLegal reviewId={reviewId} data={assign} onChange={assigned} label={step.label} primary />;
  } else if (step && latest && (step.kind === "sendReply" || step.kind === "sendToClient"
                                 || step.kind === "downloadFinal")) {
    primary = <SendOut version={latest} label={step.label} onSent={onReload} />;
  } else if (step) {
    // r4: on the tab the step takes the reader to, it is no longer the page's primary —
    // the reader is already there (a quiet button keeps the shortcut)
    const here = stepTab === view;
    primary = (
      <button type="button" className={`ws-btn ws-btn--sm${here ? "" : " ws-btn--primary"}`}
              onClick={() => go(step.kind, stepTab)}>
        {step.label}
      </button>
    );
  }
  const [takingBack, setTakingBack] = useState(false);
  const colleaguesOpen = useRef<(() => void) | null>(null);
  const [colleagues, setColleagues] = useState<string | null>(null);
  // U2 (UI-03d): on a phone the header scrolls away and a bar with the name and the one
  // primary step stays — fixed, so its arrival moves nothing (no layout shift)
  const narrow = useMinWidth(900) === false;
  const [folded, setFolded] = useState(false);
  useEffect(() => {
    const title = narrow ? document.querySelector(".ws-record h1") : null;
    if (!title) return;
    // the title counts as gone once it is under the shell bar (taller on the narrowest phones)
    const shell = getComputedStyle(title).getPropertyValue("--ws-shell-h").trim() || "52px";
    const watch = new IntersectionObserver(([seen]) => setFolded(!seen!.isIntersecting),
                                           { rootMargin: `-${shell} 0px 0px 0px` });
    watch.observe(title);
    return () => watch.disconnect();
  }, [narrow]);
  const menuToggle = useRef<HTMLElement | null>(null);
  const items = [...overflow];
  // r4: a phone keeps "Add colleague" under ⋯ (the first screen is the contract's)
  if (narrow && colleagues) {
    items.push(<button key="colleagues" type="button" role="menuitem" className="ws-menu__item"
                       onClick={() => colleaguesOpen.current?.()}>{colleagues}</button>);
  }
  if (holder && assign?.can_send && reviewId) {
    items.push(<div key="sep-takeback" role="separator" className="ws-menu__sep" />);
    items.push(<button key="takeback" type="button" role="menuitem" className="ws-menu__item"
                       onClick={(event) => {
                         menuToggle.current = event.currentTarget.closest(".ws-menu")
                           ?.querySelector<HTMLElement>(".ws-menu__toggle") ?? null;
                         setTakingBack(true);
                       }}>{TAKE_BACK_COPY.open}</button>);
  }
  // U2 (UI-03): who has it, the note for Legal and where it was made from — the brief's
  // panel says them; the header keeps one meta row
  const notes = viewer === "legal" ? [] : assign?.notes ?? [];
  // r4: Legal reads the deal owner's note first, named as theirs (the owner's notes list is
  // the owner's alone; Legal has the note on its assignment)
  const forLegal = viewer === "legal" && holder?.note ? { text: holder.note, from: contract.owner_name ?? "" } : null;
  const who = holder || notes.some((n) => n.note) || contract.made_from ? (
    <WhoHasIt contract={contract} holder={holder} notes={notes} you={holder?.user_id === identity?.user_id}
              me={identity?.user_id} forLegal={forLegal} />) : null;
  return (
    <>
    {takingBack && holder && reviewId && assign ? (
      <TakeBackFromLegal reviewId={reviewId} holder={holder} onClose={() => setTakingBack(false)}
                         returnFocus={() => menuToggle.current}
                         onDone={(got) => { assigned({ ...assign, ...got }); return onRefresh(); }} />
    ) : null}
    {/* r4: only when there is a step to take; the step lives once — this asks it (`runStep`:
        the header's own dialog or picker opens, no scrolling and no second instance) */}
    {narrow && step && primary ? (
      <div className="ws-recordbar" hidden={!folded} aria-hidden={!folded || undefined}>
        <p className="ws-recordbar__title">{contract.name}</p>
        <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" tabIndex={folded ? 0 : -1}
                onClick={() => (SELF_OPENING.has(step.kind) ? runStep(step.kind) : go(step.kind, stepTab))}>
          {step.label}</button>
      </div>
    ) : null}
    <PageHeader wide title={contract.name} back={{ href: "/contracts", label: "Contracts" }}
      meta={<>
        {contract.negotiation_stage ? (
          <StageBadge stage={contract.negotiation_stage} counts={contract.counts} viewer={viewer} final={finalLatest}
                      unsent={canSendToLegal} ourTurn={!!step} />
        ) : null}
        {/* P-1: the contract's own declared state (Draft / Active / Superseded), read back in
            words beside the deal stage (restored 2026-11-05). Once signed, the stage says it
            and a declared "Draft" beside "Signed" would contradict it, so it is not shown. */}
        {/* the deal stage already says where a draft stands, so a declared "Draft" is said
            only when there is no stage; Active / Superseded add information and stay */}
        {signedAt || (contract.status === "DRAFT" && contract.negotiation_stage) ? null : (
          <span className="ws-record__status" title="Contract status, as declared">
            {contractStatusLabel(contract.status)}
          </span>
        )}
        {versionMeta}
        <GovernedByLink contract={contract} />
        {/* AB-13 r7 — the LINKED company wins; linked, it opens every document for it */}
        {company ? (
          <button type="button" className="ws-linkbtn" onClick={onCompany}>{company.name}</button>
        ) : version?.counterparty || contract.counterparty_id ? (   /* held while the client's name loads */
          <span title="Client, as declared for this version">{version?.counterparty ?? <span className="ws-record__hold" aria-hidden="true" />}</span>
        ) : null}
        {/* AB-13: the declared effective date, said where the reader reads (absent when undeclared) */}
        {version?.effective_date ? (
          <span title="Effective date, as declared">Effective {shortDate(version.effective_date)}</span>
        ) : null}
        {/* r4: one owner word — "Owner", as the report and the lists say it */}
        <span className="ws-record__owner">{BRIEF_COPY.ownerLabel} <strong>{owned ? "you" : contract.owner_name ?? "—"}</strong></span>
        {signedAt ? <span className="lm-signed-on"><IconCheck size={14} />Signed on {shortDate(signedAt)}</span> : null}
        {assignFailed ? (
          <span className="cx-error" role="alert">{BRIEF_COPY.assignFailed}{" "}
            <button type="button" className="ws-linkbtn" onClick={() => setAssignSeq((n) => n + 1)}>{BRIEF_COPY.retry}</button>
          </span>
        ) : null}
      </>}
      secondary={<>
        {secondary}
        <ClientMenu label="More actions">{items}</ClientMenu>
        {/* in the actions row, not the meta line: it arrives after its own fetch, and on a
            phone the meta line wrapped it onto a new row — the page jumped (CLS) */}
        <CollaboratorsControl contractId={contract.id} openRef={colleaguesOpen} onLabel={setColleagues} />
        {signedAt ? <RecordSigning contractId={contract.id} label="Signing record" onSigned={onReload}
                                   versions={contract.document_versions} /> : null}
        {canSendToLegal && reviewId && assign && step?.kind !== "sendToLegal" ? (
          <SendToLegal reviewId={reviewId} data={assign} onChange={assigned} label={ACTION.sendToLegal} />
        ) : null}
      </>}
      primary={primary}>
      {brief?.(who)}
      {children}
    </PageHeader>
    </>
  );
}

/** The brief panel's first block (U2, UI-03 / AM-473): who has the contract now and the
 *  owner's note for Legal — kept after a take-back, earlier notes one press away. The
 *  notes arrive only for the owner (the server omits them for anyone else). */
/** U2 r3: the note the panel leads with — the NEWEST send's, and only when that send had a
 *  note (what the re-send picker starts from too); while with Legal, only if not taken back.
 *  Older notes are "Earlier notes". */
export function leadNote(notes: SentNote[], holding: boolean): SentNote | null {
  const newest = notes[0];
  return newest?.note && (!holding || !newest.taken_back_at) ? newest : null;
}

/** Who wrote a note, when it was not the reader (a contract transferred since): else null. */
export function noteAuthor(n: SentNote, me: string | undefined): string | null {
  return n.by && n.by.user_id !== me ? n.by.name || n.by.email : null;
}

/** "Your note to Legal" only for the reader's own; "Note to Legal from {name}" otherwise;
 *  "(taken back {date})" once it was. */
export function noteHeading(n: SentNote, me: string | undefined): string {
  const from = noteAuthor(n, me);
  const back = n.taken_back_at ? shortDate(n.taken_back_at) : null;
  return from ? (back ? BRIEF_COPY.noteFromTaken(from, back) : BRIEF_COPY.noteFrom(from))
    : back ? BRIEF_COPY.yourNoteTaken(back) : BRIEF_COPY.yourNote;
}

function WhoHasIt({ contract, holder, notes, you, me, forLegal }: {
  contract: Contract; holder: ReviewAssignments["assigned"][number] | undefined; notes: SentNote[]; you: boolean;
  /** the reader: "Your note" only when they sent it (a transferred contract keeps its notes) */
  me: string | undefined;
  /** Legal's view: the owner's note on the assignment, said first */
  forLegal: { text: string; from: string } | null;
}) {
  const lead = leadNote(notes, !!holder);
  const earlier = notes.filter((n) => n.note && n !== lead);
  const whose = (n: SentNote) => noteAuthor(n, me);
  const heading = (n: SentNote) => noteHeading(n, me);
  if (!holder && !lead && !contract.made_from) return null;
  return (
    <div className="lm-briefwho">
      {forLegal ? (
        <>
          <h3 className="lm-brief__h">{forLegal.from ? BRIEF_COPY.noteFrom(forLegal.from) : BRIEF_COPY.noteFromOwner}</h3>
          <p className="lm-briefwho__note">{forLegal.text}</p>
        </>
      ) : null}
      {holder ? (
        <>
          <h3 className="lm-brief__h">{BRIEF_COPY.whoHasIt}</h3>
          <p className="lm-briefwho__line">{BRIEF_COPY.withSince(you ? "you" : holder.name || holder.email,
                                                                  shortDate(holder.assigned_at))}</p>
        </>
      ) : null}
      {lead ? (
        <>
          <h3 className="lm-brief__h">{heading(lead)}</h3>
          <p className="lm-briefwho__note">{lead.note}</p>
        </>
      ) : null}
      {earlier.length ? (
        <Disclosure className="lm-briefwho__earlier" summary={BRIEF_COPY.earlierNotes(earlier.length)}>
          <ul>{earlier.map((n) => (
            <li key={n.sent_at}>
              <span className="lm-brief__meta">{BRIEF_COPY.noteSent(n.to?.name || n.to?.email || "Legal", shortDate(n.sent_at))}
                {whose(n) ? `. ${BRIEF_COPY.noteFrom(whose(n)!)}` : ""}</span>
              <span className="lm-briefwho__note">{n.note}</span>
            </li>
          ))}</ul>
        </Disclosure>
      ) : null}
      {contract.made_from ? (
        <p className="lm-brief__meta">{BRIEF_COPY.madeFrom(contract.made_from.name ?? templateName(contract.made_from),
                                                           contract.made_from.version, !!contract.made_from.withdrawn)}</p>
      ) : null}
    </div>
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
export function CompanyDocuments({
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
    </Dialog>
  );
}

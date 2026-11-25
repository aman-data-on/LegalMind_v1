"use client";

/**
 * Batch 5 (AB-221): "Our contract came back marked up". One short form, its sections shown
 * in order: who it is with, which deal, the file they sent back and, for a new deal, whether
 * we hold the copy we sent. The server decides every refusal; this page keeps the person's
 * choices through each one and resumes at the step that failed (review M7). Presentation
 * only: no row, base or status is computed here (rule 18).
 */

import { DOCUMENT_FACES, useStartFaces } from "@/components/workspace/faces";
import Link from "@/components/AppLink";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { documentTypeChip } from "@/lib/documentTypes";
import { INTAKE_COPY, RETURNED_COPY as C, stageWords } from "@/lib/labels";
import * as P from "@/lib/permissions";
import {
  afterRefusal, copyRefusal, dealsShown, fileRefusal, missingOf, NEW_DEAL, openForReturn, refusalOf, sendReturned,
  singleFlight, type Made, type Missing, type SendStep,
} from "@/lib/returned";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty } from "@/lib/types";
import { hasTrackedChanges, sameFile } from "@/lib/upload";
import { ErrorState } from "@/components/Feedback";
import { FilePicker } from "@/components/FilePicker";
import { PageHeader } from "@/components/page/PageHeader";
import { IconInfo } from "@/components/workspace/icons";
import { contractHref } from "@/components/workspace/model";
import { UploadContractDialog } from "@/components/workspace/UploadContractDialog";

import { ClientPicker } from "./ClientPicker";
import "./newcontract.css";
import "./intake.css";

function focusSoon(id: string) {
  requestAnimationFrame(() => document.getElementById(id)?.focus());
}

/** UI 8: where an activation with something missing sends focus */
const MISSING_AT: Record<Missing, string> = { client: "nc-client-search", deal: "rm-deal-h", file: "rm-file-h", copy: "rm-base-h" };

/** UI 1: a recovery or warning note — it must read as a message, never a footnote */
export function Alert({ id, children, live }: { id?: string; children: React.ReactNode; live?: boolean }) {
  return (
    <p id={id} className="ic-note ic-note--alert" role={live ? "alert" : undefined} tabIndex={id ? -1 : undefined}>
      <IconInfo size={16} />
      <span>{children}</span>
    </p>
  );
}

export function ReturnedMarkup() {
  useStartFaces(DOCUMENT_FACES);   // W2-5 r2: this draws a document
  const { can } = useSession();
  const router = useRouter();
  const [client, setClient] = useState<Counterparty | null>(null);
  const [deal, setDeal] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [haveCopy, setHaveCopy] = useState(true);
  const [copy, setCopy] = useState<File | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copyTracked, setCopyTracked] = useState(false);
  const [noTracked, setNoTracked] = useState(false);
  const [step, setStep] = useState<SendStep | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [resumable, setResumable] = useState(false);     // UI 9: the copy we sent is already in
  const [dealProblem, setDealProblem] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const [asTheirs, setAsTheirs] = useState(false);
  const [dealsKey, setDealsKey] = useState(0);
  // R7: one run at a time, whatever the clicks; review M7: what is already in survives a retry
  const [flight] = useState(() => singleFlight((run: () => Promise<void>) => run()));
  const made = useRef<Made>({ contractId: null, copyIn: false });

  const isNew = deal === NEW_DEAL;
  // UI 29: a refused file is a missing file — the bar says so once
  const missing: Missing | null = fileError ? "file" : missingOf({ client, deal, file, haveCopy, copy });
  const busy = step !== null;

  function pickClient(c: Counterparty | null) {
    // S7: a new answer resets what depended on it, and focus goes where the next choice is
    setClient(c); setDeal(null); setDealProblem(null); setDuplicate(null); setNoTracked(false); setFailure(null);
    made.current = { contractId: null, copyIn: false };
    focusSoon(c ? "rm-deal-h" : "nc-client-search");
  }

  function pickFile(f: File | null) {
    setFile(null); setDuplicate(null); setNoTracked(false);
    const problem = f ? fileRefusal(f) : null;          // Q5: a PDF sends no request
    setFileError(problem);
    if (f && !problem) setFile(f);
  }

  async function pickCopy(f: File | null) {
    setCopy(null); setCopyTracked(false);
    setFileError((now) => (now === C.same ? null : now));   // a new copy answers "the same file"
    const problem = f ? copyRefusal(f) : null;
    setCopyError(problem);
    if (!f || problem) return;
    setCopy(f);
    made.current.copyIn = false;
    setCopyTracked(await hasTrackedChanges(f));          // S3: a warning, never a refusal
  }

  async function send() {
    if (busy) return;                                     // R7: busy until the result, even while landing
    if (missing) { focusSoon(MISSING_AT[missing]); return; }   // UI 8: say where, once
    if (!client || !file || !deal) return;
    setFailure(null); setDealProblem(null); setDuplicate(null); setNoTracked(false);
    let landed = false;                                   // a success keeps the bar busy
    try {
      if (isNew && haveCopy && copy && await sameFile(copy, file)) {
        setFileError(C.same); focusSoon("rm-file-err");   // M7: two picks of one file
        return;
      }
      const out = await sendReturned({ deal, clientId: client.id, clientName: client.name, file, copy, haveCopy,
                                       review: can(P.REVIEW_CREATE), made: made.current, onStep: setStep });
      if (out.duplicate) { setDuplicate(out.contractId); return; }
      landed = true;
      router.push(contractHref(out.contractId, "changes"));
    } catch (cause) {
      const next = afterRefusal(refusalOf(cause, !isNew));
      if (next.forgetDeal) made.current = { contractId: null, copyIn: false };   // archived by the refusal
      if (next.haveCopy) setHaveCopy(true);
      if (next.noTracked) setNoTracked(true);
      if (next.dropFile) setFile(null);
      if (next.fileError) setFileError(next.fileError);
      if (next.dealProblem) { setDeal(null); setDealProblem(next.dealProblem); setDealsKey((k) => k + 1); }
      if (next.failure) { setFailure(cause); setResumable(made.current.copyIn); }
      focusSoon(next.focus);
    } finally {
      if (!landed) setStep(null);
    }
  }
  const submit = () => void flight(send);

  const next = (
    <>
      <ol className="rm-next__list">{C.next.map((line) => <li key={line}>{line}</li>)}</ol>
      <p className="ic-quiet">{C.nothingSent}</p>
    </>
  );

  return (
    <div className="lm-page ic rm">
      <PageHeader wide title={C.title} back={{ href: "/contracts", label: "Contracts" }} />
      <p className="ic-lead">{C.lead}</p>
      <div className="ic-grid">
        <div className="ic-main">
          <section className="ic-section" aria-labelledby="rm-who">
            <h2 id="rm-who" className="ic-section__h">{INTAKE_COPY.whoTitle}</h2>
            <ClientPicker value={client} onChange={pickClient} disabled={busy} showGaps={false} />
          </section>
          {client ? (
            <DealChoice key={`${client.id}-${dealsKey}`} client={client} value={deal} disabled={busy}
                        problem={dealProblem} onChange={(d) => { setDeal(d); setDealProblem(null); setDuplicate(null); }} />
          ) : null}
          {deal ? (
            <ReturnedFile file={file} error={fileError} busy={busy} existing={!isNew} onFile={pickFile}
                          onAsTheirs={() => setAsTheirs(true)} />
          ) : null}
          {isNew && file ? (
            <BaseChoice haveCopy={haveCopy} noTracked={noTracked} busy={busy} copy={copy} copyError={copyError}
                        copyTracked={copyTracked} onCopy={(f) => void pickCopy(f)}
                        onHave={(yes) => {
                          setHaveCopy(yes);
                          if (!yes) { setNoTracked(false); setFileError((now) => (now === C.same ? null : now)); }
                        }} />
          ) : null}
          {duplicate ? (
            <Alert live>{C.duplicate} <Link className="nc-link" href={contractHref(duplicate)}>{C.openDeal}</Link></Alert>
          ) : null}
          {failure ? (
            // UI 9: one action (the bar's Try again), and what is already kept
            <div id="rm-fail" tabIndex={-1}>
              <ErrorState title={C.failed} error={failure} {...(resumable ? { fix: C.resumeCopyIn } : {})} />
            </div>
          ) : null}
          <details className="rm-next">
            <summary className="ic-section__h">{C.whatNext}</summary>
            {next}
          </details>
        </div>
        <aside className="ic-panel" aria-labelledby="rm-next-h">
          <h2 id="rm-next-h" className="ic-section__h">{C.whatNext}</h2>
          {next}
        </aside>
      </div>
      <div className="ic-bar rm-bar">
        {/* UI 8: the reason is read with the button; only a real step is announced */}
        <span className="ic-quiet" id="rm-bar-why">{!step && missing ? C.missing[missing] : ""}</span>
        <span className="ic-quiet" aria-live="polite">{step ? C.step(step.n, step.of, step.what) : ""}</span>
        <button type="button" className="ws-btn ws-btn--primary" aria-disabled={!!missing || busy || undefined}
                aria-describedby={missing ? "rm-bar-why" : undefined} aria-busy={busy || undefined} onClick={submit}>
          {busy ? <><span className="ws-spin" aria-hidden="true" /> {step?.what === "check" ? C.busyCheck : C.busy}</>
            : failure ? C.retry : C.submit}
        </button>
      </div>
      {asTheirs ? <UploadContractDialog firstRun={false} onClose={() => setAsTheirs(false)} /> : null}
    </div>
  );
}

/** The file the client sent back: one picker, compact once chosen (UI 11), its refusal linked. */
export function ReturnedFile({ file, error, busy, existing, onFile, onAsTheirs }: {
  file: File | null; error: string | null; busy: boolean; existing: boolean; onFile: (f: File | null) => void;
  onAsTheirs: () => void;
}) {
  return (
    <section className="ic-section" aria-labelledby="rm-file-h">
      <h2 id="rm-file-h" className="ic-section__h" tabIndex={-1}>{C.fileTitle}</h2>
      <FilePicker onFile={onFile} chosen={file} accept=".docx" title={C.pickTitle} hint={C.fileHint} disabled={busy}
                  compact={!!file} invalid={!!error} describedBy={error ? "rm-file-err" : undefined}
                  error={error ? <p id="rm-file-err" className="nc-error" role="alert" tabIndex={-1}>{error}</p> : null} />
      {error === C.pdf ? (
        <p className="ic-quiet">{C.pdfWayOn}{" "}
          <button type="button" className="nc-linkbtn" onClick={onAsTheirs}>{C.pdfUpload}</button></p>
      ) : null}
      {existing ? <p className="ic-quiet">{C.existingBase}</p> : null}
    </section>
  );
}

/** "Do you have the copy we sent?" — after a NO_TRACKED_CHANGES refusal the tracked-only
 *  answer is unavailable and says why (UI 2). */
export function BaseChoice({ haveCopy, noTracked, busy, copy, copyError, copyTracked, onCopy, onHave }: {
  haveCopy: boolean; noTracked: boolean; busy: boolean; copy: File | null; copyError: string | null;
  copyTracked: boolean; onCopy: (f: File | null) => void; onHave: (yes: boolean) => void;
}) {
  return (
    <fieldset className="ic-section rm-group" disabled={busy}>
      <legend><h2 id="rm-base-h" className="ic-section__h" tabIndex={-1}>{C.baseTitle}</h2></legend>
      {noTracked ? <Alert id="rm-notracked" live>{C.noTracked}</Alert> : null}
      <label className="nc-option">
        <input type="radio" name="rm-base" checked={haveCopy} onChange={() => onHave(true)} />
        <span className="nc-item__l1">{C.copyYes}</span><span className="nc-item__l2">{C.copyYesLine}</span>
      </label>
      {haveCopy ? (
        <div className="rm-copy">
          <FilePicker compact onFile={onCopy} chosen={copy} accept=".docx" hint={C.copyHint}
                      title={C.copyTitle} invalid={!!copyError} describedBy={copyError ? "rm-copy-err" : undefined}
                      error={copyError ? <p id="rm-copy-err" className="nc-error" role="alert">{copyError}</p> : null} />
          {copyTracked ? <Alert>{C.copyTracked}</Alert> : null}
        </div>
      ) : null}
      <label className="nc-option">
        <input type="radio" name="rm-base" checked={!haveCopy} onChange={() => onHave(false)}
               disabled={noTracked} aria-describedby={noTracked ? "rm-notracked" : undefined} />
        <span className="nc-item__l1">{C.copyNo}</span><span className="nc-item__l2">{C.copyNoLine}</span>
      </label>
    </fieldset>
  );
}

/** Which deal: this client's deals the reader may add a version to (`scope=negotiable`,
 *  server-scoped, SEC-07), 20 at a time. Only a deal that can take the file is a choice; the
 *  others sit in one closed list with "Open the deal" (UI 3). */
function DealChoice({ client, value, onChange, disabled, problem }: {
  client: Counterparty; value: string | null; onChange: (deal: string) => void; disabled: boolean;
  problem: string | null;
}) {
  const [rows, setRows] = useState<Contract[] | null>(null);
  const [failed, setFailed] = useState<unknown>(null);
  const [page, setPage] = useState(1);
  const [more, setMore] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api.contracts(page, 20, { counterparty_id: client.id, scope: "negotiable" })
      .then((r) => {
        if (!live) return;
        setFailed(null);
        const shown = dealsShown(r.items);
        setRows((now) => (page === 1 ? shown : [...(now ?? []), ...shown]));
        setMore(r.pagination.page * r.pagination.page_size < r.pagination.total);
        // D3: chosen for the person only when the client has no deal at all
        if (page === 1 && r.pagination.total === 0 && !problem) onChange(NEW_DEAL);
      })
      .catch((e) => { if (live) { setFailed(e); setRows((now) => now ?? []); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a page or a retry reloads
  }, [client.id, page, attempt]);

  const line = (c: Contract) => C.dealLine(documentTypeChip(c.contract_type), c.negotiation_stage
    ? stageWords(c.negotiation_stage.stage) : null, c.latest_version?.version_number ?? null,
    c.latest_version?.version_role, formatDate(c.updated_at));
  const open = (rows ?? []).filter(openForReturn);
  const closed = (rows ?? []).filter((c) => !openForReturn(c));
  return (
    <fieldset className="ic-section rm-group" disabled={disabled}>
      <legend><h2 id="rm-deal-h" className="ic-section__h" tabIndex={-1}>{C.dealTitle}</h2></legend>
      {problem ? <p className="nc-error" role="alert">{problem}</p> : null}
      {failed ? <ErrorState title={C.dealsFailed} fix={C.dealsFailedFix} onRetry={() => setAttempt((n) => n + 1)} /> : null}
      {rows === null ? (
        <div className="lm-skel" aria-live="polite" aria-label="Loading deals"><span className="lm-skel__row" /><span className="lm-skel__row" /></div>
      ) : open.map((c) => (
        <label key={c.id} className="nc-option">
          <input type="radio" name="rm-deal" checked={value === c.id} onChange={() => onChange(c.id)} />
          <span className="nc-item__l1">{c.name}</span><span className="nc-item__l2">{line(c)}</span>
        </label>
      ))}
      {rows !== null && !rows.length && !failed ? <p className="ic-quiet">{C.noDeals}</p> : null}
      {closed.length ? (
        <details className="rm-closed">
          <summary>{C.closedDeals(closed.length)}</summary>
          <p className="ic-quiet">{C.dealOpen}</p>
          <ul className="nc-results">
            {closed.map((c) => (
              <li key={c.id} className="nc-item nc-item--static">
                <span className="nc-item__l1">{c.name}</span><span className="nc-item__l2">{line(c)}</span>
                <Link className="nc-link" href={contractHref(c.id)}>{C.openDeal}</Link>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {more ? <button type="button" className="ws-btn ws-btn--sm rm-more" onClick={() => setPage((n) => n + 1)}>{C.moreDeals}</button> : null}
      <label className="nc-option">
        {/* UI 7: no choice before the deals are known (still usable when they failed to load) */}
        <input type="radio" name="rm-deal" checked={value === NEW_DEAL} disabled={rows === null}
               onChange={() => onChange(NEW_DEAL)} />
        <span className="nc-item__l1">{C.newDeal}</span><span className="nc-item__l2">{C.newDealLine}</span>
      </label>
    </fieldset>
  );
}

"use client";

/** The Changes tab's pieces the document view also draws (W2-2/W2-3): the one fetch the
 *  workspace owns, "for us", our reply's files and Send out. Their own module so the
 *  Changes pane itself can load only when its tab opens. Moved verbatim from ChangesPane. */
import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { PreviewPanel } from "@/components/PreviewPanel";
import { FEEDBACK_COPY } from "@/lib/feedbackCopy";
import { ApiError, api, describeError } from "@/lib/api";
import { effectLabel, type ChangeList, type EffectForUs, type Measured, type ReplyGate } from "@/lib/changes";
import { isOurs } from "@/lib/documentTypes";
import { useStep } from "@/lib/nextStep";
import { saveBlob } from "@/lib/pdfDownload";
import type { DocumentVersion } from "@/lib/types";

import "./changes.css";
import { requirementTitle } from "./findingLanguage";
import { IconAlertCircle, IconBetter, IconDownload, IconFallback, IconFile, IconFileMinus, IconSame, IconWorse } from "./icons";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; list: ChangeList }
  | { kind: "error"; error: unknown };

/** The pair the tab shows: the client's latest version against ours before it — or,
 *  once our reply is the latest version, the round that reply answered. */
export function clientVersion(versions: DocumentVersion[]): number | undefined {
  const latest = versions[0];
  return latest?.version_role === "COMPANY_DRAFT" && versions.length > 2
    ? latest.version_number - 1 : undefined;
}

/** One version only: a tab exactly when the server lists it — not ours (`is_ours`: an
 *  undeclared version is no one's, so its paper is listed and asked about), or made
 *  from our blank template (`AM-290`, `AM-302`). */
export function changesEnabled(versions: DocumentVersion[]): boolean {
  const only = versions.length === 1 ? versions[0] : undefined;
  // a signed copy alone has nothing to answer
  return versions.length > 1 || (!!only && only.version_role !== "FINAL_SIGNED"
    && (!isOurs(only) || !!only.made_from_template));
}

/** One fetch for the tab label and the pane, owned by the workspace page. */
export function useClientChanges(contractId: string, versions: DocumentVersion[]) {
  const toVersion = clientVersion(versions);
  // one version only: a tab exactly when it is the client's paper (`AM-290`, client
  // paper first — the server's `is_ours`, read the other way round)
  const enabled = changesEnabled(versions);
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [seq, setSeq] = useState(0);
  const reload = useCallback(() => setSeq((n) => n + 1), []);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api.clientChanges(contractId, toVersion).then(
      (list) => { if (!cancelled) setState({ kind: "ready", list }); },
      (error: unknown) => { if (!cancelled) setState({ kind: "error", error }); });
    return () => { cancelled = true; };
  }, [enabled, contractId, toVersion, seq]);
  return { state, setState, reload, enabled };
}

const EFFECT_ICON: Record<EffectForUs, typeof IconBetter> = { POSITIVE: IconBetter, NEUTRAL: IconSame, FALLBACK: IconFallback, NEGATIVE: IconWorse };
/** a NEGATIVE row not measured worse never wears the "worse" arrow */
const MEASURED_ICON: Record<Measured, typeof IconBetter> = { WORSE: IconWorse, NOT_MEASURED: IconAlertCircle, UNCLEAR: IconAlertCircle, ABSENT: IconFileMinus, REVIEW: IconAlertCircle };

/** "For us": an icon AND the words — the shape tells the three apart without colour, the
 *  words say it (WCAG 1.4.1). Its own slot, never merged with the review's word. */
export function ForUs({ effect, measured, size = 13 }: { effect: EffectForUs; measured?: Measured | undefined; size?: number }) {
  const Icon = effect === "NEGATIVE" && measured ? MEASURED_ICON[measured] : EFFECT_ICON[effect];
  return <span className="cx-forus" data-effect={effect} data-measured={effect === "NEGATIVE" ? measured : undefined}>
    <Icon size={size} />{effectLabel(effect, measured)}</span>;
}


/** Our reply's files, previewed first (UX Batch 2): "Preview" opens the exact PDF with
 *  Download PDF and Word inside. A reply with an undecided point is refused (`AM-293` r1,
 *  409 REPLY_UNDECIDED); the refusal lists what is open, each point a link to it. */
export function ReplyDownloads({ version, pdf = "reply-pdf", word: hasWord = true }: {
  version: Pick<DocumentVersion, "id"> & Partial<Pick<DocumentVersion, "version_number">>;
  /** our reply's PDF, or — a contract made from our template — the contract's */
  pdf?: "reply-pdf" | "pdf";
  /** false for a final copy of the client's own PDF: there is no Word file (`AM-318`) */
  word?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<{ message: string; gate?: ReplyGate | undefined } | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);   // focus returns here (WCAG 2.4.3)
  async function word() {
    setBusy(true);
    setRefused(null);
    try {
      const { blob, name } = await api.replyFile(version.id, "content");
      saveBlob(blob, name);
    } catch (cause) {
      setRefused({ message: describeError(cause), gate: cause instanceof ApiError ? cause.gate : undefined });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm" onClick={() => { setRefused(null); setOpen(true); }}>
        <IconFile size={14} /> {FEEDBACK_COPY.preview}
      </button>
      {/* AB-213 D8: the file itself, one click from the dialog that says "download it" */}
      {hasWord ? (
        <button type="button" className="ws-btn ws-btn--sm" disabled={busy} aria-busy={busy || undefined}
                onClick={() => void word()}>
          <IconDownload size={14} /> {FEEDBACK_COPY.downloadWord}
        </button>
      ) : null}
      {open ? (
        <PreviewPanel title={`${pdf === "reply-pdf" ? "Our reply" : "The contract"}${version.version_number ? `: version ${version.version_number}` : ""}`}
                      pdfPath={`/document-versions/${encodeURIComponent(version.id)}/${pdf}`}
                      onWord={hasWord ? () => void word() : undefined} wordBusy={busy}
                      onClose={() => setOpen(false)} returnFocus={() => trigger.current}
                      renderError={(cause) => (cause instanceof ApiError && cause.gate
                        ? <GateList message={describeError(cause)} gate={cause.gate} /> : null)} />
      ) : null}
      {refused ? <GateList message={refused.message} gate={refused.gate} /> : null}
    </>
  );
}

/** What keeps our reply inside LegalMind (`AM-293`): the review's open points, each a
 *  link to that point on the reply (the Document tab's `?finding=`). */
export function GateList({ message, gate }: { message: string; gate?: ReplyGate | null | undefined }) {
  return (
    <div className="cx-blocked" role="alert">
      <p className="cx-blocked__title">{message}</p>
      {gate?.reason === "ANALYSIS_NOT_FINISHED" ? (
        <p className="ws-pane__note">The reply is being reviewed like any upload. It can be downloaded once its review
          has finished and nothing in it is undecided.</p>
      ) : null}
      {gate?.open_points.length ? (
        <ul className="cx-blocked__list">
          {gate.open_points.map((p) => (
            <li key={p.finding_id}>
              <a href={`?finding=${encodeURIComponent(p.finding_id)}`}>{requirementTitle({ code: p.requirement_code })}</a>
              <span>needs a decision</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** "Send our reply" / "Send to client" (`AM-260`): LegalMind sends nothing itself, so the
 *  step says what it is — download the file, send it to the client, record when it went
 *  (once, audited, server-checked: a reply with an undecided point is refused, `AM-293`).
 *  The final contract (`AM-318`) is only downloaded: it is signed in another tool, and
 *  recording that it went is optional and never moves the deal off Final. */
export function SendOut({ version, label, onSent }: {
  version: Pick<DocumentVersion, "id" | "version_number" | "reply" | "package" | "final_copy" | "sent_at" | "mime_type">;
  label: string; onSent: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);     // U2 r2: Esc hands focus back here
  const final = !!(version.package || version.final_copy);
  useStep(final ? "downloadFinal" : version.reply ? "sendReply" : "sendToClient",
          useCallback(() => setOpen(true), []));
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => setOpen(true)}>{label}</button>
      {open ? (
        <Dialog onClose={() => setOpen(false)} titleId="lm-sendout-title" returnFocus={() => trigger.current}>
          <h2 id="lm-sendout-title">{label}</h2>
          <p className="ws-pane__note">
            {final ? <>Download version {version.version_number}, the final contract, and sign it in your
              signing tool. Nothing more is needed here.</>
              : <>Download version {version.version_number}, send it to the client from your email, then
                record it here so everyone sees it went.</>}
          </p>
          <div className="cx-dialog__foot cx-dialog__foot--start">
            <ReplyDownloads version={version} pdf={version.reply ? "reply-pdf" : "pdf"}
                            word={version.mime_type !== "application/pdf"} />
          </div>
          {error ? <p className="cx-error" role="alert">{error}</p> : null}
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" onClick={() => setOpen(false)}>{final ? "Close" : "Cancel"}</button>
            {final && version.sent_at ? null : (
              <button type="button" className={`ws-btn${final ? "" : " ws-btn--primary"}`} disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          await api.markSent(version.id);
                          setOpen(false);
                          onSent();
                        } catch (cause) {
                          setError(describeError(cause));
                        } finally {
                          setBusy(false);
                        }
                      }}>
                {busy ? "Recording…" : final ? "Record that you sent it" : "I have sent it"}
              </button>
            )}
          </div>
        </Dialog>
      ) : null}
    </>
  );
}

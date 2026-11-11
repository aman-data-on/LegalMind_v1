"use client";

/**
 * The ONE preview before a download (UX Batch 2): the EXACT PDF the reader will send —
 * fetched through the one PDF helper (`fetchPdf`: 200 / 202 rendering / 503 not made) and
 * drawn by the browser's own viewer — with Download PDF and Download Word inside it. The
 * PDF downloaded is the very file previewed (one fetch, one Blob). When the PDF cannot be
 * made, the panel says so and Word stays available. Presentation only: every download is
 * checked and audited on the server (rule 18).
 */

import { useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/Feedback";
import { FEEDBACK_COPY } from "@/lib/labels";
import { downloadWord, fetchPdf, saveBlob } from "@/lib/pdfDownload";
import { toastFailure } from "@/components/Toast";
import { IconDownload, IconFile, IconX } from "@/components/workspace/icons";

type Shown =
  | { kind: "loading"; waiting: boolean }
  | { kind: "ready"; blob: Blob; url: string; name: string | undefined }
  | { kind: "not-made"; message: string }
  | { kind: "error"; error: unknown };

export function PreviewPanel({ title, pdfPath, onWord, wordBusy = false, onClose, renderError, returnFocus }: {
  title: string;
  /** the API path of the PDF (`/document-versions/{id}/reply-pdf`) */
  pdfPath: string;
  /** downloads the Word file; absent when there is none (a client's own PDF) */
  onWord?: (() => void) | undefined;
  wordBusy?: boolean;
  onClose: () => void;
  /** a refusal the caller explains better (the reply's open points, `AM-293`) */
  renderError?: ((error: unknown) => React.ReactNode) | undefined;
  returnFocus?: () => HTMLElement | null | undefined;
}) {
  const [shown, setShown] = useState<Shown>({ kind: "loading", waiting: false });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    let url: string | null = null;
    fetchPdf(pdfPath, { onWaiting: () => { if (live) setShown({ kind: "loading", waiting: true }); } })
      .then((got) => {
        if (!live) return;
        if (got.kind === "file") {
          url = URL.createObjectURL(got.blob);
          setShown({ kind: "ready", blob: got.blob, url, name: got.name });
        } else setShown({ kind: "not-made", message: got.message });
      })
      .catch((error: unknown) => { if (live) setShown({ kind: "error", error }); });
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [pdfPath, attempt]);

  const retry = () => { setShown({ kind: "loading", waiting: false }); setAttempt((n) => n + 1); };
  const titleId = "lm-preview-title";
  return (
    <Dialog onClose={onClose} titleId={titleId} overlayClassName="lm-preview" {...(returnFocus ? { returnFocus } : {})}>
      <header className="lm-preview__head">
        <h2 id={titleId} className="lm-preview__title">{title}</h2>
        <button type="button" className="ws-btn lm-preview__close" aria-label={FEEDBACK_COPY.close} onClick={onClose}>
          <IconX size={16} />
        </button>
      </header>
      <div className="lm-preview__body">
        {shown.kind === "loading" ? <LoadingState label={FEEDBACK_COPY.preparingPreview} /> : null}
        {shown.kind === "ready" ? (
          // `<object>`, not an iframe: where the browser cannot draw a PDF inline (Android
          // Chrome, some locked-down browsers) it shows its fallback instead of a blank box
          <object className="lm-preview__frame" data={shown.url} type="application/pdf" aria-label={title}>
            <EmptyState title={FEEDBACK_COPY.noInlinePdf} body={FEEDBACK_COPY.noInlinePdfFix} />
          </object>
        ) : null}
        {shown.kind === "not-made" ? (
          <ErrorState title={FEEDBACK_COPY.previewFailed} fix={shown.message} onRetry={retry} />
        ) : null}
        {shown.kind === "error" ? (renderError?.(shown.error) ?? (
          <ErrorState title={FEEDBACK_COPY.previewFailed} error={shown.error} onRetry={retry} />
        )) : null}
      </div>
      <footer className="lm-preview__foot">
        {shown.kind === "ready" ? (
          <a className="ws-link lm-preview__open" href={shown.url} target="_blank" rel="noreferrer">{FEEDBACK_COPY.openPdf}</a>
        ) : <span />}
        <span className="lm-preview__acts">
          {onWord ? (
            <button type="button" className="ws-btn" disabled={wordBusy} aria-busy={wordBusy || undefined} onClick={onWord}>
              <IconDownload size={16} /> {FEEDBACK_COPY.downloadWord}
            </button>
          ) : null}
          <button type="button" className="ws-btn ws-btn--primary" disabled={shown.kind !== "ready"}
                  onClick={() => { if (shown.kind === "ready") saveBlob(shown.blob, shown.name); }}>
            <IconDownload size={16} /> {FEEDBACK_COPY.downloadPdf}
          </button>
        </span>
      </footer>
    </Dialog>
  );
}

/** A file the server makes on request (`?format=pdf|docx`: a blank template, a draft, a
 *  review copy), previewed before it is saved — the one way to download it. */
export function PreviewButton({ path, title, text = FEEDBACK_COPY.preview, label }: {
  /** the API path without `?format=` (`/templates/{key}/blank`) */
  path: string;
  /** the panel's title: which file, which version */
  title: string;
  /** the button's words ("Preview blank") */
  text?: string;
  /** the accessible name, where the words alone are ambiguous on a list of cards */
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const join = path.includes("?") ? "&" : "?";
  async function word() {
    setBusy(true);
    try { await downloadWord(`${path}${join}format=docx`); }
    catch (cause) { toastFailure("The Word file could not be downloaded")(cause); }
    finally { setBusy(false); }
  }
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm" aria-label={label} onClick={() => setOpen(true)}>
        <IconFile size={14} /> {text}
      </button>
      {open ? (
        <PreviewPanel title={title} pdfPath={`${path}${join}format=pdf`} onWord={() => void word()} wordBusy={busy}
                      onClose={() => setOpen(false)} returnFocus={() => trigger.current} />
      ) : null}
    </>
  );
}

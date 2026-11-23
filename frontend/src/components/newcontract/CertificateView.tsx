"use client";

/**
 * The client's GST certificate beside the Client details card (review change 3), so the
 * reader checks each value against the file without leaving the form. Fetched through the
 * one file helper (`usePdf`); a PDF opens larger in the shared `PreviewPanel`.
 */

import { useState } from "react";

import { api } from "@/lib/api";
import { FEEDBACK_COPY, INTAKE_COPY as C } from "@/lib/labels";
import { EmptyState, ErrorState, LoadingState } from "@/components/Feedback";
import { PreviewPanel, usePdf } from "@/components/PreviewPanel";

function Shown({ path, name }: { path: string; name: string }) {
  const { shown, retry } = usePdf(path);
  const [large, setLarge] = useState(false);
  if (shown.kind === "loading") return <LoadingState label={FEEDBACK_COPY.preparingPreview} rows={4} />;
  if (shown.kind !== "ready") {
    return <ErrorState title={C.certFailed} {...(shown.kind === "error" ? { error: shown.error } : { fix: shown.message })}
                       onRetry={retry} heading="h3" />;
  }
  const pdf = shown.blob.type === "application/pdf";
  return (
    <div className="ic-certview">
      {pdf
        ? <object className="ic-certview__frame" data={shown.url} type="application/pdf" aria-label={name}>
            <EmptyState title={FEEDBACK_COPY.noInlinePdf} body={C.certNoInline}
                        action={<button type="button" className="ws-btn ws-btn--sm" onClick={() => setLarge(true)}>{C.viewLarger}</button>} />
          </object>
        : <img className="ic-certview__img" src={shown.url} alt={name} />}
      {pdf ? <button type="button" className="ws-btn ws-btn--sm" onClick={() => setLarge(true)}>{C.viewLarger}</button> : null}
      {large ? <PreviewPanel title={name} pdfPath={path} onClose={() => setLarge(false)} /> : null}
    </div>
  );
}

export function CertificateView({ clientId, filename, uploadedAt }: {
  clientId: string; filename: string | undefined; uploadedAt: string | undefined;
}) {
  if (!filename) return <EmptyState body={C.noCertificate} />;
  // keyed by the upload time: a replaced certificate is fetched again
  return <Shown key={uploadedAt} path={api.gstCertificatePath(clientId)} name={filename} />;
}

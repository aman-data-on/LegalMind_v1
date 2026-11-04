/**
 * The ONE PDF download (every PDF button: our reply, a contract made from a template).
 * The worker makes the PDF, so the server answers:
 *
 *   200                         the PDF
 *   202 {status: "rendering"}   not yet — ask again after `Retry-After` seconds
 *   503 PDF_NOT_MADE            it could not be made — say so and stop
 *   409 REPLY_UNDECIDED         unchanged: an ApiError the caller shows (`AM-293`)
 *
 * Polling stops after ~2 minutes with a plain message. Nothing is decided here.
 */

import { useState } from "react";

import { ApiError, api, describeError, toApiError } from "./api";

export type PdfOutcome =
  | { kind: "file"; blob: Blob; name: string | undefined }
  | { kind: "not-made"; message: string }
  | { kind: "timeout"; message: string };

export const PDF_WAIT_MS = 120_000;
export const PDF_TIMEOUT = "The PDF is taking longer than usual. Try again in a minute; the Word file can still be downloaded.";
const NOT_MADE_TAIL = "The Word file can still be downloaded.";

const nap = (ms: number) => new Promise<void>((resolve) => { window.setTimeout(resolve, ms); });

/** Fetch `path` (an API path such as `/document-versions/{id}/reply-pdf`) until it is a file. */
export async function fetchPdf(path: string, opts: {
  onWaiting?: () => void; sleep?: (ms: number) => Promise<void>; now?: () => number; maxMs?: number;
} = {}): Promise<PdfOutcome> {
  const sleep = opts.sleep ?? nap, now = opts.now ?? Date.now, until = now() + (opts.maxMs ?? PDF_WAIT_MS);
  for (;;) {
    const response = await api.pdfResponse(path);
    if (response.status === 202) {
      opts.onWaiting?.();
      const wait = Math.max(1, Number(response.headers.get("Retry-After")) || 3) * 1000;
      if (now() + wait > until) return { kind: "timeout", message: PDF_TIMEOUT };
      await sleep(wait);
      continue;
    }
    if (response.status === 503) {
      const body = (await response.json().catch(() => ({}))) as { error?: { code?: string; message?: string } };
      if (body.error?.code === "PDF_NOT_MADE") {
        const said = body.error.message?.trim() ?? "The PDF could not be made.";
        return { kind: "not-made", message: said.includes(NOT_MADE_TAIL) ? said : `${said} ${NOT_MADE_TAIL}` };
      }
      throw new ApiError(503, "SERVICE_UNAVAILABLE", body.error?.message ?? "The PDF could not be made.",
        response.headers.get("X-Request-Id") ?? "-");
    }
    if (!response.ok) throw await toApiError(response, response.headers.get("X-Request-Id") ?? "-");
    const name = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(response.headers.get("Content-Disposition") ?? "")?.[1];
    return { kind: "file", blob: await response.blob(), name: name ? decodeURIComponent(name) : undefined };
  }
}

export function saveBlob(blob: Blob, name: string | undefined): void {
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: name ?? "" }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** A PDF button's state: idle → "Preparing the PDF…" while the worker makes it → saved,
 *  or a plain message. `error` keeps the ApiError so a 409 gate can list its points. */
export function usePdfDownload(path: string) {
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  async function download() {
    setBusy(true); setWaiting(false); setMessage(null); setError(null);
    try {
      const got = await fetchPdf(path, { onWaiting: () => setWaiting(true) });
      if (got.kind === "file") saveBlob(got.blob, got.name);
      else setMessage(got.message);
    } catch (cause) {
      setError(cause);
      setMessage(describeError(cause));
    } finally {
      setBusy(false); setWaiting(false);
    }
  }
  return { busy, waiting, message, error, download, label: waiting ? "Preparing the PDF…" : null };
}

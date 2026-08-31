"use client";

/**
 * Export the Review's analysis as a file — PDF or DOCX (owner directive
 * 2026-08-31; 49.3's export row). Renders nothing without `export.generate`
 * (permission-aware, not permission-apologetic — DESIGN.md).
 *
 * The server renders the file under the caller's own permissions, so what
 * downloads is exactly what this account can see on screen — nothing more.
 */

import { useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

export function ExportControl({ reviewId }: { reviewId: string }) {
  const { can } = useSession();
  const [busy, setBusy] = useState<"pdf" | "docx" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!can(P.EXPORT_GENERATE)) return null;

  async function download(format: "pdf" | "docx") {
    setBusy(format);
    setError(null);
    try {
      const { blob, filename } = await api.exportReview(reviewId, format);
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? describeError(cause)
          : "The export could not be generated.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <span className="ws-export">
      <span className="ws-pane__note">Export</span>
      <button type="button" className="ws-btn ws-btn--sm" disabled={busy !== null}
              onClick={() => void download("pdf")}>
        {busy === "pdf" ? "Rendering…" : "PDF"}
      </button>
      <button type="button" className="ws-btn ws-btn--sm" disabled={busy !== null}
              onClick={() => void download("docx")}>
        {busy === "docx" ? "Rendering…" : "DOCX"}
      </button>
      {error ? (
        <span className="ws-field__error" role="alert">{error}</span>
      ) : null}
    </span>
  );
}

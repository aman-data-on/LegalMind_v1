"use client";

/**
 * Inline document upload for the workspace's empty state — 2026-08-30 cleanup.
 *
 * Before this, the empty state linked to the legacy `/contracts/{id}` page to
 * upload — exactly the "navigation path into the old application" the cleanup
 * exists to remove. The upload call itself was always real (`api.uploadDocument`,
 * the same `POST .../document-versions` the legacy page used); only the button
 * pointed at the wrong screen.
 *
 * `.pdf,.docx` and `required` mirror the legacy input; the server still sniffs
 * the actual bytes regardless of what the browser claims (34.16) — this is a
 * convenience for the file picker, not a validation boundary.
 */

import { useRef, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";

export function UploadDocument({
  contractId,
  onUploaded,
}: {
  contractId: string;
  /** Awaited, so a caller chaining analysis keeps the busy state honest. */
  onUploaded: () => void | Promise<void>;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadDocument(contractId, file);
      await onUploaded();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
      <label>
        <span className="ws-visually-hidden">Document file</span>
        <input ref={fileInput} type="file" accept=".pdf,.docx" required disabled={busy} />
      </label>
      <button type="submit" className="ws-btn ws-btn--primary" disabled={busy}>
        {busy ? "Uploading…" : "Upload"}
      </button>
      <ErrorBanner error={error} />
    </form>
  );
}

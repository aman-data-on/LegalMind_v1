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
import { api, type UploadRole } from "@/lib/api";
import { VERSION_ROLES } from "@/lib/documentTypes";
import { ROLE_WORDS } from "./model";
import { FilePicker } from "@/components/FilePicker";

export function UploadDocument({
  contractId,
  onUploaded,
  roleDefault,
  onCancel,
  submitLabel = "Upload",
}: {
  contractId: string;
  /** Awaited, so a caller chaining analysis keeps the busy state honest. */
  onUploaded: () => void | Promise<void>;
  /** A further version (drawn in the upload dialog): asks what it is, starting here
   *  ("" = the reader must choose). Declared before analysis — 33.7 fixes it after. */
  roleDefault?: string;
  /** a further version's dialog closes from its own footer, beside Upload */
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [role, setRole] = useState(roleDefault ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [picked, setPicked] = useState<File | null>(null);
  /** each missing answer said under its own field, never as a browser bubble */
  const [missing, setMissing] = useState<{ file?: boolean; role?: boolean }>({});
  const further = roleDefault !== undefined;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    const gaps = { file: !file, role: !role };            // AM-324 r4: always said
    setMissing(gaps);
    if (!file || gaps.role) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadDocument(contractId, file!, role as UploadRole);
      await onUploaded();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  const acts = [
    <button key="up" type="submit" className="ws-btn ws-btn--sm ws-btn--primary" disabled={busy}>
      {busy ? "Uploading…" : submitLabel}
    </button>,
    onCancel ? (
      <button key="cancel" type="button" className="ws-btn ws-btn--sm" onClick={onCancel} disabled={busy}>Cancel</button>
    ) : null,
  ];
  return (
    <form onSubmit={submit} noValidate className={further ? "ws-upload ws-upload--version" : "ws-upload"}>
      {/* the one upload picker (UX Batch 2): the native control stays in the form */}
      <div className="ws-field">
        {further ? <span className="ws-field__label">File</span> : null}
        <FilePicker compact required inputRef={fileInput} chosen={picked} disabled={busy}
                    invalid={missing.file} describedBy={missing.file ? "ws-upload-file-error" : undefined}
                    onFile={(file) => { setPicked(file); setMissing((m) => ({ ...m, file: false })); }}
                    error={missing.file ? <p className="ws-field__error" id="ws-upload-file-error">Choose a file to upload</p> : null} />
      </div>
      {/* AM-324 r4: every upload says whose paper it is */}
      {(
        <label className="ws-field">
          <span className="ws-field__label">What is this version?</span>
          <select value={role} required disabled={busy} aria-invalid={missing.role || undefined}
                  aria-describedby={missing.role ? "ws-upload-role-error" : undefined}
                  onChange={(event) => {
                    setRole(event.target.value);
                    setMissing((m) => ({ ...m, role: false }));
                  }}>
            <option value="" disabled>Choose…</option>
            {/* a signed copy goes through Record signing, never declared here (AM-298) */}
            {VERSION_ROLES.filter((r) => r.role !== "FINAL_SIGNED").map((r) => (
              <option key={r.role} value={r.role}>{`${ROLE_WORDS[r.role] ?? r.label} — ${r.hint}`}</option>
            ))}
          </select>
          {missing.role ? <p className="ws-field__error" id="ws-upload-role-error">Choose what this version is</p> : null}
        </label>
      )}
      {further ? <ErrorBanner error={error} /> : null}
      {/* the dialog's footer: Cancel, then the one primary, right-aligned */}
      <div className={further ? "ws-upload__acts ws-modal__acts" : "ws-upload__acts"}>
        {further ? acts.reverse() : acts}
      </div>
      {further ? null : <ErrorBanner error={error} />}
    </form>
  );
}

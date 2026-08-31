"use client";

/**
 * Upload-first intake — the 2026-08-31 UX correction. The user's act is "here
 * is a contract"; everything the backend needs (create the contract record,
 * upload the version, resolve the current standards, start the Review, run the
 * analysis) happens behind ONE primary action, and the user lands in the
 * workspace at whatever stage is real.
 *
 * The confirm panel keeps exactly two decisions with the user:
 *   Name — derived from the filename as an editable default.
 *   Type — HUMAN-DECLARED (owner Q9, locked): the select starts empty; a
 *          filename hint is text beside it, applied only by the user's click.
 *
 * Best-effort chaining, honest degradation: a missing published snapshot or a
 * missing review.create permission never blocks the upload — the workspace's
 * own states say what happened and who unblocks it. A `duplicate_of` result is
 * surfaced (34.5: reported, never suppressed) on the workspace note.
 */

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, describeError } from "@/lib/api";
import { DOCUMENT_TYPES, documentTypeLabel, nameFromFilename, typeHintFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

type Stage = "idle" | "uploading" | "analyzing";

export function UploadContract({ firstRun }: { firstRun: boolean }) {
  const { can } = useSession();
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<unknown>(null);
  const [dragging, setDragging] = useState(false);

  if (!can(P.CONTRACT_CREATE) || !can(P.DOCUMENT_UPLOAD)) {
    return firstRun ? (
      <p className="ws-pane__note">Your account does not include document upload.</p>
    ) : null;
  }

  function choose(chosen: File | null) {
    if (!chosen) return;
    setFile(chosen);
    setName(nameFromFilename(chosen.name));
    setContractType("");
    setError(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !contractType) return;
    setError(null);
    setStage("uploading");
    let contractId: string;
    try {
      const contract = await api.createContract(name.trim(), contractType);
      contractId = contract.id;
      await api.uploadDocument(contractId, file);
    } catch (cause) {
      // Nothing usable was made visible — stay here and say why.
      setError(cause);
      setStage("idle");
      return;
    }
    // Analysis, best-effort: resolve the latest published standards and run.
    // Any failure here is a STATE the workspace explains, never a dead end.
    setStage("analyzing");
    try {
      if (can(P.REVIEW_CREATE)) {
        const snapshots = await api.snapshots({ page_size: 1 });
        const snapshot = snapshots.items[0];
        if (snapshot) {
          const detail = await api.contract(contractId);
          const versionId = detail.document_versions?.[0]?.id;
          if (versionId) {
            const review = await api.createReview(versionId, snapshot.id);
            await api.analyzeReview(review.id);
          }
        }
      }
    } catch {
      // The workspace's findings pane states the real situation.
    }
    router.push(`/workspace/${contractId}`);
  }

  const hint = file ? typeHintFromFilename(file.name) : null;

  if (!file) {
    return (
      <div
        className={`ws-drop${dragging ? " ws-drop--over" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          choose(event.dataTransfer.files?.[0] ?? null);
        }}
      >
        <p className="ws-drop__lede">
          {firstRun
            ? "Give LegalMind a contract — it reads it, compares it with your approved legal standards, and answers questions about it."
            : "Upload a contract to analyse it against your approved legal standards."}
        </p>
        <label className="ws-btn ws-btn--primary ws-drop__pick">
          Upload a contract
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx"
            className="ws-visually-hidden"
            onChange={(event) => choose(event.target.files?.[0] ?? null)}
          />
        </label>
        <span className="ws-drop__hint">PDF or DOCX — or drop the file here</span>
      </div>
    );
  }

  return (
    <form className="ws-intake" onSubmit={submit} aria-labelledby="ws-upload-title">
      <h2 id="ws-upload-title" className="ws-intake__title">
        {file.name} <span className="ws-mono ws-intake__size">{Math.max(1, Math.round(file.size / 1024))} KB</span>
      </h2>
      <div className="ws-intake__fields">
        <label className="ws-field">
          <span className="ws-field__label">Name</span>
          <input required value={name} onChange={(event) => setName(event.target.value)} disabled={stage !== "idle"} />
          <span className="ws-field__help">From the filename — change it if you like.</span>
        </label>
        <label className="ws-field ws-field--type">
          <span className="ws-field__label">
            Document type <span className="ws-field__req">(required)</span>
          </span>
          <select
            required
            value={contractType}
            onChange={(event) => setContractType(event.target.value)}
            disabled={stage !== "idle"}
          >
            <option value="">Choose the type…</option>
            {DOCUMENT_TYPES.map((type) => (
              <option key={type.code} value={type.code}>
                {type.label} ({type.code})
              </option>
            ))}
          </select>
          <span className="ws-field__help">
            {hint && contractType !== hint ? (
              <>
                The filename mentions &ldquo;{hint}&rdquo; —{" "}
                <button type="button" className="ws-escalate__link" onClick={() => setContractType(hint)}>
                  select {documentTypeLabel(hint)}
                </button>{" "}
                if that&rsquo;s right.{" "}
              </>
            ) : null}
            You declare the type; LegalMind never guesses it.
          </span>
        </label>
        <button
          type="submit"
          className="ws-btn ws-btn--primary"
          disabled={stage !== "idle" || !name.trim() || !contractType}
        >
          {stage === "uploading" ? "Uploading…" : stage === "analyzing" ? "Starting analysis…" : "Upload and analyze"}
        </button>
      </div>
      {stage === "idle" ? (
        <button type="button" className="ws-escalate__link" onClick={() => setFile(null)}>
          Choose a different file
        </button>
      ) : null}
      {error ? (
        <p className="ws-field__error" role="alert">
          {error instanceof ApiError ? describeError(error) : "The upload could not be completed."}
        </p>
      ) : null}
    </form>
  );
}

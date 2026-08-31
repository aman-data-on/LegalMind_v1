"use client";

/**
 * Upload-first intake, now suggestion-assisted (owner, 2026-08-31). The user's
 * act is "here is a contract": choosing the file immediately creates the
 * contract record and uploads the version, and the assist lane then reads the
 * document's own opening text to PROPOSE a Step 6 type. The confirm panel keeps
 * exactly two decisions with the user:
 *
 *   Name — derived from the filename as an editable default.
 *   Type — still HUMAN-DECLARED (owner Q9's substance is intact): the select is
 *          pre-filled only as a suggestion, and the value is recorded only by
 *          the user's own confirm (PATCH). When the assist lane is not
 *          confident — or unavailable, gated, or wrong-shaped — the select
 *          starts empty exactly as before, with the filename hint as fallback.
 *
 * Best-effort chaining, honest degradation: a missing published snapshot or a
 * missing review.create permission never blocks the upload — the workspace's
 * own states say what happened and who unblocks it. A `duplicate_of` result is
 * surfaced (34.5: reported, never suppressed) on the workspace note.
 */

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { chainAnalysis } from "@/lib/analysisChain";
import { ApiError, api, describeError } from "@/lib/api";
import { DOCUMENT_TYPES, documentTypeLabel, nameFromFilename, typeHintFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { TypeSuggestion } from "@/lib/types";

type Stage = "idle" | "uploading" | "suggesting" | "confirm" | "analyzing";

/** Mirrors the server default (`LEGALMIND_MAX_UPLOAD_BYTES`, 50 MB). A
 *  convenience pre-check for an immediate, friendly message — the server's
 *  own validation stays the authority (34.16). */
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx"];

function preflightProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "This file type is not supported. Please choose a PDF or DOCX file.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "This file exceeds the 50 MB limit. Please choose a smaller file.";
  }
  if (file.size === 0) {
    return "This file is empty. Please choose another file.";
  }
  return null;
}

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
  const [contractId, setContractId] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<TypeSuggestion | null>(null);

  if (!can(P.CONTRACT_CREATE) || !can(P.DOCUMENT_UPLOAD)) {
    return firstRun ? (
      <p className="ws-pane__note">Your account does not include document upload.</p>
    ) : null;
  }

  async function choose(chosen: File | null) {
    if (!chosen || stage !== "idle") return;
    const problem = preflightProblem(chosen);
    if (problem) {
      setFile(null);
      setError(problem);
      return;
    }
    const derivedName = nameFromFilename(chosen.name);
    setFile(chosen);
    setName(derivedName);
    setContractType("");
    setSuggestion(null);
    setError(null);
    setStage("uploading");

    // Create + upload behind the one gesture. The type is deliberately NOT set
    // yet — it is declared by the user on confirm (Q9's substance).
    let versionId: string;
    try {
      const contract = await api.createContract(derivedName);
      setContractId(contract.id);
      const uploaded = await api.uploadDocument(contract.id, chosen);
      versionId = uploaded.document_version.id;
    } catch (cause) {
      setFile(null);
      setContractId(null);
      setError(cause);
      setStage("idle");
      return;
    }

    // The assist lane proposes a type from the document's own opening text.
    // Every failure shape is the same honest "not confident" — the select then
    // starts empty exactly as it did before this feature existed.
    setStage("suggesting");
    try {
      const proposed = await api.suggestType(versionId);
      setSuggestion(proposed);
      if (proposed.confident && proposed.suggested_type) {
        setContractType(proposed.suggested_type);
      }
    } catch {
      setSuggestion(null);
    }
    setStage("confirm");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!contractId || !contractType) return;
    setError(null);
    setStage("analyzing");
    try {
      // The human act that records the declaration — the suggestion never
      // wrote anything.
      await api.updateContract(contractId, {
        name: name.trim(),
        contract_type: contractType,
      });
    } catch (cause) {
      setError(cause);
      setStage("confirm");
      return;
    }
    // Analysis, best-effort: resolve the latest published standards and run.
    // Any failure here is a STATE the workspace explains, never a dead end.
    await chainAnalysis(contractId, can(P.REVIEW_CREATE));
    router.push(`/workspace?id=${contractId}`);
  }

  const hint = file ? typeHintFromFilename(file.name) : null;
  const suggested = suggestion?.confident ? suggestion.suggested_type : null;

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
          void choose(event.dataTransfer.files?.[0] ?? null);
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
            onChange={(event) => void choose(event.target.files?.[0] ?? null)}
          />
        </label>
        <span className="ws-drop__hint">PDF or DOCX — or drop the file here</span>
        {error ? (
          <p className="ws-field__error" role="alert">
            {typeof error === "string" ? error : describeError(error)}
          </p>
        ) : null}
      </div>
    );
  }

  const busy = stage === "uploading" || stage === "suggesting";

  return (
    <form className="ws-intake" onSubmit={submit} aria-labelledby="ws-upload-title">
      <h2 id="ws-upload-title" className="ws-intake__title">
        {file.name} <span className="ws-mono ws-intake__size">{Math.max(1, Math.round(file.size / 1024))} KB</span>
      </h2>
      <div className="ws-intake__fields">
        <label className="ws-field">
          <span className="ws-field__label">Name</span>
          <input required value={name} onChange={(event) => setName(event.target.value)} disabled={stage !== "confirm"} />
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
            disabled={stage !== "confirm"}
          >
            <option value="">{busy ? "Reading the document…" : "Choose the type…"}</option>
            {DOCUMENT_TYPES.map((type) => (
              <option key={type.code} value={type.code}>
                {type.label} ({type.code})
              </option>
            ))}
          </select>
          <span className="ws-field__help" aria-live="polite">
            {busy ? (
              stage === "uploading" ? "Uploading…" : "Identifying the document type…"
            ) : suggested && contractType === suggested ? (
              <>
                LegalMind suggested this from the document
                {suggestion?.reason ? <> — {suggestion.reason}</> : null}. Change it if it&rsquo;s wrong; you confirm the type, it&rsquo;s never recorded without you.
              </>
            ) : (
              <>
                {stage === "confirm" && !suggested && !contractType ? (
                  <>Couldn&rsquo;t confidently identify the type — please choose it. </>
                ) : null}
                {hint && contractType !== hint ? (
                  <>
                    The filename mentions &ldquo;{hint}&rdquo; —{" "}
                    <button type="button" className="ws-escalate__link" onClick={() => setContractType(hint)}>
                      select {documentTypeLabel(hint)}
                    </button>{" "}
                    if that&rsquo;s right.{" "}
                  </>
                ) : null}
                You confirm the type; nothing is recorded without you.
              </>
            )}
          </span>
        </label>
        <button
          type="submit"
          className="ws-btn ws-btn--primary"
          disabled={stage !== "confirm" || !name.trim() || !contractType}
        >
          {stage === "uploading"
            ? "Uploading…"
            : stage === "suggesting"
              ? "Identifying document type…"
              : stage === "analyzing"
                ? "Starting analysis…"
                : "Confirm and analyze"}
        </button>
      </div>
      {stage === "confirm" ? (
        <button
          type="button"
          className="ws-escalate__link"
          onClick={() => {
            setFile(null);
            setContractId(null);
            setSuggestion(null);
            setContractType("");
            setStage("idle");
          }}
        >
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

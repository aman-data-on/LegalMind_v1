"use client";

/**
 * Upload-first intake, staged as a live checklist (owner, 2026-09-01 —
 * "AI Contract Intelligence" redesign, superseding the 2026-08-31 plain-form
 * confirm panel's VISUALS only). The user's act is "here is a contract": one
 * upload gesture, then the system narrates what it is doing — Uploaded,
 * Content Extracted, Type Detected, Standard Identified, Analyzing — using
 * exactly the same sequential calls the previous version already made, never
 * a new backend capability.
 *
 * AM-50 (owner, 2026-09-09) amends Q9 / AM-34 / DOC-06: a CONFIDENT suggestion
 * is recorded by the intake and the review starts — "I uploaded my contract and
 * LegalMind reviewed it." The audit trail records that the type came from the
 * suggestion; the reader can change it in Edit details, which re-runs the
 * analysis; the evaluator still refuses an undeclared type. Only when the
 * document's text does not say what it is does the intake ask its one question.
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

import { IconCheckCircle, IconUploadCloud } from "./icons";

type Stage = "idle" | "uploading" | "extracted" | "suggesting" | "analyzing";

/** Mirrors the server default (`LEGALMIND_MAX_UPLOAD_BYTES`, 25 MB — owner, 2026-09-02). A
 *  convenience pre-check for an immediate, friendly message — the server's
 *  own validation stays the authority (34.16). */
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx"];

const CHECKLIST_ORDER: Stage[] = ["uploading", "extracted", "suggesting", "analyzing"];

function preflightProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "This file type is not supported. Please choose a PDF or DOCX file.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "This file exceeds the 25 MB limit. Please choose a smaller file.";
  }
  if (file.size === 0) {
    return "This file is empty. Please choose another file.";
  }
  return null;
}

export function UploadContract({ firstRun }: {
  firstRun: boolean;
  /** Kept for callers; the intake no longer asks for declared facts — they
   *  live in "Edit details", where they always were too (AM-50). */
  counterparties?: string[];
}) {
  const { can } = useSession();
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");
  /** Where a pre-filled value came from — so the help text names its source and
   *  never implies the system decided anything. `null` once the human touches it. */
  const [typeSource, setTypeSource] = useState<"assist" | "filename" | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<unknown>(null);
  const [dragging, setDragging] = useState(false);
  const [contractId, setContractId] = useState<string | null>(null);
  const contractIdRef = useRef<string | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  /** The type the intake recorded on the reader's behalf (AM-50) — shown as
   *  "Reviewed as …" while the analysis starts. */
  const [recordedType, setRecordedType] = useState<string | null>(null);

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
    setError(null);
    setStage("uploading");

    // Create + upload behind the one gesture. The type is deliberately NOT set
    // yet — it is declared by the user on confirm (Q9's substance).
    let versionId: string;
    try {
      const contract = await api.createContract(derivedName);
      setContractId(contract.id);
      contractIdRef.current = contract.id;
      const uploaded = await api.uploadDocument(contract.id, chosen);
      versionId = uploaded.document_version.id;
      setVersionId(versionId);
    } catch (cause) {
      setFile(null);
      setContractId(null);
      contractIdRef.current = null;
      setError(cause);
      setStage("idle");
      return;
    }
    setStage("extracted");

    // The assist lane proposes a type from the document's own opening text.
    setStage("suggesting");
    let proposedType: string | null = null;
    try {
      const proposed = await api.suggestType(versionId);
      if (proposed.confident && proposed.suggested_type) {
        proposedType = proposed.suggested_type;
      }
    } catch {
      /* not confident — the one question below */
    }

    // AM-51 (owner, 2026-09-09): the type is one optional signal, never a gate.
    // A confident suggestion is recorded (audited as ASSIST_SUGGESTION) so the
    // reader sees "Reviewed as …" and the engine has the signal; without one the
    // review still starts — the engine measures the document by its content.
    if (proposedType) {
      try {
        await api.updateContract(contract_id_or_throw(contractIdRef.current), {
          name: derivedName, contract_type: proposedType,
          contract_type_source: "ASSIST_SUGGESTION",
        });
        setRecordedType(proposedType);
        setContractType(proposedType);
      } catch {
        setRecordedType(null);
      }
    }
    setStage("analyzing");
    await chainAnalysis(contractIdRef.current!, can(P.REVIEW_CREATE));
    router.push(`/dashboard?id=${contractIdRef.current}`);
  }

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
        <span className="ws-drop__icon" aria-hidden="true"><IconUploadCloud size={28} /></span>
        <h2 className="ws-drop__title">Upload a contract</h2>
        {/*
          No body copy (owner, 2026-09-01: essentials only). It read "You'll
          confirm the contract type on the next step, then every clause is
          measured against the standard approved for that type" — which is steps 3
          and 4 of the strip beside it, restated. The heading names the action and
          the control performs it.

          (For the record, the string before that one — "LegalMind will
          automatically detect the contract type" — was removed on correctness
          grounds, not brevity: owner Q9 makes the type declared, never inferred.)
        */}
        <label className="ws-btn ws-btn--primary ws-drop__pick">
          Upload Contract
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx"
            className="ws-visually-hidden"
            onChange={(event) => void choose(event.target.files?.[0] ?? null)}
          />
        </label>
        <span className="ws-drop__hint">PDF or DOCX, up to 25 MB — PDF preferred (it carries its own page layout) — or drag and drop</span>
        {error ? (
          <p className="ws-field__error" role="alert">
            {typeof error === "string" ? error : describeError(error)}
          </p>
        ) : null}
      </div>
    );
  }

  const stageIndex = CHECKLIST_ORDER.indexOf(stage);

  return (
    <div className="ws-intake" aria-labelledby="ws-upload-title">
      <h2 id="ws-upload-title" className="ws-intake__title">
        {file.name} <span className="ws-mono ws-intake__size">{Math.max(1, Math.round(file.size / 1024))} KB</span>
      </h2>

      {/* The live checklist — every step is a real, already-happened (or
          in-flight) act; nothing here is decorative pacing. */}
      <ol className="ws-checklist" aria-live="polite">
        <ChecklistRow done={stageIndex >= CHECKLIST_ORDER.indexOf("uploading")} active={stage === "uploading"}>
          Uploaded
        </ChecklistRow>
        <ChecklistRow done={stageIndex >= CHECKLIST_ORDER.indexOf("extracted")} active={false}>
          Content Extracted
        </ChecklistRow>
        <ChecklistRow done={stage === "analyzing"} active={stage === "suggesting"}>
          {stage === "analyzing" ? (
            recordedType ? (
              <>Reviewed as <strong>{documentTypeLabel(recordedType)}</strong> — change it any time in Edit details</>
            ) : (
              "Reviewing by content — the type can be added in Edit details"
            )
          ) : (
            "Reading the document…"
          )}
        </ChecklistRow>
        {stage === "analyzing" ? (
          <ChecklistRow done={false} active spinner>Reviewing against the company standards…</ChecklistRow>
        ) : null}
      </ol>

      {stage !== "idle" && stage !== "analyzing" ? (
        <button
          type="button"
          className="ws-escalate__link"
          onClick={() => {
            setFile(null);
            setContractId(null);
            setVersionId(null);
            contractIdRef.current = null;
            setRecordedType(null);
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
    </div>
  );
}

function contract_id_or_throw(id: string | null): string {
  if (!id) throw new Error("no contract");
  return id;
}

function ChecklistRow({
  done, active, spinner, children,
}: { done: boolean; active: boolean; spinner?: boolean; children: React.ReactNode }) {
  return (
    <li className={`ws-checklist__row${done ? " ws-checklist__row--done" : ""}${active ? " ws-checklist__row--active" : ""}`}>
      <span className="ws-checklist__icon" aria-hidden="true">
        {done ? <IconCheckCircle size={15} /> : spinner || active ? <span className="ws-spin" /> : <span className="ws-checklist__dot" />}
      </span>
      {children}
    </li>
  );
}

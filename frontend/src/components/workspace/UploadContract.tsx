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
 * Q9 / `AM-34` stand exactly as locked: the type is HUMAN-DECLARED. What
 * changed on 2026-09-01: the type select is now ALWAYS shown, and is pre-filled
 * when there is anything to pre-fill it with — the assist lane's proposal first,
 * then a Step 6 code named in the filename (`AM-34` t1 authorises both inputs and
 * says the proposal "pre-fills the intake select"). The help text names which
 * source produced the value, so a guess never reads as a determination.
 *
 * Owner Q9 is unchanged and this is why it holds: pre-filling a control is not
 * recording a type. `contract_type` is written only by the submit — an explicit
 * human act — and the field says so directly above the button.
 * behaviour changed there, only the surrounding frame.
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

import { IconCheckCircle, IconUploadCloud } from "./icons";

type Stage = "idle" | "uploading" | "extracted" | "suggesting" | "confirm" | "analyzing";

/** Mirrors the server default (`LEGALMIND_MAX_UPLOAD_BYTES`, 50 MB). A
 *  convenience pre-check for an immediate, friendly message — the server's
 *  own validation stays the authority (34.16). */
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx"];

const CHECKLIST_ORDER: Stage[] = ["uploading", "extracted", "suggesting", "confirm", "analyzing"];

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
  /** Where a pre-filled value came from — so the help text names its source and
   *  never implies the system decided anything. `null` once the human touches it. */
  const [typeSource, setTypeSource] = useState<"assist" | "filename" | null>(null);
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
    setStage("extracted");

    // The assist lane proposes a type from the document's own opening text.
    // Every failure shape is the same honest "not confident" — the picker
    // then appears exactly as it did before this feature existed.
    setStage("suggesting");
    let proposedType: string | null = null;
    try {
      const proposed = await api.suggestType(versionId);
      setSuggestion(proposed);
      if (proposed.confident && proposed.suggested_type) {
        proposedType = proposed.suggested_type;
        setContractType(proposedType);
        setTypeSource("assist");
      }
    } catch {
      setSuggestion(null);
    }

    if (!proposedType) {
      /*
       * `AM-34` t1 (AB-7) — the proposal may be drawn from "the document version's
       * own committed evidence **plus its original filename**", and "the proposal
       * pre-fills the intake select". So when the assist lane cannot answer, a
       * filename that names a Step 6 code still pre-fills it.
       *
       * Owner Q9 is untouched and this is the reason it is safe: pre-filling a
       * select is not recording a type. `contract_type` is written only by the
       * submit below — an explicit human act — and the help text says so. Before
       * this, the filename hint sat behind a link the reader had to notice and
       * click, which is why a document plainly named "…MSA…" still arrived with an
       * empty picker (owner, 2026-09-01: "pehle toh automatically kar leta tha").
       */
      const fromName = typeHintFromFilename(chosen.name);
      if (fromName) {
        setContractType(fromName);
        setTypeSource("filename");
      }
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
    router.push(`/documents?id=${contractId}`);
  }

  const confident = suggestion?.confident === true && !!suggestion.suggested_type;

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
        <span className="ws-drop__hint">PDF or DOCX — or drag and drop file here</span>
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
    <form className="ws-intake" onSubmit={submit} aria-labelledby="ws-upload-title">
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
        <ChecklistRow done={stage === "confirm" || stage === "analyzing"} active={stage === "suggesting"}>
          {stage === "confirm" || stage === "analyzing" ? (
            confident ? (
              <>Type Detected: <strong>{documentTypeLabel(suggestion!.suggested_type)}</strong></>
            ) : (
              "Type needs your confirmation"
            )
          ) : (
            "Detecting document type…"
          )}
        </ChecklistRow>
        {stage === "analyzing" ? (
          <>
            <ChecklistRow done active={false}>Relevant Standard Identified</ChecklistRow>
            <ChecklistRow done={false} active spinner>Analyzing…</ChecklistRow>
          </>
        ) : null}
      </ol>

      {stage === "confirm" ? (
        <div className="ws-intake__confirm">
          <label className="ws-field">
            <span className="ws-field__label">Name</span>
            <input required value={name} onChange={(event) => setName(event.target.value)} />
            <span className="ws-field__help">From the filename — change it if you like.</span>
          </label>

          {/*
            One presentation, always. This used to branch: a confident suggestion
            showed a prose line ("LegalMind identified this as a …") with a "Not
            right? Change it" link, and the select appeared only if you clicked it.
            Two problems — the reader had to act to see the field they were about to
            be judged on, and the prose asserted an identification more firmly than
            a suggestion warrants. A pre-selected select says the same thing in a
            control the reader can already change, which is also the shape `AM-34`
            t1 describes ("the proposal pre-fills the intake select").
          */}
          <label className="ws-field ws-field--type">
              <span className="ws-field__label">
                Document type <span className="ws-field__req">(required)</span>
              </span>
              <select
                required
                value={contractType}
                onChange={(event) => {
                  setContractType(event.target.value);
                  setTypeSource(null);   // it is the reader's choice now, not a guess
                }}
              >
                <option value="">Choose the type…</option>
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type.code} value={type.code}>
                    {type.label} ({type.code})
                  </option>
                ))}
              </select>
              {/*
                Three cases, and each says where the value came from. Naming the
                source is what keeps a pre-filled select honest under owner Q9: the
                reader can see this was a guess from a filename or from the
                document's text, not a determination.
              */}
              <span className="ws-field__help">
                {typeSource === "filename" ? (
                  <>Pre-filled from the filename. Change it if that&rsquo;s wrong. </>
                ) : typeSource === "assist" ? (
                  <>Suggested from the document&rsquo;s opening text. Change it if that&rsquo;s wrong. </>
                ) : !contractType ? (
                  <>Couldn&rsquo;t identify the type from the filename or the text — please choose it. </>
                ) : null}
                Nothing is recorded until you confirm.
              </span>
          </label>

          <button
            type="submit"
            className="ws-btn ws-btn--primary"
            disabled={!name.trim() || !contractType}
          >
            Confirm &amp; Analyze
          </button>
        </div>
      ) : null}

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

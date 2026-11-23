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
 * suggestion; the reader never selects a type (AM-64, 2026-09-13) — the
 * analysis; the evaluator still refuses an undeclared type. Only when the
 * document's text does not say what it is does the intake ask its one question.
 *
 * Best-effort chaining, honest degradation: a missing published snapshot or a
 * missing review.create permission never blocks the upload — the workspace's
 * own states say what happened and who unblocks it. A `duplicate_of` result is
 * surfaced (34.5: reported, never suppressed) on the workspace note.
 *
 * Dashboard UI improvements (2026-09-29): this component now renders inside a
 * compact modal (`UploadContractDialog`) rather than an inline disclosure
 * panel — it no longer owns its own heading, the caller's dialog chrome
 * carries "Upload a contract". It also gained an explicit "selected" stage: a
 * chosen file is shown with its name/size/type before any network call is
 * made, and the upload/analysis chain below starts only once the reader
 * activates "Upload & Analyze" — nothing here changed about the chain itself
 * (still create → upload → suggest type → analyze), only when it starts.
 */

import Link from "next/link";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, describeError } from "@/lib/api";
import { documentTypeLabel, nameFromFilename } from "@/lib/documentTypes";
import { RETURNED_COPY } from "@/lib/labels";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { preflightProblem, startContract } from "@/lib/upload";

import { IconCheckCircle, IconFile, IconXCircle } from "./icons";
import { contractHref } from "./model";
import { FilePicker } from "@/components/FilePicker";

type Stage = "idle" | "selected" | "uploading" | "extracted" | "suggesting" | "analyzing";

const CHECKLIST_ORDER: Stage[] = ["uploading", "extracted", "suggesting", "analyzing"];

/** "2.4 MB" / "820 KB" — whichever unit the reference's selected-file row uses. */
function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** The extension alone, as the reference's file-type label ("PDF", "DOCX"). */
function fileTypeLabel(name: string): string {
  const ext = name.split(".").pop();
  return ext ? ext.toUpperCase() : "FILE";
}

export function UploadContract({ firstRun, onClose }: {
  firstRun: boolean;
  /** Cancel/close the enclosing dialog — called from the Cancel action while
   *  a file is selected but not yet uploading. */
  onClose: () => void;
  /** Kept for callers; the intake no longer asks for declared facts — they
   *  live in "Edit details", where they always were too (AM-50). */
  counterparties?: string[] | undefined;
}) {
  const { can } = useSession();
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [paper, setPaper] = useState<"ours" | "client" | null>(null);
  const [paperMissing, setPaperMissing] = useState(false);
  const [name, setName] = useState("");
  const [contractType, setContractType] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<unknown>(null);
  /** The type the intake recorded on the reader's behalf (AM-50) — shown as
   *  "Reviewed as …" while the analysis starts. */
  const [recordedType, setRecordedType] = useState<string | null>(null);

  if (!can(P.CONTRACT_CREATE) || !can(P.DOCUMENT_UPLOAD)) {
    return firstRun ? (
      <p className="ws-pane__note">Your account does not include document upload.</p>
    ) : null;
  }

  /** A file is chosen (drag or browse): validated and shown, nothing sent yet.
   *  Do not upload a file until the reader activates "Upload & Analyze". */
  function choose(chosen: File | null) {
    if (!chosen || stage !== "idle") return;
    const problem = preflightProblem(chosen);
    if (problem) {
      setFile(null);
      setError(problem);
      return;
    }
    setFile(chosen);
    setName(nameFromFilename(chosen.name));
    setContractType("");
    setError(null);
    setStage("selected");
  }

  function removeFile() {
    setFile(null);
    setError(null);
    setStage("idle");
    if (fileInput.current) fileInput.current.value = "";
  }

  /** create → upload → suggest type → analyze (`lib/upload.startContract`, one chain for
   *  every upload page), started explicitly rather than the instant a file is picked. */
  async function startUpload() {
    if (!file) return;
    if (!paper) { setPaperMissing(true); return; }
    setError(null);
    setStage("uploading");
    try {
      // verifier item 7 / AM-324 r4: whose paper it is travels with the file
      const { contractId } = await startContract(file, paper === "ours" ? "COMPANY_DRAFT" : "CLIENT_MODIFIED", {
        name, canReview: can(P.REVIEW_CREATE),
        onStep: (step, type) => {
          // AM-50: a confident suggestion is recorded and shown as "Reviewed as …"
          if (step === "analyzing") { setRecordedType(type); if (type) setContractType(type); }
          setStage(step);
        },
      });
      router.push(contractHref(contractId));   // AM-263: the contract's own address
    } catch (cause) {
      setError(cause);
      setStage("selected");
    }
  }

  if (!file) {
    return (
      <FilePicker primary inputRef={fileInput} onFile={choose}
                  error={error ? (
                    <p className="ws-field__error" role="alert">
                      {typeof error === "string" ? error : describeError(error)}
                    </p>
                  ) : null} />
    );
  }

  if (stage === "selected") {
    return (
      <div className="ws-upload-selected">
        <div className="ws-upload-file">
          <span className="ws-upload-file__icon" aria-hidden="true"><IconFile size={20} /></span>
          <span className="ws-upload-file__meta">
            <span className="ws-upload-file__name">{file.name}</span>
            <span className="ws-upload-file__sub ws-num">
              {formatFileSize(file.size)} · {fileTypeLabel(file.name)}
            </span>
          </span>
          <span className="ws-upload-file__ok" aria-hidden="true"><IconCheckCircle size={18} /></span>
          <button
            type="button"
            className="ws-upload-file__remove"
            aria-label={`Remove ${file.name}`}
            onClick={removeFile}
          >
            <IconXCircle size={18} />
          </button>
        </div>
        <fieldset className="ws-field ws-upload-paper" aria-describedby={paperMissing ? "ws-upload-paper-error" : undefined}>
          <legend className="ws-field__label">Whose paper is it?</legend>
          {(["ours", "client"] as const).map((which) => (
            <label key={which} className="ws-upload-paper__opt">
              <input type="radio" name="ws-upload-paper" value={which} checked={paper === which}
                     onChange={() => { setPaper(which); setPaperMissing(false); }} />
              <span>{which === "ours" ? "Our draft" : "The client's paper"}</span>
            </label>
          ))}
          {paper === "ours" ? (   // S5: a returned markup of ours has its own start
            <p className="ws-pane__note">{RETURNED_COPY.ourDraftHint}{" "}
              <Link href="/contracts/new/returned">{RETURNED_COPY.ourDraftLink}</Link></p>
          ) : null}
          {paperMissing ? <p className="ws-field__error" id="ws-upload-paper-error">Choose whose paper it is</p> : null}
        </fieldset>
        {error ? (
          <p className="ws-field__error" role="alert">
            {error instanceof ApiError ? describeError(error) : String(error)}
          </p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="ws-btn ws-btn--primary" onClick={() => void startUpload()}>
            Upload &amp; Analyze
          </button>
        </div>
      </div>
    );
  }

  const stageIndex = CHECKLIST_ORDER.indexOf(stage);

  return (
    <div className="ws-intake" aria-labelledby="ws-upload-title">
      <h3 className="ws-intake__title">
        {file.name} <span className="ws-num ws-intake__size">{formatFileSize(file.size)}</span>
      </h3>

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
              <>Reviewed as <strong>{documentTypeLabel(recordedType)}</strong> — read from the document</>
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

      {error ? (
        <p className="ws-field__error" role="alert">
          {error instanceof ApiError ? describeError(error) : "The upload could not be completed."}
        </p>
      ) : null}
    </div>
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

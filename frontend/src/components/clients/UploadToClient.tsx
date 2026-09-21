"use client";

/**
 * Upload a document straight onto a client — or a new version of one already
 * there.
 *
 * **Every call here already existed.** Create the contract (now carrying
 * `counterparty_id`, so it lands linked in one call), upload the file to it,
 * declare what the version is, and run the existing analysis chain. There is no
 * new upload path, no second file store, and the bytes go to exactly the same
 * `POST /contracts/{id}/document-versions` the Dashboard uses — which is why a
 * document uploaded here appears on the Dashboard too, immediately.
 *
 * **Two modes, one gesture.** "A new document" creates the contract; "a new
 * version of" adds to a contract that already exists and never touches the
 * versions under it (locked 42.4's unique `(contract_id, version_number)`
 * guarantees the old one stays, and Step 26 makes it immutable). The owner's
 * requirement that a revision must not overwrite its predecessor is therefore
 * structural, not a promise this component keeps.
 *
 * **The type is asked for, not inferred.** The intake on the Dashboard records
 * a confident suggestion (`AM-50`); this form is the deliberate, one-document
 * path a reader takes when they already know what they are filing, so it offers
 * the Step 6 list with a filename hint the reader must click to accept. Nothing
 * is written from the filename on its own.
 */

import { useRef, useState } from "react";

import { api, describeError } from "@/lib/api";
import { chainAnalysis } from "@/lib/analysisChain";
import {
    VERSION_ROLES,
  nameFromFilename,
} from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Counterparty } from "@/lib/types";

/** Mirrors the server's own limit (`LEGALMIND_MAX_UPLOAD_BYTES`, 25 MB). A
 *  convenience pre-check for an immediate message — 34.16 keeps the server's
 *  validation the authority, and it sniffs the bytes regardless. */
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SUPPORTED = [".pdf", ".docx", ".md", ".txt"];

function preflight(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED.some((ext) => name.endsWith(ext))) {
    return "This file type is not supported. Please choose a PDF, DOCX, Markdown or text file.";
  }
  if (file.size === 0) return "This file is empty. Please choose another file.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return "This file exceeds the 25 MB limit. Please choose a smaller file.";
  }
  return null;
}

export function UploadToClient({ client, onDone, initialContractId }: {
  client: Counterparty;
  onDone: () => void | Promise<void>;
  /** Pre-selects "a new version of" a specific document — how a document
   *  row's own "Upload new version" action opens this same panel rather
   *  than building a second one. The reader can still change it; this only
   *  saves the one lookup when the intent is already known. */
  initialContractId?: string;
}) {
  const { can } = useSession();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  /** "" means a new document; otherwise the contract a new version belongs to. */
  const [intoContractId, setIntoContractId] = useState(initialContractId ?? "");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const existing = (client.contracts ?? []).filter((c) => !c.archived_at);

  function choose(chosen: File | null) {
    setError(null);
    if (!chosen) { setFile(null); return; }
    const problem = preflight(chosen);
    if (problem) { setFile(null); setError(problem); return; }
    setFile(chosen);
    if (!intoContractId) setName(nameFromFilename(chosen.name));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      let contractId = intoContractId;
      if (!contractId) {
        setStep("Creating the document record…");
        // ONE call, already linked: an upload that created the contract and then
        // failed to link it would put the document in LegalMind but not on this
        // client's page — the outcome this feature exists to prevent.
        const contract = await api.createContract(
          name.trim() || nameFromFilename(file.name),
          undefined,
          client.id,
        );
        contractId = contract.id;
      }

      setStep("Uploading…");
      const uploaded = await api.uploadDocument(contractId, file);

      // AM-64 (owner, 2026-09-13): the reader never selects a type. The assist
      // lane's CONFIDENT inference is recorded and audited as the intake does
      // (AM-50); an unconfident one records nothing, and the review is
      // content-first either way (AM-60/AM-61). Best-effort: a failure here
      // never stops the upload or the review.
      if (!intoContractId) {
        setStep("Reading what kind of document this is…");
        try {
          const proposed = await api.suggestType(uploaded.document_version.id);
          if (proposed.confident && proposed.suggested_type) {
            await api.updateContract(contractId, {
              contract_type: proposed.suggested_type,
              contract_type_source: "ASSIST_SUGGESTION",
            });
          }
        } catch {
        }
      }

      // What this version IS. Declared before analysis on purpose: locked 33.7
      // freezes a version's declared metadata once a Review exists, so the
      // order here is the difference between a recorded role and a 409.
      if (role) {
        setStep("Recording what this version is…");
        try {
          await api.declareVersion(uploaded.document_version.id,
                                   { version_role: role });
        } catch {
          // Best-effort: the document is uploaded and safe. The version list
          // offers the same choice again rather than losing the upload over it.
        }
      }

      setStep("Starting the review…");
      await chainAnalysis(contractId, can(P.REVIEW_CREATE));
      await onDone();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
      setStep(null);
    }
  }

  return (
    <form className="ws-cl__upload" id="ws-cl-upload" onSubmit={submit}
          aria-labelledby="ws-cl-upload-title">
      <h3 id="ws-cl-upload-title">Upload a document for {client.name}</h3>

      <div className="ws-cl__upload-grid">
        <label className="ws-field ws-cl__form-wide">
          <span className="ws-field__label">
            File <span className="ws-field__req">(required)</span>
          </span>
          <input ref={fileInput} type="file" accept=".pdf,.docx,.md,.txt" required
                 disabled={busy}
                 onChange={(event) => choose(event.target.files?.[0] ?? null)} />
          <span className="ws-field__help">PDF, DOCX, Markdown or text, up to 25 MB.</span>
        </label>

        <label className="ws-field">
          <span className="ws-field__label">This is</span>
          <select value={intoContractId} disabled={busy}
                  onChange={(event) => setIntoContractId(event.target.value)}>
            <option value="">A new document</option>
            {existing.map((contract) => (
              <option key={contract.id} value={contract.id}>
                A new version of &ldquo;{contract.name}&rdquo;
              </option>
            ))}
          </select>
          {intoContractId ? (
            <span className="ws-field__help">
              Added as the next version. The versions already there are kept
              exactly as they are.
            </span>
          ) : null}
        </label>

        <label className="ws-field">
          <span className="ws-field__label">Version</span>
          <select value={role} onChange={(event) => setRole(event.target.value)}
                  disabled={busy}>
            <option value="">Not classified</option>
            {VERSION_ROLES.map((r) => (
              <option key={r.role} value={r.role}>{r.label} — {r.hint}</option>
            ))}
          </select>
        </label>

        {/* Name and type belong to the DOCUMENT, so they are asked for only
            when a document is being created — a new version of an existing one
            inherits both, and offering to change them here would quietly edit
            the document while the reader thought they were filing a revision. */}
        {!intoContractId ? (
          <>
            <label className="ws-field">
              <span className="ws-field__label">Document name</span>
              <input value={name} onChange={(event) => setName(event.target.value)}
                     maxLength={500} disabled={busy}
                     placeholder="Taken from the filename" />
            </label>
          </>
        ) : null}
      </div>

      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}

      <div className="ws-cl__form-acts">
        {step ? (
          <span className="ws-pane__note" role="status" aria-live="polite">{step}</span>
        ) : null}
        <span className="ws-cl__spacer" />
        <button type="submit" className="ws-btn ws-btn--primary"
                disabled={busy || !file}>
          {busy ? "Working…" : "Upload"}
        </button>
      </div>
    </form>
  );
}

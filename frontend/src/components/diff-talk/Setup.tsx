"use client";

/**
 * Diff-Talk's SETUP mode: two numbered document slots — choose from a list, or drop
 * / browse a file. Each list offers only its own side (Step 6's source axis: an
 * upload is declared ORGANIZATION or COUNTERPARTY as it lands).
 */

import { useState } from "react";

import { IconCheck, IconUploadCloud } from "@/components/workspace/icons";
import { api, describeError, uploadFirstDocument } from "@/lib/api";
import { documentTypeChip, nameFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, WebsiteDocument } from "@/lib/types";

type Option = { value: string; label: string };

/** Deferred-OCR wait after an upload — WorkspacePage's 3 s cadence, capped at 3 min. */
const OCR_POLL_MS = 3000;
const OCR_POLL_LIMIT = 60;
const isReading = (status: string) => status === "PENDING" || status === "PROCESSING";

const option = (c: Contract): Option => {
  const chip = documentTypeChip(c.contract_type);
  return { value: c.latest_version!.id, label: chip ? `${c.name} (${chip})` : c.name };
};

export function Setup({ left, right, website, documents, listError, onChange, onUploaded }: {
  left: string;
  right: string;
  website: WebsiteDocument[];
  documents: Contract[];
  listError: string | null;
  onChange: (left: string, right: string) => void;
  /** After an upload: refresh the lists, then select it (or not, `null`). */
  onUploaded: (side: "left" | "right", ref: string | null) => Promise<void>;
}) {
  const ours = documents.filter((c) => c.latest_version?.source === "ORGANIZATION");
  const theirs = documents.filter((c) => c.latest_version?.source !== "ORGANIZATION");
  return (
    <section className="ws-dt ws-dt--setup" aria-label="Choose the two documents">
      {listError ? <p className="ws-dt__msg is-error" role="alert">{listError}</p> : null}
      <div className="ws-dt__slots">
        <Slot step={1} label="Our document" source="ORGANIZATION" value={left}
              hint="A website document is always today's version — no upload needed."
              placeholder="Choose our document…"
              groups={[
                { label: "Website documents",
                  options: website.map((w) => ({ value: w.key, label: w.title })) },
                { label: "Uploaded by us", options: ours.map(option) },
              ]}
              onChange={(ref) => onChange(ref, right)}
              onUploaded={(ref) => onUploaded("left", ref)} />
        <Slot step={2} label="Client contract" source="COUNTERPARTY" value={right}
              hint="The client's paper — any type, any numbering."
              placeholder="Choose the client contract…"
              groups={[{ label: "Client documents in LegalMind", options: theirs.map(option) }]}
              onChange={(ref) => onChange(left, ref)}
              onUploaded={(ref) => onUploaded("right", ref)} />
      </div>
      <p className="ws-dt__setupnote">
        The two are lined up clause by clause — even when the client numbers, orders or
        words them differently — and only the differences are shown.
      </p>
    </section>
  );
}

function Slot({ step, label, hint, placeholder, value, source, groups, onChange, onUploaded }: {
  step: 1 | 2;
  label: string;
  hint: string;
  placeholder: string;
  value: string;
  source: "ORGANIZATION" | "COUNTERPARTY";
  groups: { label: string; options: Option[] }[];
  onChange: (ref: string) => void;
  onUploaded: (ref: string | null) => Promise<void>;
}) {
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const id = `dt-pick-${step}`;
  const chosen = groups.flatMap((g) => g.options).find((o) => o.value === value);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      // An ordinary LegalMind document — same storage, parsing, access and audit as
      // any upload; a refused file: the shared helper archives the empty contract.
      const contract = await api.createContract(nameFromFilename(file.name));
      const result = await uploadFirstDocument(contract.id, file);
      const versionId = result.document_version.id;
      // An ordinary document, declared ours or theirs. Deliberately NOT analysed
      // here: a review spends Gemini calls (semantic recognition, type suggestion)
      // the reader did not ask for — the Dashboard's Analyze runs it when wanted
      // (strict review 2026-10-13; the Gemini cost guard).
      await api.declareVersion(versionId, { source });
      // A scanned PDF is read by a deferred OCR pass (seconds, ~60 s at worst):
      // wait for it here rather than send the reader away (2026-10-17 — the
      // pass finished 2 s after upload and the slot still said "come back").
      let version = result.document_version;
      for (let polls = 0; polls < OCR_POLL_LIMIT && isReading(version.processing_status); polls++) {
        await new Promise((done) => window.setTimeout(done, OCR_POLL_MS));
        version = await api.documentVersion(versionId).catch(() => version);
      }
      const status = version.processing_status;
      const unreadable = result.evidence_count === 0 &&
        (isReading(status) || status === "FAILED" || version.extraction_status === "FAILED");
      if (unreadable) {
        // Nothing readable to compare: selecting it would only land on an error
        // screen (QA 2026-10-13). Say why, and what to do; the file is kept.
        await onUploaded(null);
        setError(isReading(status)
          ? `“${file.name}” is uploaded and its scanned pages are being read. Choose it from the list in a minute or two.`
          : `No text could be read from “${file.name}”. Upload a PDF with selectable text, or the Word (DOCX) file.`);
        return;
      }
      await onUploaded(versionId);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`ws-dt__slot${chosen ? " is-filled" : ""}`}>
      <div className="ws-dt__slothead">
        <span className="ws-dt__stepno" aria-hidden="true">{chosen ? <IconCheck size={14} /> : step}</span>
        <div>
          <label className="ws-dt__slotlabel" htmlFor={id}>{label}</label>
          <p className="ws-dt__hint">{hint}</p>
        </div>
      </div>
      <select id={id} className="ws-dt__select" value={value}
              onChange={(e) => { setError(null); onChange(e.target.value); }}>
        <option value="">{placeholder}</option>
        {groups.filter((g) => g.options.length).map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </optgroup>
        ))}
      </select>
      {can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD) ? (
        <label className={`ws-dt__drop${over ? " is-over" : ""}${busy ? " is-busy" : ""}`}
               onDragOver={(e) => { e.preventDefault(); setOver(true); }}
               // Only when the pointer leaves the zone itself, not one of its children.
               onDragLeave={(e) => {
                 if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
               }}
               onDrop={(e) => {
                 e.preventDefault();
                 setOver(false);
                 const file = e.dataTransfer.files?.[0];
                 if (file && !busy) void upload(file);
               }}>
          <IconUploadCloud size={20} />
          <span>
            {busy ? "Uploading and reading the file — a scanned PDF takes up to a minute…" : (
              <><strong>Upload a file</strong> — drop a PDF or DOCX here, or click to browse</>
            )}
          </span>
          <input type="file" accept=".pdf,.docx,.md,.txt" disabled={busy}
                 className="ws-visually-hidden"
                 onChange={(e) => {
                   const file = e.target.files?.[0];
                   e.target.value = "";
                   if (file) void upload(file);
                 }} />
        </label>
      ) : null}
      {error ? <p className="ws-dt__msg is-error" role="alert">{error}</p> : null}
    </div>
  );
}

"use client";

/**
 * ONE unified list of every legal document for one client — the feature's
 * central requirement, and the one it is easiest to get wrong.
 *
 * ⚠️ **There is no grouping here, by design.** Every document for the client is
 * one `<tbody>` in one `<table>`, in one order, whatever its type. Document
 * type travels as a chip in a column and as an optional filter, and that is
 * the whole of its role: the owner's instruction is explicit that type must not
 * become a folder hierarchy, and the server backs it up by returning a flat
 * array with no grouping key at all. If a future change wants MSA/NDA/SLA
 * sections, that is a product decision to take to the owner — not a rendering
 * choice to make here.
 *
 * **Nothing on this screen re-implements the document system.** A row is a
 * Contract that already exists; opening one goes to the existing workspace,
 * analysing one calls the existing `chainAnalysis`, downloading one uses the
 * existing content endpoint, and comparing versions opens the existing
 * comparison in that workspace. Rule 18: no legal evaluation happens here, and
 * every status shown is rendered exactly as the server sent it (52.7).
 *
 * **Versions are a disclosure under their document**, newest first, never a
 * replacement for it — a new version has never overwritten an older one
 * (locked 42.4's unique `(contract_id, version_number)`, and Step 26's
 * immutability), and this list makes that visible rather than merely true.
 */

import Link from "next/link";
import { useMemo, useState } from "react";

import { api, describeError } from "@/lib/api";
import { chainAnalysis } from "@/lib/analysisChain";
import {
  VERSION_ROLES,
  documentTypeChip,
  documentTypeLabel,
  versionRoleLabel,
  versionRoleTone,
} from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ClientContract, Counterparty, DocumentVersion } from "@/lib/types";

import {
  documentStatusBucket,
  relativeTime,
  STATUS_BUCKET_LABEL,
  type DocumentStatusBucket,
} from "@/components/workspace/model";
import {
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
} from "@/components/workspace/findingLanguage";
import {
  IconAlertCircle,
  IconCheckCircle,
  IconChevronRight,
  IconClock,
} from "@/components/workspace/icons";

import { currentVersion, typesPresent, versionCountLabel, shortDate } from "./model";
import { LinkExistingDocuments } from "./LinkExistingDocuments";
import { UploadToClient } from "./UploadToClient";

const STATUS_ICON: Record<DocumentStatusBucket, React.ReactNode> = {
  draft: <IconClock size={13} />,
  analyzing: <span className="ws-spin" aria-hidden="true" />,
  needs_attention: <IconAlertCircle size={13} />,
  analyzed: <IconCheckCircle size={13} />,
};

/** The six columns, in one place — the header renders them and so does the
 *  empty row's colspan, which must match or the table's footer detaches. */
const COLUMNS = ["Document", "Type", "Status", "Versions", "Last updated", ""] as const;

/**
 * The reader's three statuses for one document, exactly as the Dashboard shows
 * them — same order, same tones, same absence rule (a dash where nothing has
 * been analyzed, never a zero standing in for "not checked").
 *
 * Reusing `findingLanguage` rather than re-deriving is the point: `AM-56` fixes
 * these three words, and a second screen inventing its own would be the
 * "competing analysis status terminology" the owner ruled out.
 */
function ReaderStatuses({ contract }: { contract: ClientContract }) {
  const bucket = documentStatusBucket(contract);
  const counts = contract.latest_analysis?.user_status_counts;
  if (bucket === "draft" || bucket === "analyzing" || !counts) return null;
  return (
    <span className="ws-findings-cell">
      {USER_STATUS_ORDER.map((status) => {
        const n = counts[status] ?? 0;
        return (
          <span key={status}
                className={`ws-findings-badge ws-findings-badge--${USER_STATUS_TONE[status]}${n === 0 ? " ws-findings-badge--zero" : ""}`}
                title={`${n} ${USER_STATUS_LABELS[status]}`}>
            {n}
          </span>
        );
      })}
    </span>
  );
}

/** One version, under its document. The role is the reader's own words
 *  ("Company draft" / "Client modified" / "Final signed") and simply absent
 *  where nobody declared one — never guessed from the version number. */
function VersionRow({
  contract, version, isCurrent, onChanged,
}: {
  contract: ClientContract;
  version: DocumentVersion;
  isCurrent: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const role = versionRoleLabel(version.version_role);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const blob = await api.documentContentBlob(version.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = version.original_filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="ws-cl__ver">
      <span className="ws-cl__ver-n ws-mono">v{version.version_number}</span>
      <span className="ws-cl__ver-main">
        {role ? (
          <span className={`ws-cl__role ws-cl__role--${versionRoleTone(version.version_role)}`}>
            {role}
          </span>
        ) : (
          <span className="ws-cl__absent">Not classified</span>
        )}
        <span className="ws-cl__ver-file">{version.original_filename}</span>
      </span>
      <span className="ws-cl__ver-when">
        {shortDate(version.created_at) ?? "—"}
        {isCurrent ? <span className="ws-cl__ver-current"> · current</span> : null}
      </span>
      <span className="ws-cl__ver-acts">
        <Link className="ws-btn ws-btn--sm"
              href={`/dashboard?id=${contract.id}&version=${version.id}`}>
          Open
        </Link>
        {/* Only where the caller may actually have the bytes. Absent, never
            disabled — a control you cannot invoke is not rendered (52.3). */}
        {can(P.DOCUMENT_DOWNLOAD) ? (
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => void download()}
                  disabled={busy}>
            {busy ? "Preparing…" : "Download"}
          </button>
        ) : null}
        {/* The version's declared role. Owner-only server-side, and refused
            with 409 once the version has a Review (locked 33.7) — the message
            says so rather than this screen pretending to know. */}
        {can(P.DOCUMENT_UPLOAD) ? (
          <RoleControl version={version} onChanged={onChanged} />
        ) : null}
      </span>
      {error ? (
        <span className="ws-field__error ws-cl__ver-error" role="alert">
          {describeError(error)}
        </span>
      ) : null}
    </li>
  );
}

/** Declare what a version is — the one write this list makes, through the
 *  existing `PATCH /document-versions/{id}`. No new endpoint, no new column. */
function RoleControl({ version, onChanged }: {
  version: DocumentVersion;
  onChanged: () => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function choose(role: string) {
    setBusy(true);
    setError(null);
    try {
      await api.declareVersion(version.id, { version_role: role || null });
      await onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <label className="ws-cl__rolepick">
        <span className="ws-visually-hidden">
          What version {version.version_number} is
        </span>
        <select value={version.version_role ?? ""} disabled={busy}
                title="What this version is in the negotiation"
                onChange={(event) => void choose(event.target.value)}>
          <option value="">Not classified</option>
          {/* Short labels, deliberately. A native select renders the SELECTED
              option's full text, so "Final signed — what was executed" made
              this control the widest thing in the row and then truncated it
              anyway. The three hints are stated once, in the panel note above
              the list, where they are read rather than clipped. */}
          {VERSION_ROLES.map((role) => (
            <option key={role.role} value={role.role}>{role.label}</option>
          ))}
        </select>
      </label>
      {error ? (
        <span className="ws-field__error ws-cl__ver-error" role="alert">
          {describeError(error)}
        </span>
      ) : null}
    </>
  );
}

/** One document, and its versions underneath on request. */
function DocumentRow({ contract, onChanged }: {
  contract: ClientContract;
  onChanged: () => void | Promise<void>;
}) {
  const { can } = useSession();
  const [open, setOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const bucket = documentStatusBucket(contract);
  const versions = contract.versions ?? [];
  const current = currentVersion(versions);
  const panelId = `ws-cl-versions-${contract.id}`;

  async function analyze() {
    setAnalyzing(true);
    setError(null);
    try {
      // The EXISTING chain, unchanged: create the Review against the published
      // snapshot and run it. This screen adds no analysis of its own and could
      // not — the engine is server-side and deterministic (rule 10, AI-01).
      await chainAnalysis(contract.id, can(P.REVIEW_CREATE));
      await onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setAnalyzing(false);
    }
  }

  const analyzed = bucket === "analyzed" || bucket === "needs_attention";
  return (
    <>
      <tr className={bucket === "needs_attention" ? "ws-tr--attention" : undefined}>
        <td>
          <Link className="ws-cl__docname" href={`/dashboard?id=${contract.id}`}>
            {contract.name}
          </Link>
          {contract.archived_at ? (
            <span className="ws-chip">Archived</span>
          ) : null}
        </td>
        <td>
          {contract.contract_type ? (
            // The SHORT form in the cell, the full label as its title: a column
            // is no place for "PRIVACY_POLICY", and an underscore is not a word.
            <span className="ws-chip ws-chip--type"
                  title={documentTypeLabel(contract.contract_type)}>
              {documentTypeChip(contract.contract_type)}
            </span>
          ) : (
            <span className="ws-cl__absent">Not recorded</span>
          )}
        </td>
        <td>
          <span className={`ws-status-pill ws-status-pill--${bucket}`}>
            {STATUS_ICON[bucket]} {STATUS_BUCKET_LABEL[bucket]}
          </span>
          <ReaderStatuses contract={contract} />
        </td>
        <td>
          {versions.length > 0 ? (
            <button type="button" className="ws-cl__vertoggle"
                    aria-expanded={open} aria-controls={panelId}
                    onClick={() => setOpen((was) => !was)}>
              <span className={`ws-cl__chev${open ? " ws-cl__chev--open" : ""}`}
                    aria-hidden="true">
                <IconChevronRight size={13} />
              </span>
              {versionCountLabel(versions.length)}
            </button>
          ) : (
            <span className="ws-cl__absent">No file yet</span>
          )}
        </td>
        <td className="ws-mono">{relativeTime(contract.updated_at)}</td>
        <td className="ws-cl__rowacts">
          {/* Analyze where there is a document and no analysis; Review where
              there is one. One control, saying which it is. */}
          {current && !analyzed && can(P.REVIEW_CREATE) ? (
            <button type="button" className="ws-btn ws-btn--sm"
                    onClick={() => void analyze()} disabled={analyzing}>
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
          ) : null}
          {analyzed ? (
            <Link className="ws-btn ws-btn--sm" href={`/dashboard?id=${contract.id}`}>
              Review
            </Link>
          ) : null}
          {/* The existing comparison, in the workspace that owns it — only
              where there are two versions to compare. Never a control that
              opens onto nothing. */}
          {versions.length > 1 ? (
            <Link className="ws-btn ws-btn--sm"
                  href={`/dashboard?id=${contract.id}&compare=1`}>
              Compare
            </Link>
          ) : null}
        </td>
      </tr>
      {error ? (
        <tr>
          <td colSpan={COLUMNS.length}>
            <p className="ws-field__error" role="alert">{describeError(error)}</p>
          </td>
        </tr>
      ) : null}
      {open && versions.length > 0 ? (
        <tr className="ws-cl__verrow">
          <td colSpan={COLUMNS.length}>
            <div id={panelId} className="ws-cl__vers">
              <p className="ws-pane__note">
                Newest first. Every version is kept — uploading a revision never
                replaces the one before it. <strong>Company draft</strong> is
                what we sent, <strong>Client modified</strong> is what came
                back, and <strong>Final signed</strong> is what was executed.
              </p>
              <ul className="ws-cl__verlist">
                {versions.map((version) => (
                  <VersionRow key={version.id} contract={contract} version={version}
                              isCurrent={version.id === current?.id}
                              onChanged={onChanged} />
                ))}
              </ul>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function ClientDocuments({ client, onChanged }: {
  client: Counterparty;
  onChanged: () => void | Promise<void>;
}) {
  const { can } = useSession();
  const [typeFilter, setTypeFilter] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const contracts = client.contracts ?? [];

  const types = useMemo(() => typesPresent(contracts), [contracts]);
  // A FILTER over the one list — never a split of it into sections.
  const shown = typeFilter
    ? contracts.filter((c) => c.contract_type === typeFilter)
    : contracts;

  const canUpload = can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD);
  const canLink = can(P.CONTRACT_UPDATE);

  return (
    <section className="ws-cl__docs" aria-labelledby="ws-cl-docs-title">
      <header className="ws-cl__docs-head">
        <h2 id="ws-cl-docs-title">Legal documents</h2>
        {contracts.length > 0 ? (
          <span className="ws-cl__docs-count ws-mono">
            {contracts.length}
          </span>
        ) : null}
        <span className="ws-cl__spacer" />
        {/* The type filter appears only once there is more than one type to
            choose between — a select with one option is furniture. */}
        {types.length > 1 ? (
          <label className="ws-cl__filter">
            <span className="ws-visually-hidden">Filter by document type</span>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {types.map((code) => (
                <option key={code} value={code}>{documentTypeLabel(code)}</option>
              ))}
            </select>
          </label>
        ) : null}
        {canLink && !linkOpen ? (
          <button type="button" className="ws-btn ws-btn--sm"
                  aria-expanded={false} onClick={() => { setLinkOpen(true); setUploadOpen(false); }}>
            Link existing
          </button>
        ) : null}
        {canUpload ? (
          <button type="button" className="ws-btn ws-btn--sm ws-btn--primary"
                  aria-expanded={uploadOpen} aria-controls="ws-cl-upload"
                  onClick={() => { setUploadOpen((was) => !was); setLinkOpen(false); }}>
            {uploadOpen ? "Close" : "+ Upload document"}
          </button>
        ) : null}
      </header>

      {uploadOpen ? (
        <UploadToClient client={client} onDone={async () => {
          setUploadOpen(false);
          await onChanged();
        }} />
      ) : null}

      {linkOpen ? (
        <LinkExistingDocuments client={client} onClose={() => setLinkOpen(false)}
                               onLinked={onChanged} />
      ) : null}

      {contracts.length === 0 ? (
        <div className="ws-state">
          <h3>No legal documents for this client yet.</h3>
          <p>
            Upload a document to start building this client&rsquo;s legal record —
            or link one that is already in LegalMind.
          </p>
          {canUpload && !uploadOpen ? (
            <button type="button" className="ws-btn ws-btn--primary"
                    onClick={() => setUploadOpen(true)}>
              + Upload document
            </button>
          ) : null}
        </div>
      ) : (
        <div className="ws-cl__table">
          <table>
            <caption className="ws-visually-hidden">
              Every legal document for {client.name}, in one list. Document type
              is shown in its own column and is not a grouping.
            </caption>
            <thead>
              <tr>
                {COLUMNS.map((column, index) => (
                  <th key={column || `act-${index}`} scope="col">
                    {column || <span className="ws-visually-hidden">Actions</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 ? (
                <tr>
                  <td colSpan={COLUMNS.length}>
                    <p className="ws-pane__note">
                      No {documentTypeLabel(typeFilter)} documents for this
                      client.{" "}
                      <button type="button" className="ws-btn ws-btn--link"
                              onClick={() => setTypeFilter("")}>
                        Show all types
                      </button>
                    </p>
                  </td>
                </tr>
              ) : (
                shown.map((contract) => (
                  <DocumentRow key={contract.id} contract={contract}
                               onChanged={onChanged} />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

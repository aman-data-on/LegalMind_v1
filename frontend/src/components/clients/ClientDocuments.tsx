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
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { api, describeError } from "@/lib/api";
import { chainAnalysis } from "@/lib/analysisChain";
import { CONTRACT_STATUSES } from "@/lib/labels";
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

import { Dialog } from "@/components/Dialog";
import {
  documentStatusBucket,
  relativeTime,
  STATUS_BUCKET_LABEL,
  type DocumentStatusBucket,
} from "@/components/workspace/model";
import {
  IconAlertCircle,
  IconCheckCircle,
  IconChevronRight,
  IconClock,
} from "@/components/workspace/icons";

import { currentVersion, typesPresent, shortDate } from "./model";
import { LinkExistingDocuments } from "./LinkExistingDocuments";
import { UploadToClient } from "./UploadToClient";

/**
 * A document row's overflow menu.
 *
 * **Portaled, not the simpler absolutely-positioned menu `ClientWorkspace`'s
 * own header uses** — that one works there specifically because the header
 * has no clipping ancestor (its own comment says so). This one lives inside
 * `.ws-cl__table`, which sets `overflow-x: auto` — and per the CSS spec,
 * setting only `overflow-x` computes `overflow-y` to `auto` too, so a plain
 * absolutely-positioned dropdown would be silently clipped at the table's own
 * edge for any row not near the very bottom. Mirrors the Dashboard's own row
 * menu fix for the identical problem (`app/dashboard/page.tsx`, 2026-09-03):
 * fixed-viewport coordinates captured from the toggle at open time, portaled
 * into `.ws` itself (not `document.body`) so every design token — surface
 * color, radius, `--ws-z-dialog` — still resolves; `.ws` sets no transform of
 * its own, so `position: fixed` still measures against the real viewport.
 *
 * Deliberately simpler than the Dashboard's copy in one respect: no arrow-key
 * navigation between items (that menu can hold up to four; this one holds at
 * most three, and Tab/Escape closing plus pointer clicks cover the same
 * ground for a menu this short).
 */
function DocMenu({ children, label }: { children: ReactNode; label: string }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top?: number; bottom?: number; right: number; minWidth: number } | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  function openMenu() {
    const toggle = toggleRef.current;
    if (!toggle) return;
    const rect = toggle.getBoundingClientRect();
    const cellRect = toggle.closest("td")?.getBoundingClientRect() ?? rect;
    const estimatedHeight = 132; // up to three items plus padding
    const opensAbove = window.innerHeight - rect.bottom < estimatedHeight + 8;
    setPos({
      right: window.innerWidth - rect.right,
      minWidth: Math.max(168, cellRect.width),
      ...(opensAbove ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
    });
    setOpen(true);
  }

  function close(restoreFocus = false) {
    setOpen(false);
    setPos(null);
    if (restoreFocus) toggleRef.current?.focus();
  }

  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      if (!listRef.current?.contains(event.target as Node)
          && !toggleRef.current?.contains(event.target as Node)) close();
    }
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" && event.key !== "Tab") return;
      event.stopPropagation();
      close(event.key === "Escape");
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ws-menu">
      <button ref={toggleRef} type="button"
              className="ws-btn ws-btn--sm ws-menu__toggle"
              aria-haspopup="menu" aria-expanded={open} aria-label={label}
              onClick={() => (open ? close() : openMenu())}>
        ⋯
      </button>
      {open && pos
        ? createPortal(
            <div ref={listRef} className="ws-menu__list" role="menu"
                 aria-orientation="vertical"
                 style={{
                   position: "fixed", right: pos.right, minWidth: pos.minWidth,
                   ...(pos.top !== undefined ? { top: pos.top } : { bottom: pos.bottom }),
                 }}
                 onClick={() => close()}>
              {children}
            </div>,
            document.querySelector(".ws") ?? document.body,
          )
        : null}
    </div>
  );
}

/**
 * Edit a document's name and status — the same `PATCH /contracts/{id}` the
 * Dashboard's own `EditContractDialog` already uses. Deliberately narrower
 * than that dialog: `counterparty_id` is not offered here, because changing
 * it from a client's own document list would silently move the document to
 * a DIFFERENT client, which is a distinct act this screen does not attempt
 * to gate or explain. The declared-per-version fields (source/counterparty/
 * effective date) are likewise the Dashboard's own concern, not repeated
 * here — this dialog is the document's identity, not its negotiation facts.
 */
function EditDocumentDialog({
  contract, onClose, onSaved,
}: { contract: ClientContract; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(contract.name);
  const [status, setStatus] = useState(contract.status);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.updateContract(contract.id, {
        name: name.trim(),
        ...(status !== contract.status ? { status } : {}),
      });
      onSaved();
    } catch (cause) {
      setError(cause);
      setSaving(false);
    }
  }

  return (
    <Dialog onClose={onClose} titleId="ws-cl-docedit-title" dismissOnScrimClick={false}>
      <h2 id="ws-cl-docedit-title">Edit document details</h2>
      <form onSubmit={save}>
        <label className="ws-field">
          <span className="ws-field__label">Name</span>
          <input required maxLength={500} value={name}
                 onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {CONTRACT_STATUSES.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-modal__acts">
          <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="ws-btn ws-btn--primary"
                  disabled={saving || !name.trim()}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/**
 * Detach a document from THIS client without touching the document itself —
 * the safe action regardless of whether it was uploaded here or linked from
 * elsewhere, since neither case is distinguished in the data (AB-13: no
 * relationship table, relatedness is derived from `counterparty_id` alone).
 * Same `PATCH /contracts/{id}` as declaring any other field; `counterparty_id:
 * null` is exactly what "not linked" already means in `EditContractDialog`.
 */
function RemoveFromClientDialog({
  contract, onClose, onRemoved,
}: { contract: ClientContract; onClose: () => void; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.updateContract(contract.id, { counterparty_id: null });
      onRemoved();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <Dialog onClose={onClose} titleId="ws-cl-docremove-title">
      <h2 id="ws-cl-docremove-title">Remove this document from the client?</h2>
      <p className="ws-modal__body"><strong>{contract.name}</strong></p>
      <p className="ws-modal__body">
        This only removes it from this client&rsquo;s list. The document itself,
        its versions, findings and audit trail are unchanged — it becomes
        unlinked, exactly like a document that was never linked to a client.
      </p>
      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--bad"
                disabled={busy} onClick={() => void confirm()}>
          {busy ? "Removing…" : "Remove from client"}
        </button>
      </div>
    </Dialog>
  );
}

/**
 * Genuinely destroy a document — the same `DELETE /contracts/{id}` (`AM-55`)
 * and the same warning copy as the Dashboard's own `DeleteContractDialog`.
 * One interruption pattern for one kind of act, deliberately: a reader who
 * has seen this dialog once on the Dashboard should not be surprised by a
 * differently-worded one here.
 */
function DeleteDocumentDialog({
  contract, onClose, onDeleted,
}: { contract: ClientContract; onClose: () => void; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteContract(contract.id);
      onDeleted();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <Dialog onClose={onClose} titleId="ws-cl-docdel-title">
      <h2 id="ws-cl-docdel-title">Delete this document permanently?</h2>
      <p className="ws-modal__body"><strong>{contract.name}</strong></p>
      <p className="ws-modal__body">
        This cannot be undone. The document, every version, and any findings,
        evaluations and legal decisions on it are destroyed. If you may want
        this back, remove it from the client instead — that keeps the document.
      </p>
      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--bad"
                disabled={busy} onClick={() => void confirm()}>
          {busy ? "Deleting…" : "Delete permanently"}
        </button>
      </div>
    </Dialog>
  );
}

const STATUS_ICON: Record<DocumentStatusBucket, React.ReactNode> = {
  draft: <IconClock size={13} />,
  analyzing: <span className="ws-spin" aria-hidden="true" />,
  needs_attention: <IconAlertCircle size={13} />,
  analyzed: <IconCheckCircle size={13} />,
};

/** The columns, in one place — the header renders them and so does the
 *  empty row's colspan, which must match or the table's footer detaches.
 *
 *  "Agreement stage" and "Review status" are deliberately separate columns
 *  (owner, 2026-09-18): the first is what the negotiation reached — a fact
 *  about the FILE (`version_role`, declared per version) — and the second is
 *  what LegalMind's review found — a judgement about the CONTENT (`AM-56`'s
 *  three reader words). A document can be `Final signed` and still `Needs
 *  attention`; stacking those in one "Status" cell answered the wrong
 *  question half the time. */
const COLUMNS = [
  "Document", "Type", "Agreement stage", "Review status", "Versions",
  "Last updated", "",
] as const;

/**
 * Whether any Finding under this document specifically needs a human
 * decision — the sharpest of the three AM-56 reader statuses, and the one
 * "Needs attention" alone does not distinguish from an ordinary deviation.
 *
 * Deliberately no number here (owner, 2026-09-19): the main row states a
 * fact ("this needs a decision"), not a count to skim-read as a severity
 * score — the detailed breakdown, with its counts, is one click away in the
 * Review itself. Reads `user_status_counts` — already computed and sent by
 * the server (`AM-56`) — rather than deriving anything new.
 */
function needsDecision(contract: ClientContract): boolean {
  const counts = contract.latest_analysis?.user_status_counts;
  return Boolean(counts && (counts.NEEDS_DECISION ?? 0) > 0);
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
      </span>
      {/* Always occupies its grid slot, present or not — otherwise a row
          without the badge loses a column and every row after it drifts out
          of alignment with the ones that have it. */}
      <span className="ws-cl__ver-current">
        {isCurrent ? <span className="ws-chip">Current</span> : null}
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
function DocumentRow({ contract, onChanged, onUploadNewVersion }: {
  contract: ClientContract;
  onChanged: () => void | Promise<void>;
  onUploadNewVersion: (contractId: string) => void;
}) {
  const { can, identity } = useSession();
  const [open, setOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [editingDoc, setEditingDoc] = useState(false);
  const [removingDoc, setRemovingDoc] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState(false);
  const bucket = documentStatusBucket(contract);
  const versions = contract.versions ?? [];
  const current = currentVersion(versions);
  const currentRole = versionRoleLabel(current?.version_role);
  const panelId = `ws-cl-versions-${contract.id}`;
  // Presentation only (rule 18) — the server re-checks ownership on every
  // write regardless of what this screen offers, the same gate the
  // Dashboard's own row menu uses (`isMine`).
  const isMine = contract.owner_id === identity?.user_id;

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
          {/* `title` keeps the full name reachable when the CSS below clamps
              a long one to two lines — a hover/long-press affordance, not a
              replacement for the visible text (rule 18: presentation only). */}
          <Link className="ws-cl__docname" href={`/dashboard?id=${contract.id}`}
                title={contract.name}>
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
          {/* The CURRENT version's declared role — the same badge VersionRow
              already draws below, just surfaced here so a reader never has to
              open history to learn whether this is a draft or the executed
              copy. Same helper, same tone rule (DD-18 §3): only `FINAL_SIGNED`
              carries colour, the rest read by their text alone. */}
          {current && currentRole ? (
            <span className={`ws-cl__role ws-cl__role--${versionRoleTone(current.version_role)}`}>
              {currentRole}
            </span>
          ) : (
            <span className="ws-cl__absent">Not classified</span>
          )}
        </td>
        <td className="ws-cl__reviewcell">
          {/* "Needs decision" is a refinement WITHIN the "Needs attention"
              bucket (`documentStatusBucket` sets that bucket for ANY non-
              ACCEPTABLE finding, `NEEDS_DECISION` included), never a
              different or independent condition — so showing both read as
              the same fact said twice (owner, 2026-09-22). The sharper word
              replaces the generic one only in that one case; a document
              whose only issue is REQUIRES_MODIFICATION still reads "Needs
              attention" exactly as before, since that bucket has no sharper
              word of its own to offer. Every other bucket (Draft, Analyzing,
              No issues) is untouched. */}
          {bucket === "needs_attention" && needsDecision(contract) ? (
            <span className="ws-cl__decision">Needs decision</span>
          ) : (
            <span className={`ws-status-pill ws-status-pill--${bucket}`}>
              {STATUS_ICON[bucket]} {STATUS_BUCKET_LABEL[bucket]}
            </span>
          )}
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
              {/* "View history" states the action; the count stays alongside it
                  rather than replacing it — "3 versions" on its own read as a
                  fact with no control attached (owner, 2026-09-18). */}
              View history ({versions.length})
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
          {/* Same permission split as the Dashboard's own row menu: editing
              needs CONTRACT_UPDATE, removing/deleting need CONTRACT_ARCHIVE
              (the same grant `AM-55` already gates the permanent delete
              with), both additionally scoped to the caller's own document. */}
          {(can(P.CONTRACT_UPDATE) || can(P.CONTRACT_ARCHIVE) || can(P.DOCUMENT_UPLOAD))
           && isMine ? (
            <DocMenu label={`More actions for ${contract.name}`}>
              {can(P.CONTRACT_UPDATE) && !contract.archived_at ? (
                <button type="button" role="menuitem" className="ws-menu__item"
                        onClick={() => setEditingDoc(true)}>
                  Edit details
                </button>
              ) : null}
              {/* Opens the SAME upload panel the toolbar's "+ Upload document"
                  does, pre-selecting "a new version of" this document — no
                  second upload path, no new endpoint (owner, 2026-09-21).
                  Gated like the panel gates a new version: DOCUMENT_UPLOAD,
                  and the contract must not be archived (a write the server
                  would otherwise refuse with 409). */}
              {can(P.DOCUMENT_UPLOAD) && !contract.archived_at ? (
                <button type="button" role="menuitem" className="ws-menu__item"
                        onClick={() => onUploadNewVersion(contract.id)}>
                  Upload new version
                </button>
              ) : null}
              {can(P.CONTRACT_ARCHIVE) ? (
                <button type="button" role="menuitem" className="ws-menu__item"
                        onClick={() => setRemovingDoc(true)}>
                  Remove from client
                </button>
              ) : null}
              {can(P.CONTRACT_ARCHIVE) ? (
                <button type="button" role="menuitem"
                        className="ws-menu__item ws-menu__item--bad"
                        onClick={() => setDeletingDoc(true)}>
                  Delete permanently
                </button>
              ) : null}
            </DocMenu>
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
      {editingDoc ? (
        <EditDocumentDialog contract={contract}
                            onClose={() => setEditingDoc(false)}
                            onSaved={() => { setEditingDoc(false); void onChanged(); }} />
      ) : null}
      {removingDoc ? (
        <RemoveFromClientDialog contract={contract}
                                onClose={() => setRemovingDoc(false)}
                                onRemoved={() => { setRemovingDoc(false); void onChanged(); }} />
      ) : null}
      {deletingDoc ? (
        <DeleteDocumentDialog contract={contract}
                              onClose={() => setDeletingDoc(false)}
                              onDeleted={() => { setDeletingDoc(false); void onChanged(); }} />
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
  /** Set when the panel was opened from a document row's "Upload new
   *  version" action, so it opens already targeting that document. */
  const [uploadTarget, setUploadTarget] = useState<string | undefined>(undefined);
  const [linkOpen, setLinkOpen] = useState(false);
  const contracts = client.contracts ?? [];

  function openUploadFor(contractId: string) {
    setUploadTarget(contractId);
    setUploadOpen(true);
    setLinkOpen(false);
    // The panel renders above the table; from a row far down a long list it
    // would otherwise open off-screen with no indication anything happened.
    requestAnimationFrame(() => {
      document.getElementById("ws-cl-upload")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

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
                  onClick={() => {
                    setUploadOpen((was) => !was);
                    setUploadTarget(undefined);
                    setLinkOpen(false);
                  }}>
            {uploadOpen ? "Close" : "+ Upload document"}
          </button>
        ) : null}
      </header>

      {uploadOpen ? (
        <UploadToClient client={client} {...(uploadTarget ? { initialContractId: uploadTarget } : {})}
                        onDone={async () => {
                          setUploadOpen(false);
                          setUploadTarget(undefined);
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
        /* `--docs` scopes the fixed-layout column widths below to THIS table.
           `.ws-cl__table` is shared with `ClientDirectory`'s own list, whose
           columns are entirely different — an unscoped width rule on the
           shared class would have silently resized a screen this change
           never intended to touch. */
        <div className="ws-cl__table ws-cl__table--docs">
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
                               onChanged={onChanged}
                               onUploadNewVersion={openUploadFor} />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

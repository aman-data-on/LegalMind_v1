"use client";

/**
 * R2 (owner, 2026-11-16): what a lawyer reads off a client's change — lettered points,
 * who each binds, the standards it touches — the notes across clauses, and the internal
 * review table (preview first, then the Word file). The server computes all of it; this
 * only presents (rule 18). Nothing here is a point's status or a decision.
 */
import { useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { ErrorState, LoadingState } from "@/components/Feedback";
import { api, describeError } from "@/lib/api";
import type { ChangeList, ClientChange } from "@/lib/changes";
import { LAWYER_COPY, MUTUALITY_LABELS, PARTY_LABELS, POINT_KIND_LABELS } from "@/lib/labels";
import { saveBlob } from "@/lib/pdfDownload";
import { requirementTitle } from "./findingLanguage";

function boundLine(bound: string | null, benefits: string | null): string | null {
  if (!bound) return null;
  if (bound === "BOTH") return "Binds both sides.";
  return `Binds ${PARTY_LABELS[bound]}; helps ${PARTY_LABELS[benefits ?? ""] ?? "the other side"}.`;
}

/** The change as lettered points, with the standards it touches and who it binds. */
export function LetteredPoints({ change }: { change: ClientChange }) {
  const view = change.lawyer;
  if (!view || view.points.length < 2) return null;
  const s = view.standards;
  return (
    <section className="cx-lawyer" aria-label={LAWYER_COPY.pointsTitle}>
      <h4 className="cx-label">{LAWYER_COPY.pointsTitle}</h4>
      {view.mutuality ? <p className="cx-lawyer__meta">{MUTUALITY_LABELS[view.mutuality]}</p> : null}
      <ol className="cx-lawyer__list">
        {view.points.map((p) => (
          <li key={p.letter}>
            <strong>({p.letter}) {POINT_KIND_LABELS[p.kind]}:</strong>{" "}
            {p.after ?? p.before}
            {boundLine(p.bound, p.benefits) ? <span className="cx-lawyer__meta"> {boundLine(p.bound, p.benefits)}</span> : null}
          </li>
        ))}
      </ol>
      <p className="cx-lawyer__meta">
        {s.source === "FINDING" ? `${LAWYER_COPY.standardsFrom}: ${s.codes.map((code) => requirementTitle({ code })).join(", ")}.`
          : s.source === "HEADING_TOPIC" ? `${LAWYER_COPY.topicFrom}: ${s.topics.map((t) => t.title).join(", ")}.`
            : LAWYER_COPY.legalDecides}
      </p>
    </section>
  );
}

/** Notes across clauses for Legal: never points, never a status. */
export function NotesForLegal({ list }: { list: Pick<ChangeList, "notes_for_legal"> }) {
  const notes = list.notes_for_legal ?? [];
  if (!notes.length) return null;
  return (
    <details className="cx-banner cx-lawyer__notes">
      <summary>{LAWYER_COPY.notesTitle} ({notes.length})</summary>
      <p className="cx-lawyer__meta">{LAWYER_COPY.notesHelp}</p>
      <ul>{notes.map((n, i) => <li key={`${n.kind}-${i}`}>{n.text}</li>)}</ul>
    </details>
  );
}

type Table = { head: string[]; rows: string[][]; internal: string };

/** The internal review table: a preview, and the Word file from inside it. */
export function ReviewTableButton({ contractId }: { contractId: string }) {
  const [open, setOpen] = useState(false);
  const [table, setTable] = useState<Table | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  function load() {
    setError(null);
    setTable(null);
    api.reviewTable(contractId).then(setTable, (cause: unknown) => setError(cause ?? true));
  }
  async function download() {
    setBusy(true);
    setFailed(null);
    try {
      saveBlob(await api.reviewTableFile(contractId), "review-table.docx");
    } catch (cause) {
      setFailed(`${LAWYER_COPY.downloadFailed}. ${describeError(cause)}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm" onClick={() => { setOpen(true); load(); }}>
        {LAWYER_COPY.tableButton}
      </button>
      {open ? (
        <Dialog onClose={() => setOpen(false)} titleId="cx-table-title" returnFocus={() => trigger.current}>
          <h2 id="cx-table-title">{LAWYER_COPY.tableTitle}</h2>
          {table ? <p className="cx-lawyer__meta">{table.internal}</p> : null}
          {error ? <ErrorState title={LAWYER_COPY.tableFailed} error={error} onRetry={load} heading="h3" />
            : table === null ? <LoadingState label="Loading the review table" />
              : (
                <div className="cx-lawyer__table" tabIndex={0} role="region" aria-label={LAWYER_COPY.tableTitle}>
                  <table>
                    <thead><tr>{table.head.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
                    <tbody>{table.rows.map((r) => <tr key={r[0]}>{r.map((v, i) => <td key={i}>{v}</td>)}</tr>)}</tbody>
                  </table>
                </div>
              )}
          {failed ? <p className="cx-error" role="alert">{failed}</p> : null}
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" onClick={() => setOpen(false)}>Close</button>
            <button type="button" className="ws-btn ws-btn--primary" disabled={busy || table === null}
                    onClick={() => void download()}>
              {busy ? "Preparing…" : LAWYER_COPY.download}
            </button>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}

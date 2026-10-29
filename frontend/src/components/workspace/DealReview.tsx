"use client";

/**
 * A client's documents reviewed side by side (`AM-229`): one row per point, what each
 * document says (in plain words where they passed the figure check, `AM-232`, with the
 * clause's own words one click away), our rule, and the status with what to do. The
 * status is the contract review's and the reader's answers — never the AI's — so it is
 * shown in words beside its icon, never by colour alone. Points that are fine can be
 * hidden; the client's changes no rule checks are listed for a person to read.
 */
import { useId, useState } from "react";

import { Dialog } from "@/components/Dialog";
import type { DealCell, DealFile, DealRow, DealStatus } from "@/lib/types";

import {
  IconAlertCircle,
  IconCheckCircle,
  IconCopy,
  IconFileDiff,
  IconLock,
  IconMaximize,
  IconScale,
  IconXCircle,
} from "./icons";

export const STATUS: Record<DealStatus, { label: string; Icon: typeof IconCheckCircle }> = {
  MUST_CHANGE: { label: "Must change", Icon: IconXCircle },
  ASK_CHANGE: { label: "Ask for a change", Icon: IconAlertCircle },
  LEGAL_DECIDES: { label: "Legal decides", Icon: IconScale },
  AGREED: { label: "Agreed (signed)", Icon: IconLock },
  FINE: { label: "Fine", Icon: IconCheckCircle },
};
const ORDER: DealStatus[] = ["MUST_CHANGE", "ASK_CHANGE", "LEGAL_DECIDES", "AGREED", "FINE"];

function Chip({ status }: { status: DealStatus }) {
  const { label, Icon } = STATUS[status];
  return <span className="ws-deal__chip" data-status={status}><Icon size={14} />{label}</span>;
}

/** Our rule's value in words where it has the usual shape; else only its section. */
function ruleText(rule: DealRow["rule"]): string {
  const v = rule.value as { preferred?: unknown; unit?: string } | undefined;
  const value = v && v.preferred !== undefined && v.unit
    ? `${String(v.preferred)} ${v.unit.toLowerCase()}` : "";
  return [rule.section ? `Section ${rule.section}` : "", value].filter(Boolean).join(" · ");
}

function Cell({ cell }: { cell: DealCell | undefined }) {
  if (!cell) return <span className="ws-deal__none">Not covered</span>;
  if (cell.classification === "MISSING") return <span className="ws-deal__none">Not stated</span>;
  return (
    <div className="ws-deal__cell">
      <p>{cell.plain ?? (cell.quote ? `“${cell.quote.slice(0, 220)}${cell.quote.length > 220 ? "…" : ""}”`
        : "See the clause")}</p>
      <p className="ws-deal__where">
        {cell.clause ? `Clause ${cell.clause}` : null}
        {cell.changed ? <span className="ws-deal__changed"><IconFileDiff size={12} />
          Changed by the client</span> : null}
      </p>
      {cell.plain && cell.quote ? (
        <details className="ws-deal__quote">
          <summary>Exact words</summary>
          <blockquote>{cell.quote}</blockquote>
        </details>
      ) : null}
    </div>
  );
}

/** The table as Markdown, for pasting into an e-mail or a document. */
export function asMarkdown(files: DealFile[], rows: DealRow[]): string {
  const head = ["Topic", ...files.map((f) => f.name), "Our rule", "Status → what to do"];
  const say = (c: DealCell | undefined) => !c ? "—" : c.classification === "MISSING"
    ? "Not stated" : (c.plain ?? c.quote).replace(/\|/g, "/").replace(/\s+/g, " ");
  const lines = rows.map((r) => {
    const lead = r.decided_by ? r.cells[r.decided_by] : undefined;
    const todo = [STATUS[r.status].label, lead?.action].filter(Boolean).join(" — ");
    const also = r.also.map((a) => `${files.find((f) => f.id === a.file)?.name}: `
      + STATUS[a.status].label).join("; ");
    return [r.topic ?? r.code, ...files.map((f) => say(r.cells[f.id])), ruleText(r.rule),
            [todo, also].filter(Boolean).join(" · ")];
  });
  return [head, head.map(() => "---"), ...lines].map((l) => `| ${l.join(" | ")} |`).join("\n");
}

/** The rows: our rule sits under the topic in the chat, in its own column at full width. */
function ReviewTable({ files, rows, wide = false }: {
  files: DealFile[];
  rows: DealRow[];
  wide?: boolean;
}) {
  const name = (id: string) => files.find((f) => f.id === id)?.name ?? "Document";
  return (
    <div className="ws-deal__scroll" role="region" aria-label="Review table" tabIndex={0}
         data-wide={wide ? "" : undefined}>
      <table className="ws-deal__table">
        <thead>
          <tr>
            <th scope="col">Topic</th>
            {files.map((f) => <th key={f.id} scope="col">{f.name}</th>)}
            {wide ? <th scope="col">Our rule</th> : null}
            <th scope="col">Status → what to do</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const lead = r.decided_by ? r.cells[r.decided_by] : undefined;
            const rule = ruleText(r.rule);
            return (
              <tr key={r.code} data-needs={r.needs}>
                <th scope="row">
                  <span className="ws-deal__topic">{r.topic ?? r.code}</span>
                  {r.detail ? <span className="ws-deal__detail">{r.detail}</span> : null}
                  {!wide && rule ? <span className="ws-deal__rule">Our rule: {rule}</span> : null}
                </th>
                {files.map((f) => (
                  <td key={f.id} data-label={f.name}><Cell cell={r.cells[f.id]} /></td>
                ))}
                {wide ? <td data-label="Our rule">{rule || "—"}</td> : null}
                <td data-label="Status">
                  <Chip status={r.status} />
                  {r.note === "files_differ" ? (
                    <p className="ws-deal__todo">The documents differ and none was named to
                      win: a person decides.</p>
                  ) : lead?.action ? <p className="ws-deal__todo">{lead.action}</p> : null}
                  {r.also.map((a) => (
                    <p key={a.file} className="ws-deal__also">
                      <span>{name(a.file)}:</span> <Chip status={a.status} />
                      {a.action ? <span className="ws-deal__todo"> {a.action}</span> : null}
                    </p>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function DealReview({ files, rows, counts }: {
  files: DealFile[];
  rows: DealRow[];
  counts: Record<DealStatus, number>;
}) {
  const [allRows, setAllRows] = useState(false);
  const [copied, setCopied] = useState(false);
  const [full, setFull] = useState(false);
  const titleId = useId();
  const shown = allRows ? rows : rows.filter((r) => r.needs !== "FINE");
  const unchecked = files.flatMap((f) => f.unchecked.map((u) => ({ ...u, file: f.name })));
  return (
    <section className="ws-deal" aria-label="Side-by-side review">
      <ul className="ws-deal__counts" aria-label="Points by status">
        {ORDER.map((s) => (
          <li key={s}><Chip status={s} /><strong>{counts[s] ?? 0}</strong></li>
        ))}
      </ul>
      <ul className="ws-deal__files">
        {files.map((f) => (
          <li key={f.id}>
            <strong>{f.name}</strong>
            {f.signed ? <span className="ws-deal__tag">Signed</span> : null}
            {f.wins ? <span className="ws-deal__tag">Wins where they differ</span> : null}
            {f.changes ? <span className="ws-deal__tag">{f.changes} client changes</span> : null}
            {f.refused ? <span className="ws-deal__tag" data-warn="">Could not be read whole</span>
              : null}
          </li>
        ))}
      </ul>
      <div className="ws-deal__tools">
        <label className="ws-deal__toggle">
          <input type="checkbox" checked={allRows} onChange={(e) => setAllRows(e.target.checked)} />
          Show the {counts.FINE ?? 0} points that are fine
        </label>
        <span className="ws-deal__btns">
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => setFull(true)}>
            <IconMaximize size={14} />Full screen
          </button>
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => {
            void navigator.clipboard?.writeText(asMarkdown(files, rows)).then(() => setCopied(true));
          }}>
            <IconCopy size={14} />{copied ? "Copied" : "Copy as table"}
          </button>
        </span>
      </div>
      {full ? (
        <Dialog onClose={() => setFull(false)} titleId={titleId} overlayClassName="ws-modal--deal">
          <h2 id={titleId}>Side-by-side review</h2>
          <ReviewTable files={files} rows={shown} wide />
          <div className="ws-modal__acts">
            <button type="button" className="ws-btn" onClick={() => setFull(false)}>Close</button>
          </div>
        </Dialog>
      ) : null}
      <ReviewTable files={files} rows={shown} />
      {unchecked.length ? (
        <details className="ws-deal__unchecked">
          <summary>{unchecked.length} client changes no rule checks — read them</summary>
          <ul>
            {unchecked.map((u, i) => (
              <li key={`${u.file}-${u.clause}-${i}`}>
                <span className="ws-deal__where">{u.file} · clause {u.clause} · {u.kind}</span>
                {u.removed ? <del>{u.removed}</del> : null}
                {u.added ? <ins>{u.added}</ins> : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {files.some((f) => f.notes.length) ? (
        <details className="ws-deal__unchecked">
          <summary>The client&rsquo;s comments</summary>
          <ul>
            {files.flatMap((f) => f.notes.map((n, i) => (
              <li key={`${f.id}-${i}`}>
                <span className="ws-deal__where">{f.name} · clause {n.clause}</span>{n.text}
              </li>
            )))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

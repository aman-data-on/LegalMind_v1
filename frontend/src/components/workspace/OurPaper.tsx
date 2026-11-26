"use client";

/**
 * `AM-476` (lawyer judgement P1): "What it replaces in our paper". Each reference the
 * client's paper makes into our MSA, Terms of Service, SLA or AUP — grouped by the
 * client's sentence, then each clause of ours it reaches with our own words from the
 * version the server pinned (said once per document), or the server's reason it could
 * not be looked up. No direction, effect or favour (rule 7); the one marker is a phrase
 * quoted from our own text. Read only; the server decides what each reader receives
 * (five rows and a count for sales; file, SHA-256 and the MSA choices for Legal only).
 */
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { ErrorState, LoadingState } from "@/components/Feedback";
import { toast } from "@/components/Toast";
import { ApiError, api, describeError } from "@/lib/api";
import { OUR_PAPER_COPY as T } from "@/lib/labels";
import { type OurPaper, type PaperPin, type PaperRow, onOurPaper, ourPaper, reloadOurPaper } from "@/lib/ourPaper";

function useOurPaper(contractId: string) {
  const [data, setData] = useState<OurPaper | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => {
    setError(null);
    ourPaper(contractId).then(setData, (cause: unknown) => setError(cause ?? true));
  }, [contractId]);
  useEffect(() => { load(); return onOurPaper(contractId, load); }, [contractId, load]);
  return { data, error, retry: () => reloadOurPaper(contractId) };
}

function target(r: PaperRow): string {
  const doc = T.docName[r.doc] ?? r.doc;
  if (!r.number) return `${doc} ${T.described(r.described ?? "")}`;
  const n = r.number + (r.sub ? `(${r.sub})` : "");
  return `${doc} ${r.doc === "MSA" ? T.clause(n) : T.section(n)}`;
}

export function said(r: PaperRow): string {
  return (T.verb[r.verb] ?? T.verb.REFERS!)(target(r));
}

/** Our quote without the heading the line above already names ("17.2. Monetary Cap: …"). */
export function withoutHeading(quote: string, number: string | null, title: string | null): string {
  let q = number ? quote.replace(new RegExp(`^${number.replace(/\./g, "\\.")}\\.?\\s*`), "") : quote;
  if (title && q.toLowerCase().startsWith(title.toLowerCase())) q = q.slice(title.length).replace(/^\s*[:.–-]\s*/, "");
  return q;
}

function OurQuote({ row }: { row: PaperRow }) {
  const [all, setAll] = useState(false);
  if (!row.ours) return null;
  const text = withoutHeading(row.ours.quote, row.number, row.ours.title);
  const long = text.length > 420;
  return (
    <figure className="op-quote op-quote--ours">
      <figcaption className="cx-label">{T.ours}{row.ours.title ? `: ${row.ours.title}` : null}</figcaption>
      <blockquote className={long && !all ? "op-clamp" : undefined}>{text}</blockquote>
      {long ? <button type="button" className="ws-escalate__link" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? T.showLess : T.showAll}</button> : null}
    </figure>
  );
}

/** One clause of ours the client's sentence reaches: what it says, why it was not found,
 *  our quote, and only the exceptions (changed since, earliest copy, by wording). */
export function Row({ row, onPick }: { row: PaperRow; onPick?: (() => void) | undefined }) {
  const reason = row.status === "RESOLVED" ? null : T.status[row.status];
  return (
    <li className="op-row">
      <p className="op-row__head"><strong>{said(row)}</strong>
        {row.title ? <span className="cx-lawyer__meta"> The client calls it &ldquo;{row.title}&rdquo;.</span> : null}</p>
      {reason ? <p className="op-row__reason">{reason}
        {row.hint?.earliest ? ` ${T.earliest(row.hint.earliest)}` : null}
        {row.status === "WHICH_MSA" && onPick ? <> <button type="button" className="ws-escalate__link" onClick={onPick}>{T.pickLink}</button></> : null}
      </p> : null}
      <OurQuote row={row} />
      {row.markers?.length ? <p className="op-fact">{T.contains} {row.markers.map((m) => `«${m}»`).join(", ")}.</p> : null}
      {row.blank ? <p className="op-fact">{T.blank} «{row.blank}»</p> : null}
      {row.mode === "DESCRIBED" && row.ours ? <p className="cx-lawyer__meta">{T.byWording}</p> : null}
      {row.changed_since?.date ? <p className="cx-lawyer__meta">{T.changedSince(row.changed_since.date)}</p> : null}
    </li>
  );
}

type Group = { source: string | null; quote: string; rows: PaperRow[] };
function groups(rows: PaperRow[]): Group[] {
  const out: Group[] = [];
  for (const r of rows) {
    const last = out[out.length - 1];
    if (last && last.source === r.source && last.quote === r.client_quote) last.rows.push(r);
    else out.push({ source: r.source, quote: r.client_quote, rows: [r] });
  }
  return out;
}

function PinLine({ doc, pin }: { doc: string; pin: PaperPin }) {
  const name = T.docName[doc] ?? doc;
  if (pin.unresolved) return <li>{T.pin(name)} {T.status[pin.unresolved]}</li>;
  const how = pin.picked ? T.pickedBy(pin.picked.by_you ? T.you : pin.picked.by ?? T.someone, pin.picked.on)
    : pin.how ? T.how[pin.how] : null;
  return (
    <li>
      {T.pin(name)} {pin.label}{how ? `, ${how}` : pin.date && pin.how ? `, ${T.stored(pin.date)}` : null}.
      {pin.sha256 ? (
        <details className="op-detail"><summary>{T.fileDetail}</summary>
          <p className="cx-lawyer__meta op-sha">{pin.file}. SHA-256 {pin.sha256}</p></details>
      ) : null}
    </li>
  );
}

function PickMsa({ contractId, pin, selectId, onDone }: { contractId: string; pin: PaperPin; selectId: string; onDone: () => void }) {
  const choices = pin.hint?.choices ?? [];
  const [chosen, setChosen] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const choice = chosen === "" ? null : choices[Number(chosen)];
  const fits = (label: string) => pin.hint?.fingerprint?.find((f) => f.label === label);
  async function set() {
    if (!choice) return;
    setBusy(true);
    setFailed(null);
    try {
      await api.pickMsa(contractId, choice.template_version_id ? { template_version_id: choice.template_version_id }
        : { contract_id: choice.contract_id ?? "" });
      setConfirm(false);
      toast(T.setDone);
      onDone();
    } catch (cause) {
      setConfirm(false);
      setFailed(cause instanceof ApiError && cause.status === 403 ? T.onlyLegal : describeError(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="op-pick">
      <label htmlFor={selectId} className="cx-label">{T.pickLabel}</label>
      <select id={selectId} className="ws-dt__select" value={chosen} onChange={(e) => setChosen(e.target.value)}>
        <option value="">{T.choose}</option>
        {choices.map((c, i) => {
          const f = fits(c.label);
          return <option key={i} value={String(i)}>{c.label}{f ? ` (${T.fits(f.fits, f.of)})` : ""}</option>;
        })}
      </select>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm" disabled={!choice} onClick={() => setConfirm(true)}>{T.setButton}</button>
      {failed ? <p className="cx-error" role="alert">{failed}</p> : null}
      {confirm && choice ? (
        <Dialog onClose={() => setConfirm(false)} titleId={`${selectId}-confirm`} returnFocus={() => trigger.current}>
          <h2 id={`${selectId}-confirm`}>{T.confirmTitle}</h2>
          <p>{T.confirmBody(choice.label)}</p>
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" onClick={() => setConfirm(false)}>{T.cancel}</button>
            <button type="button" className="ws-btn ws-btn--primary" disabled={busy} onClick={() => void set()}>{T.setButton}</button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

/** The Changes tab's panel: closed by default, one line; every row for Legal, five for
 *  sales and a count. */
export function OurPaperPanel({ contractId }: { contractId: string }) {
  const { data, error, retry } = useOurPaper(contractId);
  const selectId = useId();
  const [open, setOpen] = useState(false);
  const [changing, setChanging] = useState(false);
  if (error) return <ErrorState title={T.failed} error={error} onRetry={retry} heading="h3" />;
  if (data === null) return <div className="cx-banner"><LoadingState label={T.checking} rows={1} /></div>;
  if (!data.rows.length) return <p className="cx-banner cx-lawyer__meta">{T.none}</p>;
  const msa = data.pins?.MSA;
  const total = data.rows.length + (data.more_for_legal ?? 0);
  const picking = data.can_pick && msa && (msa.unresolved || changing);
  const pick = () => {
    setOpen(true);
    if (msa?.picked) setChanging(true);
    window.requestAnimationFrame(() => document.getElementById(selectId)?.focus());
  };
  return (
    <details className="cx-banner op-panel" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary><h3 className="op-panel__title">{T.title}</h3> <span className="cx-lawyer__meta">{T.count(total)}{open ? null : <>. {T.show}</>}</span></summary>
      <p className="cx-lawyer__meta">{T.help} {T.readOn(data.on, data.on_from === "DOCUMENT")}</p>
      <ul className="op-pins">
        {Object.keys(T.docName).filter((d) => data.pins?.[d]).map((doc) => <PinLine key={doc} doc={doc} pin={data.pins![doc]!} />)}
      </ul>
      {msa?.picked && data.can_pick && !changing ? (
        <button type="button" className="ws-escalate__link" onClick={() => setChanging(true)}>{T.change}</button>
      ) : null}
      {picking && msa ? <PickMsa contractId={contractId} pin={msa} selectId={selectId}
                                 onDone={() => { setChanging(false); reloadOurPaper(contractId); }} /> : null}
      <ol className="op-list">
        {groups(data.rows).map((g, i) => (
          <li key={`${g.source}-${i}`} className="op-group">
            <h4 className="op-group__title">{g.source ? T.source(g.source) : T.theirs}</h4>
            <blockquote className="op-quote--theirs">{g.quote}</blockquote>
            <ul className="op-rows">{g.rows.map((r, k) => <Row key={k} row={r} onPick={data.can_pick ? pick : undefined} />)}</ul>
          </li>
        ))}
      </ol>
      {data.more_for_legal ? <p className="cx-lawyer__meta">{T.salesMore(data.rows.length, data.more_for_legal)}</p> : null}
    </details>
  );
}

/** On one change's card (round 2): what that clause says of our paper, in one line. */
export function AlsoInOurPaper({ contractId, clause }: { contractId: string; clause: string | null | undefined }) {
  const { data } = useOurPaper(contractId);
  const rows = (data?.rows ?? []).filter((r) => clause && r.source === clause.replace(/\.$/, ""));
  if (!rows.length) return null;
  return <p className="op-also"><strong>{T.also}</strong> {rows.map(said).join(" ")}</p>;
}

/** The deal brief's one line (S4): how many of our clauses the paper replaces or
 *  overrides; Legal may open the list. Hidden while the client's version is read. */
export function OurPaperLine({ contractId, checking, onChanges }: {
  contractId: string; checking?: boolean; onChanges?: (() => void) | undefined;
}) {
  const { data, error, retry } = useOurPaper(contractId);
  if (checking) return null;
  if (error) return <p className="op-brief">{T.briefFailed} <button type="button" className="ws-escalate__link" onClick={retry}>{T.retry}</button></p>;
  if (!data?.overrides_count || !data.overrides_by_doc) return null;
  return (
    <div className="op-brief">
      <p>{T.brief(data.overrides_by_doc)}{onChanges ? <> <button type="button" className="ws-escalate__link" onClick={onChanges}>{T.seeChanges}</button></> : null}</p>
      {data.overrides?.length ? (
        <details className="op-detail"><summary>{T.showClauses}</summary>
          <p className="cx-lawyer__meta">{data.overrides.join(", ")}.</p></details>
      ) : null}
    </div>
  );
}

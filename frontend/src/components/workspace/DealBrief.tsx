"use client";

/**
 * The deal brief (batch 3+4, AB-218): the first thing on a contract, above
 * the tabs, for the deal owner and for Legal — where the deal stands and who acts next,
 * what the client asks for, what we told them and our own mistake; for Legal, the
 * changes grouped by Legal's own tie and the client's comments. It replaces the
 * Summary's "What needs attention" (never beside it).
 *
 * Everything is the server's (`GET /contracts/{id}/brief`): the numbers are
 * `deal_counts`, a position the reader may not see never arrives (LEGAL-02), and the
 * write controls are drawn only where the server says this reader may record
 * (`can_record`) — every write checks again (rule 18).
 */

import { useCallback, useEffect, useId, useState, type ReactNode } from "react";

import { api, describeError } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { openChange, statusWords, type DealBrief as Brief, type Told } from "@/lib/dealBrief";
import { BRIEF_COPY, NOT_MARKED_COPY, plainClauseSigns, withoutSectionRefs, type StageViewer } from "@/lib/labels";
import type { NegotiationStage } from "@/lib/types";
import { ErrorState } from "@/components/Feedback";
import { toast } from "@/components/Toast";

import { AttentionLine } from "./AnalysisPanel";
import { NotMarked } from "./NotMarked";
import { useFindingsStateOptional } from "./findingsState";
import "./brief.css";

/** The brief, read again whenever the server's counts or stage change (`refreshKey`). */
export function useDealBrief(contractId: string, refreshKey: string) {
  const [state, setState] = useState<{ brief: Brief | null; error: unknown }>({ brief: null, error: null });
  const [seq, setSeq] = useState(0);
  const reload = useCallback(() => setSeq((n) => n + 1), []);
  useEffect(() => {
    let cancelled = false;
    api.dealBrief(contractId).then(
      (brief) => { if (!cancelled) setState({ brief, error: null }); },
      (error: unknown) => { if (!cancelled) setState((was) => ({ brief: was.brief, error })); });
    return () => { cancelled = true; };
  }, [contractId, refreshKey, seq]);
  return { ...state, reload };
}

export function DealBrief({ contractId, stage, viewer, refreshKey, onOpen, onChanged }: {
  contractId: string;
  stage: NegotiationStage | null;
  viewer: StageViewer;
  refreshKey: string;
  /** a change named in the brief: the page switches to Changes and opens it */
  onOpen: (rowKey: string) => void;
  /** what we told them changed: the Changes rows re-read their labels */
  onChanged: () => void;
}) {
  const { brief, error, reload } = useDealBrief(contractId, refreshKey);
  const findings = useFindingsStateOptional();
  // collapsed to three lines until the reader opens it: the document keeps the screen
  const [expanded, setOpen] = useState(false);
  if (error && !brief) {
    return <section className="lm-brief" aria-label={BRIEF_COPY.title}>
      <ErrorState heading="h2" title={BRIEF_COPY.failed} error={error} onRetry={reload} /></section>;
  }
  if (!brief) {
    return (
      <section className="lm-brief" aria-label={BRIEF_COPY.title} aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">{BRIEF_COPY.loading}</p>
        <span className="ws-skel ws-skel--line lm-brief__skel" aria-hidden="true" />
      </section>
    );
  }
  // no round of changes: the points' own line (the Summary's, moved here — never twice)
  const points = findings?.state.kind === "ready" ? (
    <AttentionLine progress={findings.state.progress} stage={stage} viewer={viewer} canDecide={false}
                   counts={brief.counts} />) : null;
  const stale = error ? <p className="lm-brief__stale" role="alert">{BRIEF_COPY.stale}{" "}
    <button type="button" className="ws-linkbtn" onClick={reload}>{BRIEF_COPY.retry}</button></p> : null;
  return <BriefView brief={brief} stale={stale} contractId={contractId} points={points} expanded={expanded}
                    onToggle={() => setOpen(!expanded)} onChanged={() => { reload(); onChanged(); }}
                    // the change opens below: the brief folds back to its three lines
                    onOpen={(key) => { setOpen(false); onOpen(key); window.setTimeout(() => openChange(key), 60); }} />;
}

/** The brief as drawn (exported for the static tests): the server's brief, nothing else. */
export function BriefView({ brief, contractId, points, stale = null, expanded, onToggle, onOpen, onChanged }: {
  brief: Brief; contractId: string; points?: ReactNode; stale?: ReactNode;
  expanded: boolean; onToggle: () => void; onOpen: (rowKey: string) => void; onChanged: () => void;
}) {
  const id = useId();
  const legal = brief.legal;
  const status = statusWords(brief);         // the server's code, in words (rule 18)
  const asks = brief.asks ?? [];
  const unmarked = brief.not_marked;
  // collapsed: three lines — the status, the first line under it (batch 8: the changes
  // not marked come first), the toggle
  const lead = unmarked ? `${(unmarked.highlights_read ? NOT_MARKED_COPY.title : NOT_MARKED_COPY.titleOldFile)(
    unmarked.count, unmarked.total)}.`
    : legal ? (legal.beyond.length ? BRIEF_COPY.startHere(legal.beyond.length) : null)
    : asks.length ? `${BRIEF_COPY.asks}: ${asks.slice(0, 3).map((a) => a.title).join(", ")}${
      asks.length + (brief.asks_more ?? 0) > 3 ? ` ${BRIEF_COPY.asksMore(asks.length + (brief.asks_more ?? 0) - 3)}` : ""}.`
      : null;
  if (!status && !points && !asks.length && !brief.told?.length && !brief.our_mistake && !legal && !unmarked) return null;
  return (
    <section className="lm-brief" aria-labelledby={`${id}-h`} data-testid="deal-brief"
             data-open={expanded || undefined}>
      <h2 id={`${id}-h`} className="ws-visually-hidden">{BRIEF_COPY.title}</h2>
      {status ? <p className="lm-brief__status" data-testid="brief-status">{status}</p> : points ?? null}
      {stale}
      {!expanded ? (lead ? <p className="lm-brief__lead">{lead}</p> : null) : (
        <div className="lm-brief__body" id={`${id}-body`}>
          {unmarked ? (
            <div className="lm-brief__first">
              <NotMarked count={unmarked.count} total={unmarked.total} highlightsRead={unmarked.highlights_read}
                         more={unmarked.more} onOpen={onOpen}
                         // the quote only beside a heading: a name made of the client's own
                         // first words is not said twice
                         items={unmarked.rows.map((r) => ({ rowKey: r.row_key, quote: r.title ? r.quote : undefined,
                                                            name: NOT_MARKED_COPY.clause(r.clause, r.title, r.quote) }))} />
            </div>
          ) : null}
          {legal ? <LegalPart brief={brief} contractId={contractId} onOpen={onOpen} onChanged={onChanged} />
            : <SalesPart brief={brief} />}
        </div>
      )}
      {legal || asks.length || brief.told?.length || brief.our_mistake || unmarked ? (
        <button type="button" className="ws-linkbtn lm-brief__toggle" aria-expanded={expanded}
                aria-controls={`${id}-body`} onClick={onToggle}>
          {expanded ? BRIEF_COPY.showLess : BRIEF_COPY.showAll}
        </button>
      ) : null}
    </section>
  );
}

function SalesPart({ brief }: { brief: Brief }) {
  const asks = brief.asks ?? [];
  return (
    <>
      {asks.length ? (
        <div className="lm-brief__part">
          <h3 className="lm-brief__h">{BRIEF_COPY.asks}</h3>
          <ul className="lm-brief__asks">
            {asks.map((a) => (
              <li key={a.row_key}>
                <span className="lm-brief__ask">{a.title}</span>{" "}
                {a.removed ? `${BRIEF_COPY.removes} ` : ""}
                {/* the client's own quote marks are kept: never doubled */}
                {/^[“"]/.test(a.quote) ? <span className="lm-brief__quote">{plainClauseSigns(a.quote)}</span>
                  : <q className="lm-brief__quote">{plainClauseSigns(a.quote)}</q>}
              </li>
            ))}
          </ul>
          {brief.asks_more ? <p className="lm-brief__more">{BRIEF_COPY.asksMore(brief.asks_more)}</p> : null}
        </div>
      ) : null}
      <div className="lm-brief__part">
        <ToldList told={brief.told} plain />
        <Mistake text={brief.our_mistake} />
      </div>
    </>
  );
}

function ToldList({ told, contractId, canRecord = false, onChanged, plain = false }: {
  told?: Told[] | undefined; contractId?: string; canRecord?: boolean; onChanged?: () => void;
  /** the deal owner's copy: "clause 7.3", never a § sign */
  plain?: boolean;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  if (!told?.length) return null;
  return (
    <>
      <h3 className="lm-brief__h">{BRIEF_COPY.told}</h3>
      <ul className="lm-brief__told">
        {told.map((t, i) => editing === t.position_key && contractId && onChanged ? (
          <li key={t.position_key ?? i}>
            <TellForm contractId={contractId} position={t} onDone={() => { setEditing(null); onChanged(); }}
                      onCancel={() => setEditing(null)} />
          </li>
        ) : (
          <li key={t.position_key ?? i}>
            <span className="lm-brief__toldtext">{plain ? plainClauseSigns(t.text) : withoutSectionRefs(t.text)}</span>
            {t.told_on ? <span className="lm-brief__meta">{BRIEF_COPY.toldOn(formatDate(t.told_on))}</span> : null}
            {canRecord && t.position_key && contractId && onChanged ? (
              <span className="lm-brief__acts">
                <button type="button" className="ws-linkbtn" aria-label={`${BRIEF_COPY.edit}: ${t.text}`}
                        onClick={() => setEditing(t.position_key!)}>{BRIEF_COPY.edit}</button>
                <Withdraw contractId={contractId} position={t} onDone={onChanged} />
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </>
  );
}

function Mistake({ text }: { text?: string | undefined }) {
  return text ? (
    <>
      <h3 className="lm-brief__h">{BRIEF_COPY.mistake}</h3>
      <p className="lm-brief__mistake">{plainClauseSigns(text)}</p>
    </>
  ) : null;
}

function LegalPart({ brief, contractId, onOpen, onChanged }: {
  brief: Brief; contractId: string; onOpen: (rowKey: string) => void; onChanged: () => void;
}) {
  const legal = brief.legal!;
  const [adding, setAdding] = useState<string | null>(null);
  return (
    <>
      <div className="lm-brief__part">
        {legal.beyond.length ? (
          <>
            <h3 className="lm-brief__h">{BRIEF_COPY.startHere(legal.beyond.length)}</h3>
            <ul className="lm-brief__links">
              {legal.beyond.map((b) => (
                <li key={b.row_key}><button type="button" className="ws-linkbtn" onClick={() => onOpen(b.row_key)}>{b.clause}</button></li>
              ))}
            </ul>
          </>
        ) : null}
        <p className="lm-brief__counts">
          {[legal.as_told ? BRIEF_COPY.asTold(legal.as_told) : null,
            legal.not_discussed ? BRIEF_COPY.notDiscussed(legal.not_discussed) : null].filter(Boolean).join(". ")}
        </p>
        {legal.whole_contract.length ? (
          <>
            <h3 className="lm-brief__h">{BRIEF_COPY.wholeContract}</h3>
            <ul className="lm-brief__plain">{legal.whole_contract.map((p) => <li key={p.finding_id}>{p.title}</li>)}</ul>
          </>
        ) : null}
        {legal.comments.length ? <p className="lm-brief__counts">{BRIEF_COPY.comments(legal.comments)}</p> : null}
        <Mistake text={brief.our_mistake} />
      </div>
      <div className="lm-brief__part">
        <ToldList told={brief.told} contractId={contractId} canRecord={legal.can_record} onChanged={onChanged} />
        {legal.note ? (
          <blockquote className="lm-brief__note">
            <span className="lm-brief__meta">{BRIEF_COPY.noteFromSales}</span>
            {legal.note}
          </blockquote>
        ) : null}
        {legal.can_record ? (adding !== null ? (
          <TellForm contractId={contractId} initial={adding} onDone={() => { setAdding(null); onChanged(); }}
                    onCancel={() => setAdding(null)} />
        ) : (
          <button type="button" className="ws-btn ws-btn--sm" onClick={() => setAdding(legal.note?.slice(0, 500) ?? "")}>
            {BRIEF_COPY.add}
          </button>
        )) : null}
      </div>
    </>
  );
}

/** Legal's words of what we told the client: a new position, or its next version. */
function TellForm({ contractId, position, initial = "", onDone, onCancel }: {
  contractId: string; position?: Told; initial?: string; onDone: () => void; onCancel: () => void;
}) {
  const id = useId();
  const [text, setText] = useState(position?.text ?? initial);
  const [toldOn, setToldOn] = useState(position?.told_on ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.tell(contractId, { text: text.trim(), told_on: toldOn || null, ties: position?.ties ?? {},
                                   expected_version: position?.version_number ?? 0 }, position?.position_key);
      toast(BRIEF_COPY.saved);
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="lm-brief__form" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <label htmlFor={`${id}-t`}>{BRIEF_COPY.textLabel}</label>
      <textarea id={`${id}-t`} rows={3} maxLength={500} required value={text} autoFocus
                aria-describedby={error ? `${id}-e` : undefined} onChange={(e) => setText(e.target.value)} />
      <label htmlFor={`${id}-d`}>{BRIEF_COPY.dateLabel}</label>
      <input id={`${id}-d`} type="date" value={toldOn} onChange={(e) => setToldOn(e.target.value)} />
      {error ? <p id={`${id}-e`} className="cx-error" role="alert">{error}</p> : null}
      <div className="lm-brief__formacts">
        <button type="button" className="ws-btn ws-btn--sm" onClick={onCancel}>{BRIEF_COPY.cancel}</button>
        <button type="submit" className="ws-btn ws-btn--sm" disabled={busy || !text.trim()}>
          {busy ? BRIEF_COPY.saving : BRIEF_COPY.save}
        </button>
      </div>
    </form>
  );
}

function Withdraw({ contractId, position, onDone }: { contractId: string; position: Told; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <button type="button" className="ws-linkbtn" disabled={busy} aria-label={`${BRIEF_COPY.withdraw}: ${position.text}`} onClick={() => {
        setBusy(true);
        setError(null);
        api.tell(contractId, { text: position.text, withdrawn: true, expected_version: position.version_number ?? 0 },
                 position.position_key).then(() => { toast(BRIEF_COPY.withdrawn); onDone(); },
          (cause: unknown) => setError(describeError(cause))).finally(() => setBusy(false));
      }}>{BRIEF_COPY.withdraw}</button>
      {error ? <span className="cx-error" role="alert">{error}</span> : null}
    </>
  );
}

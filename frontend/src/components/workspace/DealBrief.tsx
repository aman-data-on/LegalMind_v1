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

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { api, describeError } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { openChange, statusWords, type DealBrief as Brief, type Told } from "@/lib/dealBrief";
import { BRIEF_COPY, NOT_MARKED_COPY, plainClauseSigns, withoutSectionRefs, type StageViewer } from "@/lib/labels";
import type { NegotiationStage } from "@/lib/types";
import { ErrorState } from "@/components/Feedback";
import { toast } from "@/components/Toast";

import { AttentionLine } from "./AnalysisPanel";
import { IconAlertCircle, IconPanelRight, IconX } from "./icons";
import { useMinWidth } from "./WorkspaceLayout";
import { Dialog, hasTypedText, rememberInitial } from "@/components/Dialog";
import { NotMarked } from "./NotMarked";
import { AlreadyAgreed, CheckedAgainst } from "./PriorAndStandards";
import { useFindingsStateOptional } from "./findingsState";
import "./brief.css";

/** When the brief is read (P2 BE-5, W1-4): kept pure so a test can play a page's load
 *  through it. On a first load the key settles while the first read is still out (the
 *  page's change list arrives after the brief is asked); that read already answers it. The
 *  key's first value (null → the change list landed) is part of the first load too. A key
 *  change after an answer, or a reload, reads again. */
export interface BriefReads {
  firstOut: string | null;   // the contract whose first read is out
  shown: string | null;      // the contract the brief shown is of
  // changes skipped while the first read is out: the page's own settle is at most one key
  // change; a second key change or any reload (an answer made meanwhile) reads again
  skipped: { keys: number; seq: number };
  last: { key: string | null; seq: number };
}
export const briefReads = (key: string | null, seq: number): BriefReads =>
  ({ firstOut: null, shown: null, skipped: { keys: 0, seq }, last: { key, seq } });

/** One effect run: read the brief now? (updates `m`) */
export function briefShouldRead(m: BriefReads, contractId: string, key: string | null, seq: number): boolean {
  const arrived = m.last.key === null && key !== null && m.last.seq === seq;
  m.last = { key, seq };
  if (arrived && m.shown === contractId) return false;
  if (m.firstOut === contractId) {
    if (seq !== m.skipped.seq) m.skipped = { keys: 2, seq };
    else m.skipped.keys += 1;
    return false;
  }
  if (m.shown !== contractId) { m.firstOut = contractId; m.skipped = { keys: 0, seq }; }
  return true;
}

/** A read came back: true when a real change was missed meanwhile, so read again. */
export function briefSettled(m: BriefReads, contractId: string): boolean {
  if (m.firstOut !== contractId) return false;
  m.firstOut = null;
  return m.skipped.keys > 1;
}

/** The brief, read again whenever the server's counts or stage change (`refreshKey`). */
export function useDealBrief(contractId: string, refreshKey: string | null) {
  const [state, setState] = useState<{ brief: Brief | null; error: unknown }>({ brief: null, error: null });
  const [seq, setSeq] = useState(0);
  const reload = useCallback(() => setSeq((n) => n + 1), []);
  const reads = useRef<BriefReads | null>(null);
  const latest = useRef(0);
  useEffect(() => {
    const m = (reads.current ??= briefReads(refreshKey, seq));
    if (!briefShouldRead(m, contractId, refreshKey, seq)) return;
    const mine = ++latest.current;
    const settle = () => { if (briefSettled(m, contractId)) setSeq((n) => n + 1); };
    api.dealBrief(contractId).then(
      (brief) => {
        settle();
        if (latest.current === mine) { m.shown = contractId; setState({ brief, error: null }); }
      },
      (error: unknown) => {
        settle();
        if (latest.current === mine) setState((was) => ({ brief: was.brief, error }));
      });
  }, [contractId, refreshKey, seq]);
  return { ...state, reload };
}

export function DealBrief({ contractId, stage, viewer, refreshKey, onOpen, onChanged, onChanges, who }: {
  contractId: string;
  stage: NegotiationStage | null;
  viewer: StageViewer;
  /** null while the page's change list is still loading (W1-4) */
  refreshKey: string | null;
  /** a change named in the brief: the page switches to Changes and opens it */
  onOpen: (rowKey: string) => void;
  /** what we told them changed: the Changes rows re-read their labels */
  onChanged: () => void;
  /** U2 (UI-35): "and N more" opens the Changes tab */
  onChanges?: () => void;
  /** U2 (UI-03): who has it and the note for Legal — the panel's first lines, the header's no more */
  who?: ReactNode;
}) {
  const { brief, error, reload } = useDealBrief(contractId, refreshKey);
  const findings = useFindingsStateOptional();
  // U2: one line until the reader opens the panel beside the contract — the document never moves
  const [expanded, setOpen] = useState(false);
  if (error && !brief) {
    return <section className="lm-brief" aria-label={BRIEF_COPY.title}>
      <ErrorState heading="h2" title={BRIEF_COPY.failed} error={error} onRetry={reload} /></section>;
  }
  if (!brief) {
    // U2 (UI-04): the skeleton is the loaded row's own height — nothing below it moves
    return (
      <section className="lm-brief" aria-label={BRIEF_COPY.title} aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">{BRIEF_COPY.loading}</p>
        <div className="lm-brief__row" aria-hidden="true"><span className="ws-skel ws-skel--line lm-brief__skel" /></div>
      </section>
    );
  }
  // no round of changes: the points' own line (the Summary's, moved here — never twice)
  const points = findings?.state.kind === "ready" ? (
    <AttentionLine progress={findings.state.progress} stage={stage} viewer={viewer} canDecide={false}
                   counts={brief.counts} />) : null;
  const stale = error ? <p className="lm-brief__stale" role="alert">{BRIEF_COPY.stale}{" "}
    <button type="button" className="ws-linkbtn" onClick={reload}>{BRIEF_COPY.retry}</button></p> : null;
  return <BriefView brief={brief} stale={stale} contractId={contractId} points={points} expanded={expanded} who={who}
                    onToggle={() => setOpen(!expanded)} onChanged={() => { reload(); onChanged(); }}
                    onChanges={onChanges && (() => { setOpen(false); onChanges(); })}
                    // the change opens in the Changes tab: the panel closes
                    onOpen={(key) => { setOpen(false); onOpen(key); window.setTimeout(() => openChange(key), 60); }} />;
}

/** The brief as drawn (exported for the static tests): the server's brief, nothing else.
 *  U2 (UI-03/35): ONE line above the tabs — the status, and the not-marked count when there
 *  is one (AM-462 r5 keeps it first) — and the whole brief in a panel beside the contract. */
export function BriefView({ brief, contractId, points, stale = null, expanded, onToggle, onOpen, onChanged, onChanges, who }: {
  brief: Brief; contractId: string; points?: ReactNode; stale?: ReactNode;
  expanded: boolean; onToggle: () => void; onOpen: (rowKey: string) => void; onChanged: () => void;
  onChanges?: (() => void) | undefined; who?: ReactNode;
}) {
  const id = useId();
  const opener = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const legal = brief.legal;
  const status = statusWords(brief);         // the server's code, in words (rule 18)
  const asks = brief.asks ?? [];
  const unmarked = brief.not_marked;
  const more = !!(brief.already_agreed || brief.measured_against);              // batch 8 R1.4/R5
  const opened = useRef(false);
  useEffect(() => {
    if (expanded) { opened.current = true; heading.current?.focus(); }
    else if (opened.current) { opened.current = false; opener.current?.focus(); }
  }, [expanded]);
  // U2 r4: a phone gets a real modal sheet (focus trapped, the page inert); a wide screen
  // a panel docked beside the panes, which make room for it — nothing is covered
  const sheet = useMinWidth(641) === false;
  // docked: it starts where the header ends — measured on the click that opens it (the
  // header never moves while it is open)
  const [top, setTop] = useState<number | null>(null);
  const toggle = () => {
    const header = expanded ? null : document.querySelector(".ws-record");
    if (header) setTop(Math.round(header.getBoundingClientRect().bottom));
    onToggle();
  };
  if (!status && !points && !asks.length && !brief.told?.length && !brief.our_mistake && !legal && !unmarked
      && !more && !who) return null;
  const hasMore = !!(legal || asks.length || brief.told?.length || brief.our_mistake || unmarked || more || who);
  return (
    <section className="lm-brief" aria-labelledby={`${id}-h`} data-testid="deal-brief"
             data-open={expanded || undefined}>
      <h2 id={`${id}-h`} className="ws-visually-hidden">{BRIEF_COPY.title}</h2>
      <div className="lm-brief__row">
        {status ? <p className="lm-brief__status" data-testid="brief-status">{BRIEF_COPY.withoutStage(status)}</p>
          : points ?? null}
        {unmarked ? (
          <span className="lm-brief__flag" id={`${id}-unmarked`}>
            <IconAlertCircle size={16} />
            {(unmarked.highlights_read ? NOT_MARKED_COPY.title : NOT_MARKED_COPY.titleOldFile)(unmarked.count, unmarked.total)}
          </span>
        ) : null}
        {hasMore ? (
          <button ref={opener} type="button" className="ws-btn ws-btn--sm lm-brief__open" aria-expanded={expanded}
                  aria-controls={`${id}-panel`} onClick={toggle}
                  aria-describedby={unmarked ? `${id}-unmarked` : undefined}>
            <IconPanelRight size={16} /><span className="lm-brief__openlong">{BRIEF_COPY.open}</span>
            <span className="lm-brief__openshort" aria-hidden="true">{BRIEF_COPY.openShort}</span>
            {/* a phone: the not-marked count rides on the button (the line itself is in the sheet) */}
            {unmarked ? <span className="ws-filter__n lm-brief__count" aria-hidden="true">{unmarked.count}</span> : null}
          </button>
        ) : null}
      </div>
      {stale}
      {expanded ? (() => {
        const content = (
          <>
            <header className="lm-briefpanel__head">
              <h2 id={`${id}-ph`} ref={heading} tabIndex={-1}>{BRIEF_COPY.panelTitle}</h2>
              <button type="button" className="ws-btn ws-btn--sm lm-briefpanel__close" aria-label={BRIEF_COPY.close}
                      onClick={onToggle}><IconX size={16} /></button>
            </header>
            <div className="lm-brief__body lm-briefpanel__body">
              {status ? <p className="lm-briefpanel__status">{status}</p> : null}
              {who ? <div className="lm-brief__first">{who}</div> : null}
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
              {brief.already_agreed || brief.measured_against ? (
                <div className="lm-brief__first">
                  {brief.already_agreed ? <AlreadyAgreed agreed={brief.already_agreed} /> : null}
                  <CheckedAgainst brief={brief} legal={!!legal} />
                </div>
              ) : null}
              {legal ? <LegalPart brief={brief} contractId={contractId} onOpen={onOpen} onChanged={onChanged} />
                : <SalesPart brief={brief} onChanges={onChanges} />}
            </div>
          </>
        );
        return sheet ? (
          <Dialog onClose={onToggle} titleId={`${id}-ph`} overlayClassName="lm-briefsheet" keepTypedTextOnEscape
                  returnFocus={() => opener.current}>{content}</Dialog>
        ) : (
          // non-modal and docked (it covers nothing); Esc here closes it — never from a
          // field holding text the reader typed (Legal's "what we told them" draft)
          <aside className="lm-briefpanel" id={`${id}-panel`} aria-labelledby={`${id}-ph`}
                 style={top !== null ? { top } : undefined}
                 onFocusCapture={(event) => rememberInitial(event.target)}
                 onKeyDown={(event) => {
                   if (event.key !== "Escape" || hasTypedText(event.target)) return;
                   event.stopPropagation();
                   onToggle();
                 }}>{content}</aside>
        );
      })() : null}
    </section>
  );
}

function SalesPart({ brief, onChanges }: { brief: Brief; onChanges?: (() => void) | undefined }) {
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
          {brief.asks_more ? <p className="lm-brief__more">{onChanges ? (
            <button type="button" className="ws-linkbtn" onClick={onChanges}>{BRIEF_COPY.asksMoreLink(brief.asks_more)}</button>
          ) : BRIEF_COPY.asksMore(brief.asks_more)}</p> : null}
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
  // r5: the form closes back onto its own button — focus stays in the panel, so Esc still works
  const addButton = useRef<HTMLButtonElement>(null);
  const closeForm = () => { setAdding(null); window.requestAnimationFrame(() => addButton.current?.focus()); };
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
        {/* r4: the owner's note is the panel's first block ("Note to Legal from …") */}
        {legal.can_record ? (adding !== null ? (
          <TellForm contractId={contractId} initial={adding} onDone={() => { closeForm(); onChanged(); }}
                    onCancel={closeForm} />
        ) : (
          <button ref={addButton} type="button" className="ws-btn ws-btn--sm" onClick={() => setAdding(legal.note?.slice(0, 500) ?? "")}>
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

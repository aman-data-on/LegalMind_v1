"use client";

/**
 * The Changes tab — the client's changes to our contract, answered one by one
 * (CLM Phase 1, AB-150: R3, R4, R5, R6; UX §3.4/§3.7).
 *
 *   list (grouped by clause, filters)  ·  the changed passages, Word-style marks  ·  answer card
 *
 * Everything that decides is the server's: the route, the review's status word, who
 * may answer (`can_answer`) and who holds the right (`can_decide`). A control the
 * reader may not use is ABSENT, never disabled (52.4); a position the reader may not
 * see never arrives, so it is never drawn. Marks are verdict-neutral (`AM-255`): added
 * words underlined, removed words struck, each with "client added / removed" for a
 * screen reader — never colour alone. A holder decides IN PLACE through the existing
 * `DecisionControl` (`AM-250` r2) — or, on a change no standard measures, records
 * "accept theirs" as their own answer with a reason (`AM-281`, never a Legal Decision);
 * everyone else may keep our position or ask.
 */

import { finalLine } from "@/lib/package";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { useStep } from "@/lib/nextStep";
import { saveBlob } from "@/lib/pdfDownload";
import { EmptyState, ErrorState, LoadingState, NoticeState } from "@/components/Feedback";
import { SegmentedFilter } from "@/components/SegmentedFilter";
import { PreviewPanel } from "@/components/PreviewPanel";
import { StatusChip, chipStatus } from "@/components/StatusChip";
import { CHANGES_COPY, FEEDBACK_COPY, RETURNED_COPY } from "@/lib/labels";
import { PointStatusIcon } from "./PointStatus";
import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { isOurs, sectionRef } from "@/lib/documentTypes";
import { displayCaps, displayTitle } from "@/lib/templates";
import {
  ACCEPTABLE_EFFECTS, ACTION_LABEL, ANSWER_LABEL, EFFECT_LABEL, KIND_LABEL, ROUTE_REASON, acceptable, actionsFor,
  clauseName, effectLabel, effectSentence, type Measured,
  type AcceptableEffect,
  answersAsLegal, explanation, formattingOnly, changeBucket, historyLine, matches, readerFavour, readerStatus, readerWord, replyBlockers,
  firstWords, oursLabel, rowMeta, topicOf, whoLine, where,
  type Answer, type ChangeList, type ClientChange, type EffectForUs, type Filter, type ManualRow, type ReplyGate,
} from "@/lib/changes";
import type { DocumentVersion, Evaluation, Finding } from "@/lib/types";

import "./changes.css";
import { DiffText } from "./ChangeComposer";
import { AnswerCard, RowStatus } from "./AnswerCard";
import { ChangesBanners, EarlierAnswers } from "./ChangesBanners";
import { WordComments } from "./WordComments";
import { EscalateControl } from "./EscalateControl";
import { USER_STATUS_LABELS, readerWord as pointWord, requirementTitle } from "./findingLanguage";
import {
  IconAlertCircle, IconArrowLeft, IconBetter, IconCheck, IconChevronRight, IconClock, IconDownload, IconFile, IconFileMinus, IconLock, IconSame, IconWorse, IconFallback,
} from "./icons";
import { OfferLine } from "./OfferPlaybook";
import { FromOurStandard, LetteredPoints, NotesForLegal, ReviewTableButton } from "./LawyerView";
import { REOPEN_COPY, SALES_LINE } from "@/lib/labels";
import { formatDate } from "@/lib/dates";
import { onOpenChange } from "@/lib/dealBrief";
export { AnswerCard } from "./AnswerCard";

export const COLLEAGUE = "Changed by a colleague — reload to see their answer.";

/** A refused answer, in words: a 409 is a colleague's newer answer (R5), never retried. */
export function answerError(cause: unknown): { conflict: boolean; message: string } {
  const conflict = cause instanceof ApiError && cause.status === 409;
  return { conflict, message: conflict ? COLLEAGUE : describeError(cause) };
}

type Load =
  | { kind: "loading" }
  | { kind: "ready"; list: ChangeList }
  | { kind: "error"; error: unknown };

/** The pair the tab shows: the client's latest version against ours before it — or,
 *  once our reply is the latest version, the round that reply answered. */
export function clientVersion(versions: DocumentVersion[]): number | undefined {
  const latest = versions[0];
  return latest?.version_role === "COMPANY_DRAFT" && versions.length > 2
    ? latest.version_number - 1 : undefined;
}

/** One version only: a tab exactly when the server lists it — not ours (`is_ours`: an
 *  undeclared version is no one's, so its paper is listed and asked about), or made
 *  from our blank template (`AM-290`, `AM-302`). */
export function changesEnabled(versions: DocumentVersion[]): boolean {
  const only = versions.length === 1 ? versions[0] : undefined;
  // a signed copy alone has nothing to answer
  return versions.length > 1 || (!!only && only.version_role !== "FINAL_SIGNED"
    && (!isOurs(only) || !!only.made_from_template));
}

/** One fetch for the tab label and the pane, owned by the workspace page. */
export function useClientChanges(contractId: string, versions: DocumentVersion[]) {
  const toVersion = clientVersion(versions);
  // one version only: a tab exactly when it is the client's paper (`AM-290`, client
  // paper first — the server's `is_ours`, read the other way round)
  const enabled = changesEnabled(versions);
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [seq, setSeq] = useState(0);
  const reload = useCallback(() => setSeq((n) => n + 1), []);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api.clientChanges(contractId, toVersion).then(
      (list) => { if (!cancelled) setState({ kind: "ready", list }); },
      (error: unknown) => { if (!cancelled) setState({ kind: "error", error }); });
    return () => { cancelled = true; };
  }, [enabled, contractId, toVersion, seq]);
  return { state, setState, reload, enabled };
}

type FilterDef = { id: Filter; label: string; empty: string };
/** What each change does for us (`AM-299`) — a second, separate set of filters. */
export const EFFECT_FILTERS: FilterDef[] = [
  // 6d (UX §4): Good / Neutral / Bad or Legal checks — the review table's words
  { id: "POSITIVE", label: "Good for us", empty: "No change here is good for us." },
  { id: "NEUTRAL", label: "Neutral", empty: "No change here leaves us where we were." },
  { id: "FALLBACK", label: "Fallback", empty: "No change here is a fallback from our opening position." },
  { id: "NEGATIVE", label: "Legal checks", empty: "No change here goes to Legal." },
];

const EFFECT_ICON: Record<EffectForUs, typeof IconBetter> = { POSITIVE: IconBetter, NEUTRAL: IconSame, FALLBACK: IconFallback, NEGATIVE: IconWorse };
/** a NEGATIVE row not measured worse never wears the "worse" arrow */
const MEASURED_ICON: Record<Measured, typeof IconBetter> = { WORSE: IconWorse, NOT_MEASURED: IconAlertCircle, UNCLEAR: IconAlertCircle, ABSENT: IconFileMinus, REVIEW: IconAlertCircle };

/** "For us": an icon AND the words — the shape tells the three apart without colour, the
 *  words say it (WCAG 1.4.1). Its own slot, never merged with the review's word. */
export function ForUs({ effect, measured, size = 13 }: { effect: EffectForUs; measured?: Measured | undefined; size?: number }) {
  const Icon = effect === "NEGATIVE" && measured ? MEASURED_ICON[measured] : EFFECT_ICON[effect];
  return <span className="cx-forus" data-effect={effect} data-measured={effect === "NEGATIVE" ? measured : undefined}>
    <Icon size={size} />{effectLabel(effect, measured)}</span>;
}
const ANSWERED: FilterDef = { id: "answered", label: "Answered", empty: "No change has been answered yet." };
const ALL: FilterDef = { id: "all", label: "All", empty: "The client changed nothing." };
/** Counted by who answers (per person): the deal owner's work and what waits on Legal,
 *  or — for Legal — Legal's work and what the deal owner answers. */
export function filtersFor(list: Pick<ChangeList, "can_decide">): FilterDef[] {
  return list.can_decide ? [
    { id: "mine", label: "Yours to answer", empty: "Nothing here is waiting on you." },
    { id: "owner", label: "Deal owner's", empty: "Nothing is waiting on the deal owner." },
    ANSWERED, ALL,
  ] : [
    { id: "mine", label: "Yours to answer", empty: "Nothing here is waiting on you." },
    { id: "holder", label: "With Legal", empty: "No change is waiting for Legal." },
    ANSWERED, ALL,
  ];
}

export function ChangesPane({
  contractId, versions, changes, onVersionCreated, packageBar, packageLine, place,
}: {
  /** `AM-310`: where an agreed change is written — Annexure A, or the amendment */
  place?: string | undefined;
  /** `AM-307` U2: what an answered change becomes in the final contract */
  packageLine?: ((change: ClientChange) => string | null) | undefined;
  /** `AM-307`: the final contract's bar (`PackageBar`), given a way to open a change */
  packageBar?: ((onPick: (rowKey: string) => void) => React.ReactNode) | undefined;
  contractId: string;
  versions: DocumentVersion[];
  changes: ReturnType<typeof useClientChanges>;
  onVersionCreated: () => void;
}) {
  const { state, setState, reload } = changes;
  // The default view is the reader's own work when there is any (DESIGN.md: default
  // views bias toward the task); "All" otherwise. A pressed filter wins from then on.
  const [picked, setPicked] = useState<Filter | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [said, setSaid] = useState("");
  // phone: the list, or one change's detail screen (wider screens show both)
  const [detail, setDetail] = useState(false);
  const [bulk, setBulk] = useState<ClientChange[] | null>(null);
  const [accepting, setAccepting] = useState<AcceptableEffect | null>(null);

  const list = state.kind === "ready" ? state.list : null;
  const FILTERS = useMemo(() => [...filtersFor(list ?? { can_decide: false }), ...EFFECT_FILTERS], [list]);
  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f.id,
    list ? list.changes.filter((c) => matches(c, f.id, list)).length : 0])) as Record<Filter, number>,
  [list, FILTERS]);
  const filter: Filter = picked ?? (counts.mine ? "mine" : "all");
  const shown = useMemo(
    () => (list ? list.changes.filter((c) => matches(c, filter, list)) : []),
    [list, filter]);
  const current = shown.find((c) => c.row_key === selected) ?? shown[0] ?? null;

  // j / k walk the shown changes (the workspace's own keys for its findings)
  const currentKey = current?.row_key ?? null;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "j" && event.key !== "k") return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const t = event.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      const rows = shown;
      if (rows.length === 0) return;
      const at = Math.max(0, rows.findIndex((c) => c.row_key === currentKey));
      const next = rows[Math.min(rows.length - 1, Math.max(0, at + (event.key === "j" ? 1 : -1)))]!;
      setSelected(next.row_key);
      // after the render that opens a collapsed group around it
      window.requestAnimationFrame(() => document.getElementById(`cx-row-${next.row_key}`)?.focus());
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shown, currentKey]);

  useEffect(() => {
    if (current) document.getElementById(`cx-passage-${current.row_key}`)
      ?.scrollIntoView?.({ block: "nearest" });
  }, [current]);

  // batch 3+4: the deal brief names a change — open it here
  useEffect(() => onOpenChange((key) => {
    setPicked("all");
    setSelected(key);
    setDetail(true);
    window.requestAnimationFrame(() => document.getElementById(`cx-row-${key}`)?.focus());
  }), []);

  // the header's "Answer changes" (`nextStep`): the first change left for this reader
  useStep("answerChanges", useCallback(() => {
    const first = list?.changes.find((c) => matches(c, "mine", list));
    if (!first) return;
    setPicked("mine");
    setSelected(first.row_key);
    setDetail(true);
    window.requestAnimationFrame(() => document.getElementById(`cx-row-${first.row_key}`)?.focus());
  }, [list]));

  if (state.kind === "loading") {
    return <LoadingState label="Loading the client’s changes…" rows={5} />;
  }
  if (state.kind === "error") {
    // P1 (owner, 2026-11-09): a version nobody declared is no one's — ask, never guess
    const undeclared = state.error instanceof ApiError && state.error.code === "VERSION_ROLE_UNDECLARED";
    return undeclared ? (
      // round 2: a question for the reader, never drawn as a failure (no red, no reference)
      <div className="lm-page">
        <NoticeState title="Whose paper is this version?"
                     body="Say whose wording each version is, so the changes are read the right way round.">
          <DeclareRoles versions={versions.filter((v) => !v.version_role && !v.source)} onDone={reload} />
        </NoticeState>
      </div>
    ) : <ErrorState title="The changes could not be listed" error={state.error} onRetry={reload} />;
  }
  const data = state.list;
  const focusSoon = (id: string) => window.requestAnimationFrame(() => document.getElementById(id)?.focus());
  /** A recorded answer: the row is updated from the server's reply, and focus moves on to
   *  the next change still open in this view — or stays on the answer when it waits for
   *  a second person, or when nothing is left. Said aloud either way. */
  const replace = (row: Answered) => {
    const next = merged([row]);
    const done = next.changes.find((c) => c.row_key === row.row_key)!;
    const recorded = `Recorded: ${whoLine(done, next)}.`;
    const at = shown.findIndex((c) => c.row_key === row.row_key);
    const ahead = row.waiting_for_approval ? undefined
      : [...shown.slice(at + 1), ...shown.slice(0, Math.max(0, at))].find((c) => c.answer === null);
    if (ahead) {
      setSelected(ahead.row_key);
      setSaid(`${recorded} Next: ${where(ahead)}.`);
      focusSoon(`cx-row-${ahead.row_key}`);
    } else {
      setSelected(row.row_key);
      if (!matches(done, filter, next)) setPicked("all");
      setSaid(recorded);
      focusSoon(`cx-given-${row.row_key}`);
    }
  };
  /** The rows the server answered, merged into the list. */
  const merged = (rows: Answered[]) => {
    const by = new Map(rows.map((r) => [r.row_key, r]));
    const next = { ...data, changes: data.changes.map((c) => {
      const r = by.get(c.row_key);
      return r ? { ...c, answer: r.answer, history: r.history, waiting_for_approval: !!r.waiting_for_approval } : c;
    }) };
    setState({ kind: "ready", list: next });
    return next;
  };
  const pick = (key: string) => {
    if (!shown.some((c) => c.row_key === key)) setPicked("all");
    setSelected(key);
    setDetail(true);
    focusSoon(`cx-row-${key}`);
  };
  /** A row chosen in the list: on a phone this opens its detail screen. */
  const open = (key: string) => {
    setSelected(key);
    setDetail(true);
    // the phone's detail screen starts at its top, focus on "Back to the list"
    window.requestAnimationFrame(() => {
      const backButton = document.querySelector<HTMLElement>(".cx-back");
      if (backButton?.offsetParent) {
        backButton.closest(".cx")?.scrollTo?.({ top: 0 });
        backButton.focus();
      }
    });
  };
  const back = () => {
    setDetail(false);
    if (current) focusSoon(`cx-row-${current.row_key}`);
  };
  const formatting = data.can_answer && !data.tracked_base ? data.changes.filter((c) => formattingOnly(c) && c.answer === null) : [];
  const allUntracked = data.summary.untracked > 0 && data.summary.untracked === data.summary.total;
  // `can_answer` is false once our reply is prepared — the round is closed
  const together = Object.fromEntries(ACCEPTABLE_EFFECTS.map((e) => [e, acceptable(data.changes, e, data)])) as Record<AcceptableEffect, ClientChange[]>;
  const emptyText = (FILTERS.find((f) => f.id === filter) ?? ALL).empty;
  const showAll = filter !== "all" && data.changes.length ? (
    <button type="button" className="ws-escalate__link" onClick={() => setPicked("all")}>
      Show all {data.changes.length} changes
    </button>
  ) : null;

  return (
    <div className="cx" data-testid="changes-pane" data-view={detail ? "detail" : "list"}>
      <a className="cx-skip" href="#cx-list">Skip to the list of changes</a>
      <div className="cx-bar">
        {/* round 2: the one filter control — zero counts hidden, never clipped */}
        {FILTERS.filter((f) => !EFFECT_FILTERS.includes(f) && counts[f.id]).some((f) => counts[f.id] !== data.changes.length) ? (
        <SegmentedFilter label="Show changes" value={filter} onChange={setPicked}
                         segments={FILTERS.filter((f) => !EFFECT_FILTERS.includes(f)).map((f) => (
                           { id: f.id, label: f.label, text: f.label, count: counts[f.id], always: f.id === "all" }))} />
        ) : null}
        <SegmentedFilter label="For us" value={filter} onChange={setPicked}
                         segments={EFFECT_FILTERS.map((f) => ({ id: f.id, label: <ForUs effect={f.id as EffectForUs} />,
                           text: effectLabel(f.id as EffectForUs), count: counts[f.id] }))} />
        {/* r4: what the changes are measured from, on the bar's own row (one line less) */}
        {data.from ? <span className="cx-bar__from">{CHANGES_COPY.comparedWith(data.from.version_number)}</span> : null}
        <span className="cx-bar__table"><ReviewTableButton contractId={contractId} /></span>
        <ReplyBar contractId={contractId} versions={versions} list={data}
                  onVersionCreated={onVersionCreated} onPick={pick} />
      </div>
      {data.can_decide ? <NotesForLegal list={data} onPick={pick} rowFor={(n) => (data.changes.find((c) => c.clause.number === n)
        ?? data.changes.find((c) => c.clause.number?.startsWith(`${n}.`)))?.row_key ?? null} /> : null}
      {/* R3: the deal owner's one line — who has the changes now, never Legal's view */}
      {/* batch 3+4: the deal owner's one status line is the deal brief's, above the tabs */}
      <p className="ws-visually-hidden" role="status" aria-live="polite">{said}</p>
      {packageBar?.(pick)}
      <ChangesBanners data={data} allUntracked={allUntracked} />
      {ACCEPTABLE_EFFECTS.some((e) => together[e].length) ? (
        <div className="cx-together" role="group" aria-label="Accept without Legal">
          {ACCEPTABLE_EFFECTS.map((e) => together[e].length ? (
            <button key={e} type="button" className="ws-btn ws-btn--sm" onClick={() => setAccepting(e)}>
              <ForUs effect={e} /> Accept all {together[e].length}
            </button>
          ) : null)}
          <span className="cx-together__note">Only changes worse for us go to Legal.</span>
        </div>
      ) : null}
      {/* round 2: nothing changed — one message where the three panes would be; the bar
          above (reply, final contract) and any banner stay (PLAIN-LANGUAGE §2.6) */}
      {data.changes.length === 0 && !data.template ? (
        <EmptyState heading="h2" icon={<IconCheck size={24} />} title="No changes from the client"
                    body={data.tracked_base ? RETURNED_COPY.noChanges : "This version matches what we sent."} />
      ) : <div className="cx-grid">
        <nav className="cx-list" id="cx-list" tabIndex={-1} aria-label="Client changes">
          {shown.length ? (
            <ChangeIndex rows={shown} current={current} onPick={open} allUntracked={allUntracked} reader={data} place={place}
                         packageLine={packageLine}
                         formatting={formatting} onKeepAllFormatting={() => setBulk(formatting)} />
          ) : <div className="cx-empty"><p>{emptyText}</p>{showAll}</div>}
        </nav>
        <section className="cx-doc" aria-label={data.from
          ? `Version ${data.to.version_number} against version ${data.from.version_number}`
          : `Version ${data.to.version_number}, ${data.tracked_base ? "the client's tracked changes" : "the client's paper"}`}>
          {/* the outline's level between the page's h1 and each passage's h3 (UI review) */}
          <h2 className="ws-visually-hidden">The client&rsquo;s changes in the document</h2>
          <p className="cx-legend">
            {data.from || data.template || data.tracked_base ? (
              <>{data.tracked_base ? <>{RETURNED_COPY.legend}{" "}</> : data.template ? <>Our template (version {data.template.version}) against this copy
                (version {data.to.version_number}).{" "}</> : null}<ins>Underlined</ins>: the client added. <del>Struck</del>: the client
                removed.</>
            ) : (
              // PLAIN-LANGUAGE §2.4's own replacement wording
              <>This is the client&rsquo;s own contract. Each item below is a clause that differs from our standard.</>
            )}{" "}
            {/* the j/k keys are Legal's working tool; a Sales reader never sees the hint */}
            {data.can_decide ? <span className="cx-legend__keys"><kbd>j</kbd> <kbd>k</kbd> next and previous change</span> : null}
          </p>
          {shown.map((c) => (
            <article key={c.row_key} id={`cx-passage-${c.row_key}`} className="cx-passage"
                     aria-current={c.row_key === current?.row_key || undefined}
                     onClick={() => setSelected(c.row_key)}>
              <h3>{where(c)}{formattingOnly(c) ? <span className="cx-tag">Formatting only</span>
                : c.kind !== "MODIFIED" && !wholeClause(c) ? <span className="cx-tag">{KIND_LABEL[c.kind]}</span> : null}</h3>
              <Marked change={c} list={data} />
              <WordComments comments={[...(c.after?.comments ?? []), ...(c.before?.comments ?? [])]} />
            </article>
          ))}
        </section>
        <aside className="cx-card" aria-label="Answer">
          <h2 className="ws-visually-hidden">Answer</h2>
          <button type="button" className="ws-btn ws-btn--sm cx-back" onClick={back}>
            <IconArrowLeft size={14} /> Back to the list
          </button>
          {current ? (
            <AnswerCard key={current.row_key} change={current} list={data} contractId={contractId}
                        onAnswered={replace} onReload={reload} inPackage={packageLine?.(current)}
                        amendment={!!place} />
          ) : <p className="ws-pane__note">No change is selected.</p>}
        </aside>
        <div id="cx-editor-slot" className="cx-editor-slot" />
      </div>}
      {accepting ? (
        <AcceptTogether effect={accepting} rows={together[accepting]} list={data} contractId={contractId}
                        onClose={() => setAccepting(null)} onReload={reload}
                        onDone={(rows) => {
                          merged(rows);
                          setAccepting(null);
                          setSaid(`Accepted ${rows.length} ${rows.length === 1 ? "change" : "changes"}: ${EFFECT_LABEL[accepting].toLowerCase()}.`);
                        }} />
      ) : null}
      {bulk ? (
        <KeepAllFormatting rows={bulk} list={data} contractId={contractId} onClose={() => setBulk(null)}
                           onReload={reload}
                           onDone={(rows) => {
                             merged(rows);
                             setBulk(null);
                             setSaid(`Kept ours on ${rows.length} formatting ${rows.length === 1 ? "change" : "changes"}.`);
                           }} />
      ) : null}
    </div>
  );
}

type Answered = Pick<ClientChange, "row_key" | "answer" | "history" | "waiting_for_approval">;

/** "Keep ours on all N formatting changes": one confirmation, one request — all or none
 *  (the server refuses the whole set if a colleague answered one first). */
function KeepAllFormatting({ rows, list, contractId, onClose, onDone, onReload }: {
  rows: ClientChange[]; list: ChangeList; contractId: string;
  onClose: () => void; onDone: (rows: Answered[]) => void; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ conflict: boolean; message: string } | null>(null);
  const n = rows.length;
  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const got = await api.keepOursOnFormatting(contractId, list.to.version_number, rows.map((c) => c.row_key));
      onDone(got.rows);
    } catch (cause) {
      const e = answerError(cause);
      setError(e.conflict ? { conflict: true, message: "A colleague answered one of these first, so nothing was recorded. Reload to see their answer." } : e);
      setBusy(false);
    }
  }
  return (
    <Dialog onClose={onClose} titleId="cx-bulk-title">
      <h2 id="cx-bulk-title">Keep our wording on {n} formatting {n === 1 ? "change" : "changes"}?</h2>
      <p className="ws-pane__note">
        In each, only capitals or punctuation changed. Our reply restores our version of each as a tracked
        change. All {n} are recorded together, or none is.
      </p>
      <ul className="cx-manual">
        {rows.map((c) => <li key={c.row_key}><strong>{rowLabel(c, "")}</strong></li>)}
      </ul>
      {error ? (
        <p className="cx-error" role="alert">
          {error.message}{" "}
          {error.conflict ? <button type="button" className="ws-escalate__link" onClick={onReload}>Reload</button> : null}
        </p>
      ) : null}
      <div className="cx-dialog__foot">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--primary" disabled={busy || error?.conflict} onClick={() => void confirm()}>
          {busy ? "Recording…" : `Keep our wording on all ${n}`}
        </button>
      </div>
    </Dialog>
  );
}

/** "Accept all N better for us" / "… with no change for us" (`AM-299` r2): one
 *  confirmation, one request, all or none — each recorded with who and, as its reason,
 *  the effect. Legal can still reopen any of them. */
export function AcceptTogether({ effect, rows, list, contractId, onClose, onDone, onReload }: {
  effect: AcceptableEffect; rows: ClientChange[]; list: ChangeList; contractId: string;
  onClose: () => void; onDone: (rows: Answered[]) => void; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ conflict: boolean; message: string } | null>(null);
  const n = rows.length;
  const what = { POSITIVE: "better for us", NEUTRAL: "with no change for us", FALLBACK: "as fallbacks" }[effect];
  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const got = await api.acceptByEffect(contractId, list.to.version_number, effect, rows.map((c) => c.row_key));
      onDone(got.rows);
    } catch (cause) {
      const e = answerError(cause);
      setError(e.conflict ? { conflict: true, message: "A colleague answered one of these first, so nothing was recorded. Reload to see their answer." } : e);
      setBusy(false);
    }
  }
  return (
    <Dialog onClose={onClose} titleId="cx-accept-title">
      <h2 id="cx-accept-title">Accept {n} {n === 1 ? "change" : "changes"} {what}?</h2>
      <p className="ws-pane__note">
        Each is accepted as the client wrote it, recorded with your name and &ldquo;{EFFECT_LABEL[effect]}&rdquo; as
        the reason. Legal can still reopen any of them. All {n} are recorded together, or none is.
      </p>
      <ul className="cx-manual">
        {rows.map((c) => <li key={c.row_key}><strong>{rowLabel(c, "")}</strong></li>)}
      </ul>
      {error ? (
        <p className="cx-error" role="alert">
          {error.message}{" "}
          {error.conflict ? <button type="button" className="ws-escalate__link" onClick={onReload}>Reload</button> : null}
        </p>
      ) : null}
      <div className="cx-dialog__foot">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--primary" disabled={busy || error?.conflict} onClick={() => void confirm()}>
          {busy ? "Recording…" : `Accept all ${n}`}
        </button>
      </div>
    </Dialog>
  );
}

/** A row's clause group: its top-level number; a point on the client's paper no clause
 *  was confirmed for (MISSING included) is not placed, never "opening text". */
export function groupHead(c: ClientChange): string {
  return sectionRef(c.clause.number?.split(".")[0])
    ?? (c.kind === "THEIRS" && !c.after ? "Not placed in a clause" : "Opening text");
}

export function ChangeIndex({ rows, current, onPick, allUntracked, reader, formatting, onKeepAllFormatting, place, packageLine }: {
  rows: ClientChange[]; current: ClientChange | null; onPick: (key: string) => void;
  allUntracked: boolean; reader: ChangeList; place?: string | undefined;
  /** B5: the same line the answer panel says — the dry run's, read again after every
   *  answer — so a row never says "Our wording stays" beside "Replaced with theirs" */
  packageLine?: ((change: ClientChange) => string | null) | undefined;
  /** the open formatting-only rows this reader may answer — the bulk action's set */
  formatting: ClientChange[]; onKeepAllFormatting: () => void;
}) {
  const FMT = "Formatting only";
  // the formatting-only rows are one group, first and closed (a heading's capitals or
  // colon, 19 of them on a returned MSA, are not 19 things to read)
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set([`${FMT}-fmt`]));
  const groups: { key: string; head: string; title: string | null; name?: string | null; unit?: string | null; rows: ClientChange[]; fmt?: boolean }[] = [];
  const fmtRows = rows.filter(formattingOnly);
  if (fmtRows.length) groups.push({ key: `${FMT}-fmt`, head: FMT, title: null, rows: fmtRows, fmt: true });
  // grouped by top-level clause: "9", "9.1", "9.2" sit under 9 (the document's own number)
  // R3: a deal owner's list is grouped by plain topic, in the order topics first appear;
  // Legal's stays by clause number
  const byTopic = !reader.can_decide;
  const order = byTopic ? [...new Set(rows.map((c) => topicOf(c) ?? SALES_LINE.otherTopic))] : [];
  const ordered = byTopic ? [...rows].sort((a, b) =>
    order.indexOf(topicOf(a) ?? SALES_LINE.otherTopic) - order.indexOf(topicOf(b) ?? SALES_LINE.otherTopic)) : rows;
  for (const c of ordered) {
    if (formattingOnly(c)) continue;
    const top = c.clause.number?.split(".")[0];
    const head = byTopic ? topicOf(c) ?? SALES_LINE.otherTopic : groupHead(c);
    // a number the paper uses twice is two clauses: each row sits in its own parent
    // unit (the server's `group`), told apart by that unit's own words
    const unit = byTopic ? null : c.clause.group?.key ?? null;
    const last = groups.at(-1);
    if (last?.head !== head || (last?.unit ?? null) !== unit || last?.fmt) {
      groups.push({ key: `${head}-${groups.length}`, head, title: null, name: byTopic ? null : c.clause.group?.name ?? null, unit, rows: [] });
    }
    const g = groups.at(-1)!;
    g.rows.push(c);
    // UI-21: every numbered group is named — its top clause's own heading, in sentence case
    if (!byTopic && !g.title && (c.clause.top_heading || (c.clause.number === top && c.clause.heading))) {
      g.title = displayTitle(c.clause.top_heading || c.clause.heading!);
    }
  }
  const toggle = (key: string) => setClosed((was) => {
    const next = new Set(was);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  return (
    <ol className="cx-index">
      {groups.map((g, gi) => {
        const open = g.rows.filter((c) => c.answer === null).length;
        const expanded = !closed.has(g.key) || g.rows.some((c) => c.row_key === current?.row_key);
        return (
          <li key={g.key} data-fmt={g.fmt || undefined}>
            <button type="button" className="cx-index__head" aria-expanded={expanded}
                    aria-controls={`cx-group-${gi}`} onClick={() => toggle(g.key)}
                    // UI-21: one name, never "13 open of 3" run together from the visible parts
                    aria-label={`${/^\d/.test(g.head) ? `Clause ${g.head}` : g.head}${g.name ?? g.title ? `, ${g.name ?? g.title}` : ""}: ${
                      open ? `${open} of ${g.rows.length} open` : "done"}`}>
              <span className="cx-index__chev"><IconChevronRight size={12} /></span>
              <span className="cx-index__title">
                {g.head}{g.name ? <span> — {g.name}</span> : g.title ? <span> {g.title}</span> : null}
              </span>
              <span className="cx-index__n">
                {open ? `${open} open` : "done"}<span className="ws-visually-hidden"> of {g.rows.length}</span>
              </span>
            </button>
            {g.fmt && formatting.length > 1 ? (
              <div className="cx-index__bulk">
                <button type="button" className="ws-btn ws-btn--sm" onClick={onKeepAllFormatting}>
                  Keep our wording on all {formatting.length}
                </button>
              </div>
            ) : null}
            {expanded ? (
              <ul id={`cx-group-${gi}`}>
                {g.rows.map((c) => (
                  <li key={c.row_key}>
                    <button type="button" id={`cx-row-${c.row_key}`} className="cx-row"
                            data-answered={c.answer ? "" : undefined}
                            aria-current={c.row_key === current?.row_key || undefined}
                            onClick={() => onPick(c.row_key)}>
                      {/* the group already says the clause: a row that would only repeat
                          it, or say a bare number, says its own first words */}
                      <span className="cx-row__where">{displayCaps(rowLabel(c, groupLabel(g)))}</span>
                      {/* batch 3+4: ONE status label for this reader, the kind of change as
                          its small meta; the review's word and the effect are the card's */}
                      <span className="cx-row__meta">
                        <RowStatus change={c} list={reader} />
                        <span className="cx-row__kind">{rowMeta(c, allUntracked)}</span>
                      </span>
                      {(() => {
                        const line = packageLine ? packageLine(c) : finalLine(c, place);
                        return line ? <span className="cx-row__final"
                                           data-in={packageLine ? (line.startsWith("Can’t") ? "cannot" : undefined) : c.in_package}>{line}</span> : null;
                      })()}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** A change with no "before" text: the client's whole clause, drawn as one block with its
 *  own header — so no separate kind tag beside it (B3 p1/p2) */
const wholeClause = (c: ClientChange) => !c.before?.text && !!c.after?.text;

export function Marked({ change, list }: { change: ClientChange; list: Pick<ChangeList, "from" | "to" | "template"> }) {
  // B3 p1 (DESIGN-FOUNDATION §2.5): a clause that is wholly the client's — added, or their
  // own paper — is ONE block with a header, never a page underlined line by line. `<ins>`
  // still tells assistive technology it is the client's text.
  if (wholeClause(change) && change.after?.text) {
    return (
      <div className="cx-whole">
        <p className="cx-whole__head">{change.kind === "ADDED" ? "The client added this clause" : "The client\u2019s own clause"}</p>
        <p className="cx-whole__text"><ins><span className="ws-visually-hidden">client added: </span>{change.after.text}</ins></p>
      </div>
    );
  }
  return (
    <DiffText from={change.before?.text ?? ""} to={change.after?.text ?? ""}
              added="client added" removed="client removed"
              labels={{ from: oursLabel(list),
                        to: `The client's, version ${list.to.version_number}` }} />
  );
}

/** A clause group's label, said as a clause is (`clauseName`): "2 — Invoicing and
 *  Payment" for a number the paper uses twice, else "9 Limitation of Liability". */
export function groupLabel(g: { head: string; title: string | null; name?: string | null }): string {
  return g.name ? `${g.head} — ${g.name}` : [g.head, g.title].filter(Boolean).join(" ");
}

/** THE label of a change — row, card and lists alike: where it is, or — when that only
 *  repeats the group's own label — the changed passage's first words. */
export function rowLabel(change: ClientChange, groupLabel: string): string {
  const label = where(change);
  const words = firstWords(change);
  // a bare number ("1.2") says nothing: the number, then the clause's first words —
  // unless its name (a repeated number) already says its own words
  if (!change.clause.heading && !change.clause.name && change.clause.number && words) return `${label} ${words}`;
  // the group names its heading in sentence case (UI-21): the same words in capitals repeat it
  return label.toLowerCase() !== groupLabel.toLowerCase() ? label : words || label;
}


/** Our reply's files, previewed first (UX Batch 2): "Preview" opens the exact PDF with
 *  Download PDF and Word inside. A reply with an undecided point is refused (`AM-293` r1,
 *  409 REPLY_UNDECIDED); the refusal lists what is open, each point a link to it. */
export function ReplyDownloads({ version, pdf = "reply-pdf", word: hasWord = true }: {
  version: Pick<DocumentVersion, "id"> & Partial<Pick<DocumentVersion, "version_number">>;
  /** our reply's PDF, or — a contract made from our template — the contract's */
  pdf?: "reply-pdf" | "pdf";
  /** false for a final copy of the client's own PDF: there is no Word file (`AM-318`) */
  word?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<{ message: string; gate?: ReplyGate | undefined } | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);   // focus returns here (WCAG 2.4.3)
  async function word() {
    setBusy(true);
    setRefused(null);
    try {
      const { blob, name } = await api.replyFile(version.id, "content");
      saveBlob(blob, name);
    } catch (cause) {
      setRefused({ message: describeError(cause), gate: cause instanceof ApiError ? cause.gate : undefined });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm" onClick={() => { setRefused(null); setOpen(true); }}>
        <IconFile size={14} /> {FEEDBACK_COPY.preview}
      </button>
      {/* AB-213 D8: the file itself, one click from the dialog that says "download it" */}
      {hasWord ? (
        <button type="button" className="ws-btn ws-btn--sm" disabled={busy} aria-busy={busy || undefined}
                onClick={() => void word()}>
          <IconDownload size={14} /> {FEEDBACK_COPY.downloadWord}
        </button>
      ) : null}
      {open ? (
        <PreviewPanel title={`${pdf === "reply-pdf" ? "Our reply" : "The contract"}${version.version_number ? `: version ${version.version_number}` : ""}`}
                      pdfPath={`/document-versions/${encodeURIComponent(version.id)}/${pdf}`}
                      onWord={hasWord ? () => void word() : undefined} wordBusy={busy}
                      onClose={() => setOpen(false)} returnFocus={() => trigger.current}
                      renderError={(cause) => (cause instanceof ApiError && cause.gate
                        ? <GateList message={describeError(cause)} gate={cause.gate} /> : null)} />
      ) : null}
      {refused ? <GateList message={refused.message} gate={refused.gate} /> : null}
    </>
  );
}

/** What keeps our reply inside LegalMind (`AM-293`): the review's open points, each a
 *  link to that point on the reply (the Document tab's `?finding=`). */
export function GateList({ message, gate }: { message: string; gate?: ReplyGate | null | undefined }) {
  return (
    <div className="cx-blocked" role="alert">
      <p className="cx-blocked__title">{message}</p>
      {gate?.reason === "ANALYSIS_NOT_FINISHED" ? (
        <p className="ws-pane__note">The reply is being reviewed like any upload. It can be downloaded once its review
          has finished and nothing in it is undecided.</p>
      ) : null}
      {gate?.open_points.length ? (
        <ul className="cx-blocked__list">
          {gate.open_points.map((p) => (
            <li key={p.finding_id}>
              <a href={`?finding=${encodeURIComponent(p.finding_id)}`}>{requirementTitle({ code: p.requirement_code })}</a>
              <span>needs a decision</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** "Send our reply" / "Send to client" (`AM-260`): LegalMind sends nothing itself, so the
 *  step says what it is — download the file, send it to the client, record when it went
 *  (once, audited, server-checked: a reply with an undecided point is refused, `AM-293`).
 *  The final contract (`AM-318`) is only downloaded: it is signed in another tool, and
 *  recording that it went is optional and never moves the deal off Final. */
export function SendOut({ version, label, onSent }: {
  version: Pick<DocumentVersion, "id" | "version_number" | "reply" | "package" | "final_copy" | "sent_at" | "mime_type">;
  label: string; onSent: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);     // U2 r2: Esc hands focus back here
  const final = !!(version.package || version.final_copy);
  useStep(final ? "downloadFinal" : version.reply ? "sendReply" : "sendToClient",
          useCallback(() => setOpen(true), []));
  return (
    <>
      <button ref={trigger} type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => setOpen(true)}>{label}</button>
      {open ? (
        <Dialog onClose={() => setOpen(false)} titleId="lm-sendout-title" returnFocus={() => trigger.current}>
          <h2 id="lm-sendout-title">{label}</h2>
          <p className="ws-pane__note">
            {final ? <>Download version {version.version_number}, the final contract, and sign it in your
              signing tool. Nothing more is needed here.</>
              : <>Download version {version.version_number}, send it to the client from your email, then
                record it here so everyone sees it went.</>}
          </p>
          <div className="cx-dialog__foot cx-dialog__foot--start">
            <ReplyDownloads version={version} pdf={version.reply ? "reply-pdf" : "pdf"}
                            word={version.mime_type !== "application/pdf"} />
          </div>
          {error ? <p className="cx-error" role="alert">{error}</p> : null}
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" onClick={() => setOpen(false)}>{final ? "Close" : "Cancel"}</button>
            {final && version.sent_at ? null : (
              <button type="button" className={`ws-btn${final ? "" : " ws-btn--primary"}`} disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          await api.markSent(version.id);
                          setOpen(false);
                          onSent();
                        } catch (cause) {
                          setError(describeError(cause));
                        } finally {
                          setBusy(false);
                        }
                      }}>
                {busy ? "Recording…" : final ? "Record that you sent it" : "I have sent it"}
              </button>
            )}
          </div>
        </Dialog>
      ) : null}
    </>
  );
}

export { ReplyNotice } from "./ReplyNotice";

/** "Prepare our reply": the server's own refusal, said before it is asked — the button
 *  stays until nothing is open, and beside it a list of what is still open, each a link
 *  to that change. Prepared, the record opens on the reply version, where its notice
 *  carries the files and Mark sent — one place, not two. */
export function ReplyBar({ contractId, versions, list, onVersionCreated, onPick }: {
  contractId: string; versions: DocumentVersion[]; list: ChangeList; onVersionCreated: () => void;
  onPick: (rowKey: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState<ManualRow[] | null>(null);
  const [showOpen, setShowOpen] = useState(false);
  const latest = versions[0];
  const ours = latest?.reply && latest.version_number > list.to.version_number ? latest : null;
  const blockers = replyBlockers(list.changes);
  const blocked = blockers.open.length + blockers.legal.length + blockers.approval.length;
  const answered = list.summary.total - blockers.open.length;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `prepare` reads the latest state
  useStep("prepareReply", useCallback(() => { if (!blocked && !busy) void prepare(); }, [blocked, busy]));

  async function prepare(leave?: ManualRow[]) {
    setBusy(true);
    setError(null);
    try {
      // The server opens and runs the reply's review itself (AM-251 r4).
      await api.prepareReply(contractId, leave?.map((r) => r.row_key));
      setManual(null);
      onVersionCreated();
    } catch (cause) {
      // AB-151: the changes the reply cannot write — listed, and left only on confirm
      if (cause instanceof ApiError && cause.code === "REPLY_NOT_APPLIED" && cause.manualRows?.length) {
        setManual(cause.manualRows);
      } else {
        setError(describeError(cause));
      }
    } finally {
      setBusy(false);
    }
  }

  // round 3: nothing to answer, no counter — never "0 of 0" (PLAIN-LANGUAGE §5)
  const progress = list.summary.total ? (
    <span className="cx-bar__count">
      <strong>{answered}</strong> of {list.summary.total} answered
    </span>
  ) : null;
  if (ours) {
    return (
      <div className="cx-bar__end">
        {progress}
        <span className="cx-bar__reply">
          <span>Our reply is version {ours.version_number}
            {ours.sent_at ? `, sent ${formatDate(ours.sent_at)}` : ""}.</span>
          <button type="button" className="ws-btn ws-btn--sm" onClick={onVersionCreated}>
            Open our reply
          </button>
        </span>
      </div>
    );
  }
  if (!list.can_answer) return <div className="cx-bar__end">{progress}</div>;
  // the few waiting on someone first, then the many still to answer
  // only what blocks the reply, grouped by who must act next
  const groups: [string, ClientChange[]][] = [
    ["Waiting for a second approval", blockers.approval],
    ["Legal decides", [...blockers.legal, ...blockers.withLegal]],
    ["The deal owner answers", blockers.withOwner],
  ];
  return (
    <div className="cx-bar__end">
      {/* one counter (PLAIN-LANGUAGE §2.4): what is left, or the answered count once none is */}
      {blocked ? null : progress}
      {blocked ? (
        <button type="button" className="cx-bar__open" aria-expanded={showOpen} aria-controls="cx-blocked"
                onClick={() => setShowOpen((v) => !v)}>
          {blocked} left to answer
          <IconChevronRight size={12} />
        </button>
      ) : null}
      {/* the act is the header's one primary ("Prepare our reply", `nextStep`) */}
      {busy ? <span className="cx-bar__count" role="status" aria-live="polite">{CHANGES_COPY.preparingReply}</span> : null}
      {blocked && showOpen ? (
        <div className="cx-blocked cx-blocked--pop" id="cx-blocked"
             onKeyDown={(event) => { if (event.key === "Escape") setShowOpen(false); }}>
          <p className="cx-blocked__title">Our reply can be prepared once each change is answered and decided.</p>
          {groups.map(([title, rows]) => rows.length ? (
            <div key={title}>
              <span className="cx-label">{title} ({rows.length})</span>
              <ul className="cx-blocked__list">
                {rows.map((c) => (
                  <li key={c.row_key}>
                    <button type="button" className="ws-escalate__link" onClick={() => onPick(c.row_key)}>
                      {where(c)}{c.clause.heading ? null : <span className="cx-blocked__words"> {firstWords(c)}</span>}
                    </button>
                    {readerWord(c) ? <span>{readerWord(c)}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null)}
        </div>
      ) : null}
      {manual ? (
        <Dialog onClose={() => setManual(null)} titleId="cx-manual-title">
          <h2 id="cx-manual-title">
            {manual.length === 1 ? "1 answer" : `${manual.length} answers`} can&rsquo;t be written into the client&rsquo;s file
          </h2>
          <p className="ws-pane__note">
            The reply can still be prepared. These are left as the client wrote them, and you
            restore them by hand in Word after downloading.
          </p>
          <ul className="cx-manual">
            {manual.map((r) => <li key={r.row_key}><strong>{r.clause}</strong><span>{r.reason}</span></li>)}
          </ul>
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" onClick={() => setManual(null)}>Cancel</button>
            <button type="button" className="ws-btn ws-btn--primary" disabled={busy}
                    onClick={() => void prepare(manual)}>
              {busy ? "Preparing our reply…" : "Prepare the reply without them"}
            </button>
          </div>
        </Dialog>
      ) : null}
      {error ? <p className="cx-error" role="alert">{error}</p> : null}
    </div>
  );
}

type Paper = "COMPANY_DRAFT" | "CLIENT_MODIFIED";

/** The confirm line before a declaration that can never be changed (`AM-340`). */
export function declareConfirmLine(versionNumber: number, role: Paper): string {
  return `Declare version ${versionNumber} ${role === "COMPANY_DRAFT" ? "ours" : "the client\u2019s"}? `
    + "This can\u2019t be changed later.";
}

/** P1: say whose paper each undeclared version is, through the existing audited
 *  `PATCH /document-versions/{id}`; the changes are read again after each answer.
 *  Presentation only — the server decides; shown to those who may declare. */
function DeclareRoles({ versions, onDone }: { versions: DocumentVersion[]; onDone: () => void }) {
  const { can } = useSession();
  const [done, setDone] = useState<string[]>([]);
  const [picked, setPicked] = useState<{ version: DocumentVersion; role: Paper } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (!can(P.DOCUMENT_UPLOAD)) return <p>Ask the deal owner to say whose paper it is.</p>;
  async function declare(id: string, role: Paper) {
    setBusy(true);
    setError(null);
    try {
      await api.declareVersion(id, { version_role: role });
      setDone((d) => [...d, id]);
      setPicked(null);
      onDone();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {picked ? (
        <p>
          <span>{declareConfirmLine(picked.version.version_number, picked.role)}</span>{" "}
          <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" disabled={busy}
                  onClick={() => void declare(picked.version.id, picked.role)}>Record it</button>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked(null)}>Cancel</button>
        </p>
      ) : versions.filter((v) => !done.includes(v.id)).map((v) => (
        <p key={v.id}>
          <span>Version {v.version_number}{v.original_filename ? ` (${v.original_filename})` : ""}</span>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked({ version: v, role: "COMPANY_DRAFT" })}>Mark as ours</button>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked({ version: v, role: "CLIENT_MODIFIED" })}>Mark as the client&rsquo;s</button>
        </p>
      ))}
      {error ? <p className="ws-field__error" role="alert">{describeError(error)}</p> : null}
    </>
  );
}

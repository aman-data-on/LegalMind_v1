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
import { ErrorState, LoadingState } from "@/components/Feedback";
import { PreviewPanel } from "@/components/PreviewPanel";
import { StatusChip, chipStatus } from "@/components/StatusChip";
import { FEEDBACK_COPY } from "@/lib/labels";
import { PointStatusIcon } from "./PointStatus";
import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { isOurs, sectionRef } from "@/lib/documentTypes";
import { displayTitle } from "@/lib/templates";
import {
  ACCEPTABLE_EFFECTS, ACTION_LABEL, ANSWER_LABEL, EFFECT_LABEL, KIND_LABEL, ROUTE_REASON, acceptable, actionsFor,
  clauseName, effectLabel, effectSentence, type Measured,
  type AcceptableEffect,
  answersAsLegal, explanation, formattingOnly, changeBucket, historyLine, matches, readerStatus, readerWord, replyBlockers,
  oursLabel, whoLine, where,
  type Answer, type ChangeList, type ClientChange, type EffectForUs, type Filter, type ManualRow, type ReplyGate,
} from "@/lib/changes";
import type { DocumentVersion, Evaluation, Finding } from "@/lib/types";

import "./changes.css";
import { AnswerComposer, DiffText } from "./ChangeComposer";
import { EscalateControl } from "./EscalateControl";
import { USER_STATUS_LABELS, requirementTitle } from "./findingLanguage";
import {
  IconAlertCircle, IconArrowLeft, IconBetter, IconCheck, IconChevronRight, IconClock, IconFile, IconFileMinus, IconLock, IconSame, IconWorse, IconFallback,
} from "./icons";
import { OfferLine } from "./OfferPlaybook";
import { formatDate } from "@/lib/dates";

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
  { id: "POSITIVE", label: "Better for us", empty: "No change here is better for us." },
  { id: "NEUTRAL", label: "No change for us", empty: "No change here leaves us where we were." },
  { id: "FALLBACK", label: "Fallback", empty: "No change here is a fallback from our opening position." },
  { id: "NEGATIVE", label: "Worse for us", empty: "No change here is worse for us." },
];

const EFFECT_ICON: Record<EffectForUs, typeof IconBetter> = { POSITIVE: IconBetter, NEUTRAL: IconSame, FALLBACK: IconFallback, NEGATIVE: IconWorse };
/** a NEGATIVE row not measured worse never wears the "worse" arrow */
const MEASURED_ICON: Record<Measured, typeof IconBetter> = { WORSE: IconWorse, NOT_MEASURED: IconAlertCircle, ABSENT: IconFileMinus, REVIEW: IconAlertCircle };

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
      <ErrorState title="Whose paper is this version?" error={state.error} fix={null}>
        <DeclareRoles versions={versions.filter((v) => !v.version_role && !v.source)} onDone={reload} />
      </ErrorState>
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
  const formatting = data.can_answer ? data.changes.filter((c) => formattingOnly(c) && c.answer === null) : [];
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
        <div className="ws-filter cx-filter" role="group" aria-label="Show changes">
          {FILTERS.filter((f) => !EFFECT_FILTERS.includes(f)).map((f) => (
            <button key={f.id} type="button" aria-pressed={filter === f.id}
                    onClick={() => setPicked(f.id)}>
              {f.label}
              <span className="ws-filter__n">{counts[f.id]}</span>
            </button>
          ))}
        </div>
        <div className="ws-filter cx-filter" role="group" aria-label="For us">
          {EFFECT_FILTERS.map((f) => (
            <button key={f.id} type="button" aria-pressed={filter === f.id}
                    onClick={() => setPicked(f.id)}>
              <ForUs effect={f.id as EffectForUs} />
              <span className="ws-filter__n">{counts[f.id]}</span>
            </button>
          ))}
        </div>
        <ReplyBar contractId={contractId} versions={versions} list={data}
                  onVersionCreated={onVersionCreated} onPick={pick} />
      </div>
      <p className="ws-visually-hidden" role="status" aria-live="polite">{said}</p>
      {packageBar?.(pick)}
      {data.special_conditions_not_applied?.length ? (
        <div className="cx-banner cx-banner--strong" role="note">
          <strong>Annexure A could not be read on this copy, so each change is compared with the contract text as
            written, and every change goes to Legal.</strong>
          <ul>{data.special_conditions_not_applied.map((why) => <li key={why}>{why.charAt(0).toUpperCase() + why.slice(1)}.</li>)}</ul>
        </div>
      ) : null}
      {data.template ? (
        <p className="cx-banner" role="note">
          Made from our blank template{data.template.title
            ? <> &ldquo;{displayTitle(data.template.title)}&rdquo;</> : null}, version {data.template.version}.
          {" "}Filling in the details is not a change;{" "}
          {data.summary.total ? "every other difference from the template is listed here."
            : "nothing else differs from it."}
          {data.template.message ? <><br /><strong>{data.template.message}</strong></> : null}
        </p>
      ) : null}
      {data.summary.untracked > 0 ? (
        <p className="cx-banner" role="note">
          {allUntracked ? (
            <>{data.summary.total === 1 ? <>This change is not</> : <>None of these <strong>{data.summary.total}</strong> changes is</>} marked in the
              client&rsquo;s file — {data.summary.total === 1 ? "it was" : "they were"} made without tracking. LegalMind found each one
              by comparing the text.</>
          ) : (
            <><strong>{data.summary.untracked}</strong> of {data.summary.total} changes are not
              marked in the client&rsquo;s file (made without tracking). Each is tagged
              &ldquo;Untracked&rdquo; in the list.</>
          )}
        </p>
      ) : null}
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
      <div className="cx-grid">
        <nav className="cx-list" id="cx-list" tabIndex={-1} aria-label="Client changes">
          {shown.length ? (
            <ChangeIndex rows={shown} current={current} onPick={open} allUntracked={allUntracked} reader={data} place={place}
                         packageLine={packageLine}
                         formatting={formatting} onKeepAllFormatting={() => setBulk(formatting)} />
          ) : <div className="cx-empty"><p>{emptyText}</p>{showAll}</div>}
        </nav>
        <section className="cx-doc" aria-label={data.from
          ? `Version ${data.to.version_number} against version ${data.from.version_number}`
          : `Version ${data.to.version_number}, the client's paper`}>
          {/* the outline's level between the page's h1 and each passage's h3 (UI review) */}
          <h2 className="ws-visually-hidden">The client&rsquo;s changes in the document</h2>
          <p className="cx-legend">
            {data.from || data.template ? (
              <>{data.template ? <>Our template (version {data.template.version}) against this copy
                (version {data.to.version_number}).</> : <>Version {data.from!.version_number} (ours) → version {data.to.version_number} (the
                client&rsquo;s).</>} <ins>Underlined</ins>: the client added. <del>Struck</del>: the client
                removed.</>
            ) : (
              <>Version {data.to.version_number} is the client&rsquo;s own paper — no version of ours
                comes before it. Each row is a clause our review found differs from our standard.</>
            )}{" "}
            <span className="cx-legend__keys"><kbd>j</kbd> <kbd>k</kbd> next and previous change</span>
          </p>
          {shown.map((c) => (
            <article key={c.row_key} id={`cx-passage-${c.row_key}`} className="cx-passage"
                     aria-current={c.row_key === current?.row_key || undefined}
                     onClick={() => setSelected(c.row_key)}>
              <h3>{where(c)}{formattingOnly(c) ? <span className="cx-tag">Formatting only</span>
                : c.kind !== "MODIFIED" ? <span className="cx-tag">{KIND_LABEL[c.kind]}</span> : null}</h3>
              <Marked change={c} list={data} />
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
      </div>
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
      <h2 id="cx-bulk-title">Keep ours on {n} formatting {n === 1 ? "change" : "changes"}?</h2>
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
          {busy ? "Recording…" : `Keep ours on all ${n}`}
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

/** One line per change, grouped under its top-level clause: where it is, then its kind
 *  and — only where it says something — who answers, untracked, or the answer given.
 *  An open change reads in full ink, an answered one quieter, so the list scans as
 *  "what is left" without a colour or a counter shouting. */
function RowWho({ change, reader }: { change: ClientChange; reader: ChangeList }) {
  const who = whoLine(change, reader);
  if (change.answer) {
    return (
      <span className="cx-row__done" data-waiting={change.waiting_for_approval || undefined}>
        {change.waiting_for_approval ? <IconClock size={11} /> : <IconCheck size={11} />}{who}
      </span>
    );
  }
  return who === "Yours to answer" ? null : <span className="cx-row__tag">{who}</span>;
}

/** A row's clause group: its top-level number; a point on the client's paper no clause
 *  was confirmed for (MISSING included) is not placed, never "opening text". */
export function groupHead(c: ClientChange): string {
  return sectionRef(c.clause.number?.split(".")[0])
    ?? (c.kind === "THEIRS" && !c.after ? "Not placed in a clause" : "Opening text");
}

function ChangeIndex({ rows, current, onPick, allUntracked, reader, formatting, onKeepAllFormatting, place, packageLine }: {
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
  for (const c of rows) {
    if (formattingOnly(c)) continue;
    const top = c.clause.number?.split(".")[0];
    const head = groupHead(c);
    // a number the paper uses twice is two clauses: each row sits in its own parent
    // unit (the server's `group`), told apart by that unit's own words
    const unit = c.clause.group?.key ?? null;
    const last = groups.at(-1);
    if (last?.head !== head || (last?.unit ?? null) !== unit || last?.fmt) {
      groups.push({ key: `${head}-${groups.length}`, head, title: null, name: c.clause.group?.name ?? null, unit, rows: [] });
    }
    const g = groups.at(-1)!;
    g.rows.push(c);
    if (!g.title && c.clause.number === top && c.clause.heading) g.title = c.clause.heading;
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
                    aria-controls={`cx-group-${gi}`} onClick={() => toggle(g.key)}>
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
                  Keep ours on all {formatting.length}
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
                      <span className="cx-row__where">{rowLabel(c, groupLabel(g))}</span>
                      <span className="cx-row__meta">
                        {/* S1 — ONE status on line 1: the review's word against our standard
                            when it asks for a person, else what the change does for us. The
                            effect and our offer are said in the answer panel, never stacked
                            here beside a contradicting word (two-line rule) */}
                        {readerStatus(c) && changeBucket(c) !== "decided" && c.route === "holder"
                          ? <StatusChip status={chipStatus(readerStatus(c)!)} />
                          : <>{changeBucket(c) && c.route === "holder"
                            ? <PointStatusIcon bucket={changeBucket(c)!} size={14} /> : null}<ForUs effect={c.effect_for_us} measured={c.measured} /></>}
                        {/* "Wording changed" is most rows; only a different kind is said */}
                        {c.kind !== "MODIFIED" && c.kind !== "THEIRS" ? <span>{KIND_LABEL[c.kind]}</span> : null}
                        {c.untracked && !allUntracked ? <span className="cx-row__tag">Untracked</span> : null}
                        {/* line 2: the answer, or who answers — "Yours to answer" goes
                            unsaid, the row's full ink already says it is open */}
                        <RowWho change={c} reader={reader} />
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

export function Marked({ change, list }: { change: ClientChange; list: Pick<ChangeList, "from" | "to" | "template"> }) {
  return (
    <DiffText from={change.before?.text ?? ""} to={change.after?.text ?? ""}
              added="client added" removed="client removed"
              labels={{ from: oursLabel(list),
                        to: `The client's, version ${list.to.version_number}` }} />
  );
}

/** The evaluations and findings a holder or an asker acts on — loaded only for the
 *  change on screen, and only when the reader can act. */
function useFindingDetails(ids: string[], wanted: boolean) {
  const [details, setDetails] = useState<{ finding: Finding; evaluations: Evaluation[] }[] | null>(null);
  const key = ids.join(",");
  useEffect(() => {
    if (!wanted || !key) return;
    let cancelled = false;
    Promise.all(key.split(",").map(async (id) => {
      const [finding, evaluations] = await Promise.all([api.finding(id), api.evaluations(id)]);
      return { finding, evaluations };
    }))
      .then((got) => { if (!cancelled) setDetails(got); })
      .catch(() => { if (!cancelled) setDetails([]); });
    return () => { cancelled = true; };
  }, [key, wanted]);
  return details;
}

export function AnswerCard({ change, list, contractId, onAnswered, onReload, inPackage, amendment = false }: {
  change: ClientChange;
  list: ChangeList;
  contractId: string;
  onAnswered: (row: Pick<ClientChange, "row_key" | "answer" | "history" | "waiting_for_approval">) => void;
  onReload: () => void;
  /** `AM-307` U2: "In the final contract: …", when this deal has one */
  inPackage?: string | null | undefined;
  /** `AM-310`: the deal is an amendment — "In the amendment: …" */
  amendment?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ conflict: boolean; message: string } | null>(null);
  const holder = change.route === "holder";
  const legal = answersAsLegal(list);
  // only a change worse for us goes to Legal (`AM-299`): the only one with Ask Legal
  const asking = holder && change.effect_for_us === "NEGATIVE" && list.can_answer && !legal && !change.holder_accepted;
  const actions = actionsFor(change, list);
  const details = useFindingDetails(change.review.after.map((f) => f.finding_id),
                                    holder && (list.can_decide || asking));
  const versions = { from: list.from?.version_number ?? 0, to: list.to.version_number };

  async function answer(which: Answer) {
    setBusy(true);
    setError(null);
    try {
      onAnswered(await api.answerChange(contractId, change.row_key, list.to.version_number, {
        answer: which, expected_version: change.answer?.version_number ?? 0,
        ...(reason.trim() ? { reason: reason.trim() } : {}) }));
      setReason("");
    } catch (cause) {
      setError(answerError(cause));
    } finally {
      setBusy(false);
    }
  }

  const explain = explanation(change, versions);
  // why it is routed where it is — said to whoever does not answer it themselves
  const routeWhy = change.answer || (holder && list.can_decide) ? null : ROUTE_REASON[change.route_reason];
  const given = change.answer;
  const word = readerWord(change);
  const open = change.review.after.filter((f) => f.user_status !== "ACCEPTABLE");
  const point = open[0];
  const waiting = given?.answer === "write_wording" && !!change.waiting_for_approval;

  return (
    <div className="cx-answer">
      <header className="cx-answer__head">
        <h3 title={where(change)}>{rowLabel(change, "")}</h3>
        {/* AM-291 r1: two lines, never one status — the review's word, then who answers */}
        <p className="cx-line1">
          {/* one message (verifier item 7): a clause our standard covers is never also
              "no finding" — the route line says Legal decides it */}
          {word ? <StatusChip status={chipStatus(readerStatus(change)!)} /> : <>
            {changeBucket(change) ? <PointStatusIcon bucket={changeBucket(change)!} /> : null}
            {change.route_reason === "MEASURED_BY_A_STANDARD"
              ? <span>Our standard covers this clause</span> : <span>No finding against our standard here</span>}
          </>}
          {point ? <span> · {requirementTitle({ code: point.requirement_code })}</span> : null}
          {formattingOnly(change) ? <span className="cx-tag">Formatting only</span>
            : change.kind !== "MODIFIED" ? <span className="cx-tag">{KIND_LABEL[change.kind]}</span> : null}
          {change.moved ? <span className="cx-tag">Also moved</span> : null}
        </p>
        <p className="cx-line-forus"><ForUs effect={change.effect_for_us} measured={change.measured} size={15} />
          <span>{effectSentence(change.effect_for_us, change.measured)}</span></p>
        {/* nothing confirmed which clause holds this point: say so, never pick one */}
        {!change.after && change.candidates?.length ? (
          <p className="ws-pane__note">We could not tell which clause covers this. Clauses that may:{" "}
            {change.candidates.map(clauseName).filter(Boolean).join("; ")}.</p>
        ) : null}
        {/* AM-305: the playbook line this change is measured by */}
        <OfferLine change={change} contractId={contractId} />
        <p className="cx-line2" data-route={change.route} data-waiting={waiting || undefined}>
          <strong>{whoLine(change, list)}</strong>
          {routeWhy ? <span>{routeWhy}</span> : null}
        </p>
      </header>

      {/* On a narrow screen the passage column is not shown, so the card carries it. */}
      <div className="cx-answer__passage" tabIndex={0} role="region" aria-label="The changed passage"><Marked change={change} list={list} /></div>

      {given ? <GivenAnswer change={change} waiting={waiting} /> : null}
      {inPackage ? <p className="cx-inpkg"><strong>{amendment ? "In the amendment:" : "In the final contract:"}</strong> {inPackage}</p> : null}

      {change.review.after.length > 1 || change.review_delta.length ? (
        <div className="cx-review">
          {change.review.after.length > 1 ? (
            <>
              <span className="cx-label">From the review of version {versions.to}</span>
              <ul>
                {change.review.after.map((f) => (
                  <li key={f.finding_id}><strong>{USER_STATUS_LABELS[f.user_status]}</strong> · {requirementTitle({ code: f.requirement_code })}</li>
                ))}
              </ul>
            </>
          ) : null}
          {change.review_delta.length && list.from ? (
            <>
              <span className="cx-label">Since version {versions.from}</span>
              <ul>
                {change.review_delta.map((d) => (
                  <li key={d.requirement_code}>
                    {requirementTitle({ code: d.requirement_code })}: {d.before ? USER_STATUS_LABELS[d.before] : "not measured"} →{" "}
                    {d.after ? USER_STATUS_LABELS[d.after] : "not measured"}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
      {change.triage?.reasons.length ? (
        <ul className="cx-reasons">
          {change.triage.reasons.map((r, i) => <li key={i}>{r.reason}</li>)}
        </ul>
      ) : null}

      {legal && actions.length ? (
        <AnswerComposer change={change} list={list} actions={actions} contractId={contractId}
                        details={details} onAnswered={onAnswered} onReload={onReload} />
      ) : null}

      {!legal && actions.length ? (
        <section className="cx-section" aria-label={given ? "Change your answer" : "Your answer"}>
          <h4 className="cx-label">{given ? "Change your answer" : "Your answer"}</h4>
          {change.route === "favour" && change.favour_reason ? <p className="cx-favour">{change.favour_reason}</p> : null}
          <div className="cx-acts">
            {actions.map((a) => (
              <button key={a} type="button"
                      className={`ws-btn ws-btn--sm${change.route === "favour" && a === "accept_theirs" ? " ws-btn--primary" : ""}`}
                      disabled={busy || error?.conflict} onClick={() => void answer(a)}>
                {holder && a === "accept_theirs" ? "Accept theirs — Legal has accepted it" : ACTION_LABEL[a]}
              </button>
            ))}
          </div>
          <label className="cx-reason">
            <span>Reason <span className="cx-reason__opt">(optional, one line)</span></span>
            <input type="text" maxLength={200} value={reason}
                   onChange={(event) => setReason(event.target.value)} />
          </label>
          {error ? (
            <p className="cx-error" role="alert">
              {error.message}{" "}
              {error.conflict ? <button type="button" className="ws-escalate__link" onClick={onReload}>Reload</button> : null}
            </p>
          ) : null}
        </section>
      ) : null}

      {asking ? (
        <section className="cx-section" aria-label="Ask Legal">
          <p className="ws-pane__note">Accepting the client&rsquo;s wording here is Legal&rsquo;s decision — ask them:</p>
          {details === null && change.review.after.length ? <p role="status" className="ws-pane__note">Loading the points…</p> : null}
          {details?.length ? details.map(({ finding }) => {
            const read = change.review.after.find((f) => f.finding_id === finding.id);
            if (!read || read.user_status === "ACCEPTABLE") return null;
            return (
              <div key={finding.id} className="cx-decide__point">
                {/* named only when there are several — one point is the card's line 1 */}
                {open.length > 1 ? (
                  <p className="cx-decide__name">
                    <strong>{USER_STATUS_LABELS[read.user_status]}</strong> · {requirementTitle({ code: read.requirement_code })}
                  </p>
                ) : null}
                <EscalateControl finding={finding} onChanged={onReload} />
              </div>
            );
          }) : details !== null || !change.review.after.length ? (
            <p className="ws-pane__note">No review finding covers this clause, so contact Legal directly, or keep ours.</p>
          ) : null}
        </section>
      ) : null}

      {change.history.length > 1 ? (
        <p className="cx-history"><span className="cx-label">History</span> {historyLine(change.history)}</p>
      ) : null}
      {explain.length ? (
        <details className="cx-explain">
          <summary>Explain this</summary>
          <ul>{explain.map((line, i) => <li key={i}>{line}</li>)}</ul>
        </details>
      ) : null}
    </div>
  );
}

/** The answer on record: what, who and when, the wording it carries and its notes. The
 *  internal note is drawn only when the server sent its key (`AM-285` r3, omitted else). */
function GivenAnswer({ change, waiting }: { change: ClientChange; waiting: boolean }) {
  const given = change.answer!;
  return (
    <div className="cx-given" role="status" id={`cx-given-${change.row_key}`} tabIndex={-1}>
      <p className="cx-given__line">
        {waiting ? <IconClock size={14} /> : <IconCheck size={14} />}
        <span>
          <strong>{capital(ANSWER_LABEL[given.answer])}</strong>
          {" "}— {[given.decided_by, formatDate(given.decided_at)].join(", ")}
          {given.reason ? <span className="cx-given__why">&ldquo;{given.reason}&rdquo;</span> : null}
        </span>
      </p>
      {waiting ? (
        <p className="cx-waiting">
          Your wording is recorded as a Legal Decision. It takes effect when a second person with the
          right approves it — needed on a contract you own or created, or where our
          standard asks for two. The reply cannot be prepared until then.
        </p>
      ) : null}
      {given.wording ? (
        <div className="cx-given__wording">
          <span className="cx-label">Our wording, against theirs</span>
          <DiffText from={change.after?.text ?? ""} to={given.wording} added="we add" removed="we remove"
                    labels={{ from: "Their wording", to: "Our wording" }} />
        </div>
      ) : null}
      {given.client_note ? (
        <p className="cx-note-read cx-note-read--client"><span>Sent to the client</span>{given.client_note}</p>
      ) : null}
      {given.internal_note ? (
        <p className="cx-note-read cx-note-read--internal"><span><IconLock size={12} /> Only Legal sees this — never sent</span>{given.internal_note}</p>
      ) : null}
    </div>
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
  return label !== groupLabel ? label : words || label;
}

/** The changed passage's first words, for a change whose clause has no heading. */
function firstWords(change: ClientChange): string {
  const raw = (change.after ?? change.before)?.text.replace(/\s+/g, " ").trim() ?? "";
  // the clause's own number is already said beside it
  const n = change.clause.number;
  const text = n && raw.startsWith(n) ? raw.slice(n.length).replace(/^[.)\s]+/, "") : raw;
  return text.length > 64 ? `${text.slice(0, 62).trimEnd()}…` : text;
}


/** Our reply's files, previewed first (UX Batch 2): "Preview" opens the exact PDF with
 *  Download PDF and Word inside. A reply with an undecided point is refused (`AM-293` r1,
 *  409 REPLY_UNDECIDED); the refusal lists what is open, each point a link to it. */
export function ReplyDownloads({ version, pdf = "reply-pdf", word: hasWord = true }: {
  version: Pick<DocumentVersion, "id">;
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
      {open ? (
        <PreviewPanel title={pdf === "reply-pdf" ? "Our reply" : "The contract"}
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
  const final = !!(version.package || version.final_copy);
  useStep(final ? "downloadFinal" : version.reply ? "sendReply" : "sendToClient",
          useCallback(() => setOpen(true), []));
  return (
    <>
      <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => setOpen(true)}>{label}</button>
      {open ? (
        <Dialog onClose={() => setOpen(false)} titleId="lm-sendout-title">
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

/** The Document tab says what a reply version IS (`AM-251`): ours, answering the
 *  client's, with its files — and, once sent, when. The counts are the server's,
 *  kept when the reply was prepared; a reply prepared before they were kept says less.
 *  "Mark sent" is the header's primary action at that stage, so it is not repeated here. */
export function ReplyNotice({ version, versions, canSend }: {
  version: DocumentVersion; versions: DocumentVersion[]; canSend: boolean;
}) {
  const reply = version.reply;
  if (!reply) return null;
  const theirs = versions.find((v) => v.id === reply.to_version_id);
  const byHand = reply.by_hand ?? [];
  return (
    <section className="ws-replynote" aria-label="Our reply" data-sent={version.sent_at ? "" : undefined}>
      <div className="ws-replynote__text">
        <p className="ws-replynote__title">
          Version {version.version_number} is our reply to the client&rsquo;s
          {theirs ? ` version ${theirs.version_number}` : " version"}
        </p>
        <p className="ws-replynote__sub">
          {reply.tracked !== undefined
            ? `${reply.tracked} of our changes ${reply.tracked === 1 ? "is" : "are"} in it as tracked changes`
            : "Our answers are in it as tracked changes"}
          {byHand.length ? `; ${byHand.length} to restore by hand in Word (${byHand.join(", ")})` : ""}.
          {" "}
          {version.sent_at
            ? <strong>Sent to the client on {formatDate(version.sent_at)}.</strong>
            : canSend ? "Send our reply from the top of the page once it has gone to the client."
            : "Not yet sent to the client."}
        </p>
      </div>
      <div className="ws-replynote__acts">
        <ReplyDownloads version={version} />
      </div>
    </section>
  );
}

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

  const progress = (
    <span className="cx-bar__count">
      <strong>{answered}</strong> of {list.summary.total} answered
    </span>
  );
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
      {progress}
      {blocked ? (
        <button type="button" className="cx-bar__open" aria-expanded={showOpen} aria-controls="cx-blocked"
                onClick={() => setShowOpen((v) => !v)}>
          {blocked} still open before the reply
          <IconChevronRight size={12} />
        </button>
      ) : null}
      {/* the act is the header's one primary ("Prepare our reply", `nextStep`) */}
      {busy ? <span className="cx-bar__count" role="status">Preparing our reply…</span> : null}
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
                  onClick={() => void declare(picked.version.id, picked.role)}>Confirm</button>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked(null)}>Cancel</button>
        </p>
      ) : versions.filter((v) => !done.includes(v.id)).map((v) => (
        <p key={v.id}>
          <span>Version {v.version_number}{v.original_filename ? ` (${v.original_filename})` : ""} is</span>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked({ version: v, role: "COMPANY_DRAFT" })}>ours</button>{" "}
          <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                  onClick={() => setPicked({ version: v, role: "CLIENT_MODIFIED" })}>the client&rsquo;s</button>
        </p>
      ))}
      {error ? <p className="ws-field__error" role="alert">{describeError(error)}</p> : null}
    </>
  );
}

"use client";

/**
 * Legal's answer to one client change (CLM S2; `AM-284`, `AM-285`, `AM-291` r2): one
 * choice of Keep ours · Accept theirs · Use our standard · Write our wording, then that
 * choice's panel, so every answer carries the same reason and notes. The actions offered
 * are `actionsFor`'s — the server's flags — and an action the reader may not take is not
 * drawn. Accepting a point a standard measures is a Legal Decision: since AB-213 D9 the
 * lawyer's Accept and reason record it (Accept the deviation) and then the answer, in one
 * step; only an effective acceptance lets the answer record. The wording is a person's, typed here; nothing drafts or completes it
 * (`AM-284` r7). The internal note is offered only to a reader who could read it back
 * (`legal_position.view`, `AM-285` r3) — for anyone else the field does not exist.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ApiError, api, describeError } from "@/lib/api";
import { ACTION_LABEL, answerFor, isHeading, redline, verdictsFor, where, type Answer, type ChangeList, type ClientChange, type Mark, type Verdict } from "@/lib/changes";
import { VERDICT_COPY, VERDICT_LABELS } from "@/lib/labels";
import { useSeesLegalPosition } from "@/lib/session";
import type { Evaluation, Finding } from "@/lib/types";

import { requirementTitle } from "./findingLanguage";
import { IconArrowLeft, IconLock } from "./icons";
import { StatusChip, chipStatus } from "@/components/StatusChip";

export const NO_STANDARD = "No standard clause is published for this point yet.";
/** A THEIRS point not confirmed in exactly one clause: the reply cannot place wording. */
export const BY_HAND = "The reply cannot place this wording in one clause of theirs. You will add it by hand in Word after downloading.";

/** A refused answer, in words. 409 CONFLICT is a colleague's newer answer — never retried. */
export function composerError(cause: unknown): { conflict: boolean; message: string } {
  if (cause instanceof ApiError && cause.code === "NO_STANDARD_CLAUSE") return { conflict: false, message: NO_STANDARD };
  const conflict = cause instanceof ApiError && cause.status === 409 && cause.code === "CONFLICT";
  return { conflict, message: conflict ? "Changed by a colleague — reload to see their answer." : describeError(cause) };
}

type Answered = Pick<ClientChange, "row_key" | "answer" | "history" | "waiting_for_approval">;

/** One mark, saying itself in words for a screen reader (never colour alone). */
function MarkSpan({ m, added, removed }: { m: Mark; added: string; removed: string }) {
  if (m.op === "eq") return <span>{m.text}</span>;
  if (m.op === "case") return <span className="cx-case"><span className="ws-visually-hidden">capitals changed: </span>{m.text}</span>;
  return m.op === "ins"
    ? <ins><span className="ws-visually-hidden">{added}: </span>{m.text}</ins>
    : <del><span className="ws-visually-hidden">{removed}: </span>{m.text}</del>;
}

/** Text marked as an edit of another, the way a lawyer reads it: a small edit marked
 *  word by word in place (punctuation and capitals by character); a rewritten clause
 *  (`REWRITE_SHARE` of its words) as a replaced block — the old text struck above, the
 *  new below, each named — never the two interleaved word by word. */
export function DiffText({ from, to, added, removed, labels }: {
  from: string; to: string; added: string; removed: string;
  /** the two blocks' names, when the text is rewritten */
  labels: { from: string; to: string };
}) {
  const { replaced, marks } = redline(from, to);
  if (replaced) {
    return (
      <div className="cx-replaced">
        <div className="cx-replaced__old">
          <span className="cx-replaced__label">{labels.from}</span>
          <p className="cx-marked"><del><span className="ws-visually-hidden">{removed}: </span>{from}</del></p>
        </div>
        <div className="cx-replaced__new">
          <span className="cx-replaced__label">{labels.to}</span>
          <p className="cx-marked"><ins><span className="ws-visually-hidden">{added}: </span>{to}</ins></p>
        </div>
      </div>
    );
  }
  return (
    <p className={`cx-marked${isHeading(to || from) ? " cx-marked--heading" : ""}`}>
      {marks.map((m, i) => <MarkSpan key={i} m={m} added={added} removed={removed} />)}
    </p>
  );
}

/** The two notes, told apart by shape AND words — never a tint alone. The internal one
 *  is drawn only for a reader who could read it back (`AM-285` r3). */
function Notes({ clientNote, setClientNote, internalNote, setInternalNote, seesInternal }: {
  clientNote: string; setClientNote: (v: string) => void;
  internalNote: string; setInternalNote: (v: string) => void; seesInternal: boolean;
}) {
  return (
    <div className="cx-notes">
      <label className="cx-note cx-note--client">
        <span>Sent to the client <span className="cx-reason__opt">— a comment on this change in our reply</span></span>
        <textarea maxLength={500} rows={2} value={clientNote} onChange={(event) => setClientNote(event.target.value)} />
      </label>
      {seesInternal ? (
        <label className="cx-note cx-note--internal">
          <span><IconLock size={12} /> Only Legal sees this <span className="cx-reason__opt">— never sent</span></span>
          <textarea maxLength={1000} rows={2} value={internalNote}
                    onChange={(event) => setInternalNote(event.target.value)} />
        </label>
      ) : null}
    </div>
  );
}

/** Who reads the reason — said under the field, so nobody writes it for the client. */
export const REASON_READERS = "Kept with this answer in LegalMind, for everyone on this contract. Never sent to the client.";

export function AnswerComposer({ change, list, actions, contractId, details, onAnswered, onReload, initial = null }: {
  change: ClientChange;
  list: ChangeList;
  actions: Answer[];
  contractId: string;
  /** the findings on the client's clause, for the Legal Decision (null while loading) */
  details: { finding: Finding; evaluations: Evaluation[] }[] | null;
  onAnswered: (row: Answered) => void;
  onReload: () => void;
  /** the choice open on first render (none: the reader picks) */
  initial?: Answer | null;
}) {
  const id = useId();
  const seesInternal = useSeesLegalPosition();
  const theirs = change.after?.text ?? "";
  // R3 step 10: Legal picks a verdict; Reject then picks the wording sent back
  const [verdict, setVerdict] = useState<Verdict | null>(
    initial === "accept_theirs" ? "accept" : initial === "write_wording" ? "accept_changes"
      : initial === "ask_client" ? "ask_client" : initial ? "reject" : null);
  const [rejectWith, setRejectWith] = useState<Answer | null>(initial);
  const choice = answerFor(verdict, actions, rejectWith);
  const [share, setShare] = useState(false);
  // a second answer starts from the wording already recorded, never back at theirs
  const recorded = change.answer?.wording ?? null;
  const [wording, setWording] = useState(recorded ?? theirs);
  const [reason, setReason] = useState("");
  const [clientNote, setClientNote] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ conflict: boolean; message: string } | null>(null);
  // the wording editor opens over the list and the passage (the wide centre), never in
  // this narrow card: a portal into the pane's slot, so its state stays here
  // (looked up on render: the choice is a click, so the pane — and its slot — is mounted)
  const slot = choice === "write_wording" && typeof document !== "undefined"
    ? document.getElementById("cx-editor-slot") : null;
  const editorRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (choice === "write_wording") window.requestAnimationFrame(() => editorRef.current?.focus());
  }, [choice]);

  const several = change.review.after.filter((f) => f.user_status !== "ACCEPTABLE").length > 1;
  const measured = !change.unmeasured && change.review.after.some((f) => f.evaluation_ids.length);
  const verdicts = verdictsFor(actions);
  const wordings = actions.filter((a) => a === "keep_ours" || a === "use_standard");
  // the condition stays Legal's (the internal note, omitted for other readers) unless
  // shared; a reader who cannot keep an internal note shares it (rule 18: never hidden in the UI only)
  const shared = share || !seesInternal;
  // accepting a point Legal decides is the decision itself until one accepts it (AM-250 r2)
  const decides = choice === "accept_theirs" && change.route === "holder" && !change.holder_accepted
    && !change.unmeasured;
  const reasonRequired = choice === "write_wording" || decides
    || (choice === "accept_theirs" && change.route === "holder" && !!change.unmeasured);
  // AB-213 D9: the points Accept decides in the same step (each with the same reason)
  const toDecide = decides ? (details ?? []).flatMap(({ finding, evaluations }) => {
    const read = change.review.after.find((f) => f.finding_id === finding.id);
    // a match is no deviation: only the evaluations that differ get a Legal Decision
    return !read || read.user_status === "ACCEPTABLE" ? []
      : evaluations.filter((e) => e.classification !== "MATCH");
  }) : [];
  const ready = !!choice && (!decides || details !== null) && (!reasonRequired || !!reason.trim())
    && (choice !== "ask_client" || !!clientNote.trim())
    && (choice !== "write_wording" || (!!wording.trim() && wording.trim() !== theirs.trim()));

  async function submit() {
    if (!choice || !ready) return;
    setBusy(true);
    setError(null);
    const condition = choice === "write_wording" && !shared ? reason.trim() : "";
    const why = condition ? VERDICT_COPY.conditionKept : reason.trim();
    const [note, inside] = [clientNote.trim(), [condition, internalNote.trim()].filter(Boolean).join("\n\n")];
    const standard = choice === "use_standard" ? change.anchor?.clause_version_id : null;
    try {
      // AB-213 D9 (AM-405 r2): one step — the lawyer's Accept, with their reason, is their
      // Legal Decision to accept each measured point, then the answer. A decision that
      // waits for a second person stops here; the answer follows once it takes effect.
      for (const evaluation of toDecide) {
        const done = await api.recordDecision(evaluation.id, {
          decision_type: "ACCEPT_DEVIATION", justification: reason.trim(),
          expected_version: evaluation.current_decision?.version_number ?? 0,
        });
        if (!done.is_effective) {
          setError({ conflict: false, message: "Recorded. It waits for a second Legal approval before their wording is accepted." });
          onReload();
          return;
        }
      }
      onAnswered(await api.answerChange(contractId, change.row_key, list.to.version_number, {
        answer: choice, expected_version: change.answer?.version_number ?? 0,
        ...(why ? { reason: why } : {}),
        ...(choice === "write_wording" ? { wording: wording.trim() } : {}),
        ...(standard ? { clause_version_id: standard } : {}),
        ...(note ? { client_note: note } : {}),
        ...(seesInternal && inside ? { internal_note: inside } : {}),
      }));
      setVerdict(null);
    } catch (cause) {
      setError(composerError(cause));
    } finally {
      setBusy(false);
    }
  }

  const ours = change.before?.text ?? "";
  const panel: Record<Answer, ReactNode> = {
    ask_client: (
      <>
        <p className="cx-panel__what">{VERDICT_COPY.askHelp}</p>
        <label className="cx-note cx-note--client">
          <span>{VERDICT_COPY.askLabel}</span>
          <textarea maxLength={500} rows={3} required value={clientNote}
                    onChange={(event) => setClientNote(event.target.value)} />
        </label>
        {measured ? <p className="ws-pane__note">Each point on this clause is recorded as waiting for the
          client&apos;s answer.</p> : null}
      </>
    ),
    keep_ours: <p className="cx-panel__what">Our wording from version {list.from?.version_number} stays. The reply restores it
      as a tracked change.</p>,
    accept_theirs: decides ? (
      <>
        <p className="cx-panel__what">Accepting their wording records your Legal Decision to accept the difference
          from our standard{several ? " on each point below" : ""}, with your reason.</p>
        {details === null ? <p role="status" className="ws-pane__note">Loading the points…</p> : null}
        {several ? change.review.after.filter((f) => f.user_status !== "ACCEPTABLE").map((read) => (
          <p key={read.finding_id} className="cx-decide__name">
            <StatusChip status={chipStatus(read.user_status, read.in_our_favour)} /> {requirementTitle({ code: read.requirement_code })}
          </p>
        )) : null}
      </>
    ) : change.route === "holder" && change.unmeasured ? (
      <p className="cx-panel__what">None of our standards covers this clause, so accepting it is recorded as your answer,
        not a Legal Decision.</p>
    ) : <p className="cx-panel__what">Their wording stands in the reply as they wrote it.</p>,
    use_standard: <p className="cx-panel__what">Their wording is replaced word for word by our published standard clause. If none is published, nothing is recorded.</p>,
    write_wording: <p className="cx-panel__what">Our wording is open in the editor.</p>,
  };

  const errorLine = error ? (
    <p className="cx-error" role="alert">
      {error.message}{" "}
      {error.conflict ? <button type="button" className="ws-escalate__link" onClick={onReload}>Reload</button> : null}
    </p>
  ) : null;
  const versionTo = list.to.version_number;
  // "Write our wording", wide: their text and ours side by side, the redline the client
  // will receive (with the note as the comment they get), and a footer that never
  // scrolls away — reason, who reads it, and "Record our wording".
  const editor = (
    <form className="cx-editor" aria-labelledby={`${id}-ed`} data-testid="wording-editor"
          onSubmit={(event) => { event.preventDefault(); void submit(); }}
          onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); setVerdict(null); } }}>
      <header className="cx-editor__head">
        <button type="button" className="ws-btn ws-btn--sm cx-editor__back" onClick={() => setVerdict(null)}>
          <IconArrowLeft size={14} /> Back to the choices
        </button>
        <h3 id={`${id}-ed`}>Write our wording <span>{where(change)}</span></h3>
      </header>
      <div className="cx-editor__body">
        <div className="cx-editor__cols">
          <div className="cx-editor__theirs">
            <span className="cx-label">{change.before ? `The client's version ${versionTo}, against ours` : `The client's version ${versionTo}`}</span>
            <div className="cx-editor__ref">
              {change.before ? (
                <DiffText from={ours} to={theirs} added="client added" removed="client removed"
                          labels={{ from: `Ours, version ${list.from?.version_number ?? ""}`, to: `The client's, version ${versionTo}` }} />
              ) : <p className="cx-marked">{theirs}</p>}
            </div>
          </div>
          <div className="cx-editor__ours">
            <label className="cx-label" htmlFor={`${id}-wording`}>
              Our wording <span className="cx-reason__opt">{recorded ? "(starts as the wording we recorded — edit it)" : "(starts as theirs — edit it)"}</span>
            </label>
            <textarea id={`${id}-wording`} ref={editorRef} className="cx-wording__input" maxLength={5000} value={wording}
                      onChange={(event) => setWording(event.target.value)} />
          </div>
        </div>
        <div className="cx-editor__preview" aria-live="polite">
          <span className="cx-label">How the client will see it</span>
          <div className="cx-editor__page">
            {wording.trim() === theirs.trim()
              ? <p className="ws-pane__note">No change from their wording yet.</p>
              : <DiffText from={theirs} to={wording} added="we add" removed="we remove"
                          labels={{ from: "Their wording", to: "Our wording" }} />}
            {clientNote.trim() ? (
              <aside className="cx-balloon" aria-label="Our comment, as the client sees it">
                <span>Our comment in the reply</span>{clientNote.trim()}
              </aside>
            ) : null}
          </div>
        </div>
        <Notes clientNote={clientNote} setClientNote={setClientNote} internalNote={internalNote}
               setInternalNote={setInternalNote} seesInternal={seesInternal} />
        {measured ? <p className="ws-pane__note">On this point your wording is recorded as a Legal Decision — the
          reply waits for it to take effect.</p> : null}
      </div>
      <footer className="cx-editor__foot">
        <div className="cx-condition">
          <Reason required value={reason} onChange={setReason} condition shared={shared} />
          {seesInternal ? (
            <label className="cx-share">
              <input type="checkbox" checked={share} onChange={(event) => setShare(event.target.checked)} />
              {VERDICT_COPY.share}
            </label>
          ) : null}
        </div>
        <div className="cx-editor__submit">
          {errorLine}
          <button type="submit" className="ws-btn ws-btn--primary" disabled={busy || !ready || error?.conflict}>
            {busy ? "Recording…" : "Record our wording"}
          </button>
        </div>
      </footer>
    </form>
  );

  return (
    <section className="cx-section cx-compose" aria-labelledby={`${id}-title`}>
      <h4 id={`${id}-title`} className="cx-label">{change.answer ? "Change your answer" : "Your answer"}</h4>
      <div className="cx-choices" role="radiogroup" aria-labelledby={`${id}-title`}>
        {verdicts.map((v) => (
          <label key={v} className="cx-choice" data-on={verdict === v || undefined}>
            <input type="radio" name={`${id}-choice`} value={v} checked={verdict === v}
                   onChange={() => { setVerdict(v); setError(null); }} />
            <span>{VERDICT_LABELS[v]}</span>
          </label>
        ))}
      </div>
      {verdict === "reject" && wordings.length > 1 ? (
        <fieldset className="cx-rejectwith">
          <legend>{VERDICT_COPY.rejectWith}</legend>
          <div className="cx-choices" role="radiogroup">
            {wordings.map((a) => (
              <label key={a} className="cx-choice" data-on={rejectWith === a || undefined}>
                <input type="radio" name={`${id}-reject`} value={a} checked={rejectWith === a}
                       onChange={() => { setRejectWith(a); setError(null); }} />
                <span>{ACTION_LABEL[a]}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}
      {change.kind === "THEIRS" && !change.anchor?.clause_version_id ? (
        <p className="ws-pane__note">{NO_STANDARD}</p>
      ) : null}
      {/* the reply writes into ONE clause of theirs: none known, or several — by hand */}
      {change.kind === "THEIRS" && (choice === "write_wording" || choice === "use_standard")
        && (!change.after || (change.clauses?.length ?? 0) > 1) ? (
        <p className="ws-pane__note">{BY_HAND}</p>
      ) : null}

      {choice === "write_wording" ? (
        <>
          {panel.write_wording}
          {slot ? createPortal(editor, slot) : editor}
        </>
      ) : choice ? (
        <form className="cx-panel" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          {panel[choice]}
          <Reason required={reasonRequired} value={reason} onChange={setReason} />
          {choice === "ask_client" ? null : (
            <Notes clientNote={clientNote} setClientNote={setClientNote} internalNote={internalNote}
                   setInternalNote={setInternalNote} seesInternal={seesInternal} />)}
          <div className="cx-panel__foot">
            <button type="submit" className="ws-btn ws-btn--sm ws-btn--primary"
                    disabled={busy || !ready || error?.conflict}>
              {busy ? "Recording…" : ACTION_LABEL[choice]}
            </button>
          </div>
          {errorLine}
        </form>
      ) : null}
    </section>
  );
}

function Reason({ required, value, onChange, condition = false, shared = true }: {
  required: boolean; value: string; onChange: (v: string) => void;
  /** R3 "Accept with changes": the field is Legal's condition, Legal's own unless shared */
  condition?: boolean; shared?: boolean;
}) {
  const id = useId();
  return (
    <label className="cx-reason">
      <span>{condition ? VERDICT_COPY.condition : "Reason"} <span className="cx-reason__opt">{required ? "(required)" : "(optional, one line)"}</span></span>
      <input type="text" maxLength={200} required={required} value={value} aria-describedby={`${id}-who`}
             onChange={(event) => onChange(event.target.value)} />
      <span id={`${id}-who`} className="cx-reason__who">{condition && !shared ? VERDICT_COPY.conditionHelp : REASON_READERS}</span>
    </label>
  );
}

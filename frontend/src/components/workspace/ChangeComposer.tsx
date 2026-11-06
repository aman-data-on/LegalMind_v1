"use client";

/**
 * Legal's answer to one client change (CLM S2; `AM-284`, `AM-285`, `AM-291` r2): one
 * choice of Keep ours · Accept theirs · Use our standard · Write our wording, then that
 * choice's panel, so every answer carries the same reason and notes. The actions offered
 * are `actionsFor`'s — the server's flags — and an action the reader may not take is not
 * drawn. Accepting a point a standard measures is a Legal Decision: its panel places the
 * existing `DecisionControl` (unchanged), and only an effective acceptance lets the
 * answer record. The wording is a person's, typed here; nothing drafts or completes it
 * (`AM-284` r7). The internal note is offered only to a reader who could read it back
 * (`legal_position.view`, `AM-285` r3) — for anyone else the field does not exist.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ApiError, api, describeError } from "@/lib/api";
import { ACTION_LABEL, isHeading, redline, where, type Answer, type ChangeList, type ClientChange, type Mark } from "@/lib/changes";
import { useSeesLegalPosition } from "@/lib/session";
import type { Evaluation, Finding } from "@/lib/types";

import { DecisionControl } from "./DecisionControl";
import { USER_STATUS_LABELS, requirementTitle } from "./findingLanguage";
import { IconArrowLeft, IconLock } from "./icons";

export const NO_STANDARD = "No standard clause is published for this point yet.";

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
  const [choice, setChoice] = useState<Answer | null>(initial);
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
  // accepting a point Legal decides is the decision itself until one accepts it (AM-250 r2)
  const decides = choice === "accept_theirs" && change.route === "holder" && !change.holder_accepted
    && !change.unmeasured;
  const reasonRequired = choice === "write_wording"
    || (choice === "accept_theirs" && change.route === "holder" && !!change.unmeasured);
  const ready = !!choice && !decides && (!reasonRequired || !!reason.trim())
    && (choice !== "write_wording" || (!!wording.trim() && wording.trim() !== theirs.trim()));

  async function submit() {
    if (!choice || !ready) return;
    setBusy(true);
    setError(null);
    const [why, note, inside] = [reason.trim(), clientNote.trim(), internalNote.trim()];
    const standard = choice === "use_standard" ? change.anchor?.clause_version_id : null;
    try {
      onAnswered(await api.answerChange(contractId, change.row_key, list.to.version_number, {
        answer: choice, expected_version: change.answer?.version_number ?? 0,
        ...(why ? { reason: why } : {}),
        ...(choice === "write_wording" ? { wording: wording.trim() } : {}),
        ...(standard ? { clause_version_id: standard } : {}),
        ...(note ? { client_note: note } : {}),
        ...(seesInternal && inside ? { internal_note: inside } : {}),
      }));
      setChoice(null);
    } catch (cause) {
      setError(composerError(cause));
    } finally {
      setBusy(false);
    }
  }

  const ours = change.before?.text ?? "";
  const panel: Record<Answer, ReactNode> = {
    keep_ours: <p className="cx-panel__what">Our wording from version {list.from?.version_number} stays. The reply restores it
      as a tracked change.</p>,
    accept_theirs: decides ? (
      <>
        <p className="cx-panel__what">Record your Legal Decision on each point below, then accept their wording.</p>
        {details === null ? <p role="status" className="ws-pane__note">Loading the points…</p> : null}
        {details?.map(({ finding, evaluations }) => {
          const read = change.review.after.find((f) => f.finding_id === finding.id);
          if (!read || read.user_status === "ACCEPTABLE") return null;   // nothing to decide on a match
          return (
            <div key={finding.id} className="cx-decide__point">
              {/* named only when there are several — one point is the card's line 1 */}
              {several ? (
                <p className="cx-decide__name">
                  <strong>{USER_STATUS_LABELS[read.user_status]}</strong> · {requirementTitle({ code: read.requirement_code })}
                </p>
              ) : null}
              {evaluations.map((evaluation) => (
                <DecisionControl key={evaluation.id} evaluation={evaluation} onRecorded={onReload} />
              ))}
            </div>
          );
        })}
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
          onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); setChoice(null); } }}>
      <header className="cx-editor__head">
        <button type="button" className="ws-btn ws-btn--sm cx-editor__back" onClick={() => setChoice(null)}>
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
        <Reason required value={reason} onChange={setReason} />
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
        {actions.map((a) => (
          <label key={a} className="cx-choice" data-on={choice === a || undefined}>
            <input type="radio" name={`${id}-choice`} value={a} checked={choice === a}
                   onChange={() => { setChoice(a); setError(null); }} />
            <span>{ACTION_LABEL[a]}</span>
          </label>
        ))}
      </div>
      {change.kind === "THEIRS" && !change.anchor?.clause_version_id ? (
        <p className="ws-pane__note">{NO_STANDARD}</p>
      ) : null}

      {choice === "write_wording" ? (
        <>
          {panel.write_wording}
          {slot ? createPortal(editor, slot) : editor}
        </>
      ) : choice && decides ? (
        // the Legal Decision's own forms: never inside another form, whose submit
        // would swallow "Record decision"
        <div className="cx-panel">{panel[choice]}{errorLine}</div>
      ) : choice ? (
        <form className="cx-panel" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          {panel[choice]}
          <Reason required={reasonRequired} value={reason} onChange={setReason} />
          <Notes clientNote={clientNote} setClientNote={setClientNote} internalNote={internalNote}
                 setInternalNote={setInternalNote} seesInternal={seesInternal} />
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

function Reason({ required, value, onChange }: { required: boolean; value: string; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <label className="cx-reason">
      <span>Reason <span className="cx-reason__opt">{required ? "(required)" : "(optional, one line)"}</span></span>
      <input type="text" maxLength={200} required={required} value={value} aria-describedby={`${id}-who`}
             onChange={(event) => onChange(event.target.value)} />
      <span id={`${id}-who`} className="cx-reason__who">{REASON_READERS}</span>
    </label>
  );
}

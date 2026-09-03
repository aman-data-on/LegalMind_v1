"use client";

/**
 * Ask about this document — a SECONDARY, floating interaction (owner directive,
 * 2026-09-02; DD-15, superseding DD-9 §4).
 *
 * What changed and why
 * --------------------
 * The former `AskBar` was a permanent row at the bottom of `.ws-workmain`: an
 * input, a suggestion-chip row and an honesty note, ~128px of the workspace's
 * height reserved on every screen whether or not anyone was asking anything.
 * The owner's objection is a hierarchy objection, not a styling one — the
 * document, the clauses and the findings are the work; Ask is a tool you reach
 * for. So Ask now occupies NO layout row at all. It is a launcher pinned in the
 * bottom-right of the workspace, and the conversation opens over the canvas.
 *
 * The interaction pattern, and why not hover
 * ------------------------------------------
 * A disclosure, not a modal, and click/Enter/Space — never hover-to-open. Hover
 * cannot be performed on a touch screen at all, and a corner panel that opens on
 * pointer transit opens constantly by accident while someone is reading. Hover
 * therefore drives visual affordance only. The panel is `role="dialog"` with
 * `aria-modal="false"`: focus is MOVED to the input on open but never trapped,
 * so a reader can tab straight back out into the clause list, click a clause, or
 * scroll the document with the conversation still open. Escape closes and
 * returns focus to the launcher.
 *
 * The launcher floats above the panels, so — WCAG 2.2 AA 2.4.11, "Focus Not
 * Obscured", which names chat widgets explicitly — the scrolling panels carry
 * bottom padding equal to its footprint (`workspace.css`), and it hides itself
 * while the conversation is open. Nothing can come to rest underneath it.
 *
 * Version context is now explicit, and that is the actual defect fixed
 * ---------------------------------------------------------------------
 * Ask used to be DISABLED whenever an older version was open, with a button
 * offering to "open the latest version" — because the server always answered
 * from the newest version, so an answer's citations pointed at evidence rows
 * that are not in the open version's reading order. The API now takes the
 * version being asked about, so Ask works on EVERY version: it answers about the
 * document on screen and names which one in its header.
 *
 * A conversation is contract-scoped (`AM-27`: "an assist-lane session"), so a
 * transcript may legitimately contain turns answered from different versions.
 * Each answer therefore carries its own version, a turn from another version
 * says so, and its citations offer to open THAT version rather than pretending
 * to highlight a row the open page does not contain.
 *
 * Unchanged from the former bar, deliberately:
 *
 *   ANSWERED            prose + numbered citations; each citation POINTS at its
 *                       evidence row through the slice-1 highlight gesture
 *   a refusal           the identical sentence whatever the cause (`AM-29` r4),
 *                       on the quiet surface — the system working, not failing
 *   routed_to_evaluator a compliance-shaped question is a pointer to the
 *                       Findings pane, a third type, not an answer or a refusal
 *
 * The conversation is durable: on mount the dock reopens this contract's most
 * recent conversation — the server keeps citations across reloads. A finding's
 * "Ask about this" arrives as an EDITABLE draft (askIntent), which OPENS the
 * dock and focuses the input, and never sends. One honest status line while a
 * request is in flight (decision #180); scores are retrieval scores, labelled as
 * exactly that (`AI-03` item 16, rule 12).
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { ApiError, api, describeError } from "@/lib/api";
import type { AskResult, ConversationTurn } from "@/lib/types";

import { useAskIntent } from "./askIntent";
import { useHighlight } from "./highlight";
import { IconSend, IconSparkle, IconX } from "./icons";

interface Turn {
  question: string;
  result: AskResult | null;
  error: string | null;
  /** The version this turn was answered from — null when nothing was retrieved. */
  versionNumber: number | null;
  documentVersionId: string | null;
}

/** A replayed turn pair from `GET /conversations/{id}` in the live dock's shape. */
export function turnsFromHistory(messages: ConversationTurn[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role === "USER") {
      turns.push({
        question: message.content,
        result: null,
        error: null,
        versionNumber: null,
        documentVersionId: null,
      });
    } else {
      const last = turns[turns.length - 1];
      if (!last) continue;
      last.result = {
        conversation_id: "",
        message_id: message.id,
        answer_state: message.answer_state ?? "ANSWERED",
        text: message.content,
        routed_to_evaluator: message.routed_to_evaluator,
        document_version_id: message.document_version_id ?? "",
        version_number: message.version_number ?? 0,
        citations: message.citations,
      };
      last.versionNumber = message.version_number;
      last.documentVersionId = message.document_version_id;
    }
  }
  return turns;
}

export function AskDock({
  contractId,
  documentVersionId,
  versionNumber,
  isLatest,
  onOpenVersion,
}: {
  contractId: string;
  /** The version on screen — what a question is about. */
  documentVersionId: string;
  versionNumber: number;
  /** Whether the open version is the newest; used for the header's wording only. */
  isLatest: boolean;
  /** Open another version — for a citation belonging to a different one. */
  onOpenVersion?: ((documentVersionId: string) => void) | undefined;
}) {
  const askIntent = useAskIntent();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [restoring, setRestoring] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const conversationRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const busy = pending !== null;
  const titleId = useId();

  // Reopen this contract's most recent conversation, citations intact. Scoped to
  // the contract, not the version: the history belongs to the document, and each
  // turn reports which version answered it.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { items } = await api.conversations({ contract_id: contractId, page_size: 1 });
        const latest = items[0];
        if (!latest || cancelled) return;
        const detail = await api.conversation(latest.id);
        if (cancelled) return;
        conversationRef.current = detail.id;
        setTurns(turnsFromHistory(detail.messages));
      } catch {
        // History is a convenience; asking still works without it.
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contractId]);

  // A finding's handoff: open the dock, place the draft, focus the input, send
  // nothing. Opening is part of the handoff now that the input is not always on
  // screen — otherwise "Ask about this" would silently do nothing visible.
  const consumedSeq = useRef(0);
  useEffect(() => {
    const draft = askIntent?.draft;
    if (!draft || draft.seq === consumedSeq.current) return;
    consumedSeq.current = draft.seq;
    setQuestion(draft.text);
    setOpen(true);
  }, [askIntent?.draft]);

  /* Focus follows disclosure, in both directions: the input on open, the launcher
   * on close. Never a trap — the panel is not modal, so a reader can tab straight
   * out into the clause list with the conversation still open.
   *
   * It has to run in an effect rather than in the click handler: the launcher is
   * `hidden` while the panel is open, and focusing a hidden element does nothing.
   * Restoring focus therefore has to wait until React has re-rendered it visible.
   * `wasOpen` keeps this from stealing focus on first mount, when nothing was
   * closed and the reader may be anywhere on the page. */
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) inputRef.current?.focus();
    else if (wasOpen.current) launcherRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  const close = useCallback(() => setOpen(false), []);

  /* Escape closes, from anywhere on the page while the panel is open — a
   * non-modal panel can be left with focus somewhere else entirely, and Escape
   * should still dismiss it.
   *
   * Two deliberate restraints. It listens in the BUBBLE phase and does not stop
   * propagation, and it yields to the document pane's annotation popup: that
   * popup is a nested dialog whose textarea has focus and its own Escape
   * handler, so a capture-phase swallow here would close the conversation while
   * leaving the popup the user was actually looking at open. Whichever surface
   * the reader is in is the one Escape belongs to. */
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      const target = event.target;
      if (target instanceof Element && target.closest(".ws-annopop")) return;
      close();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  // The newest turn should be visible whenever the log changes.
  useEffect(() => {
    if (!open) return;
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [open, turns.length, pending]);

  const submit = useCallback(async () => {
    const asked = question.trim();
    if (!asked || busy) return;
    setPending(asked);
    setQuestion("");
    try {
      if (!conversationRef.current) {
        const conversation = await api.createConversation(contractId);
        conversationRef.current = conversation.id;
      }
      // The version on screen is the version asked about — never "whichever is
      // newest". This is the fix; everything else here is presentation.
      const result = await api.ask(conversationRef.current, asked, documentVersionId);
      setTurns((previous) => [...previous, {
        question: asked,
        result,
        error: null,
        versionNumber: result.version_number,
        documentVersionId: result.document_version_id,
      }]);
    } catch (error) {
      const message = error instanceof ApiError ? describeError(error) : "The question could not be sent.";
      setTurns((previous) => [...previous, {
        question: asked, result: null, error: message,
        versionNumber: null, documentVersionId: null,
      }]);
    } finally {
      setPending(null);
    }
  }, [busy, contractId, documentVersionId, question]);

  const turnCount = turns.length;

  return (
    <div className="ws-dock" data-open={open}>
      {/* Narrow viewports only (CSS): a tap outside closes the sheet, the
          expected touch gesture. Decorative — Escape and the close button are
          the accessible paths, so this carries no role and no name. */}
      {open ? (
        <div className="ws-dock__scrim" onClick={close} aria-hidden="true" />
      ) : null}

      <button
        ref={launcherRef}
        type="button"
        className="ws-dock__launcher"
        aria-expanded={open}
        aria-controls={`${titleId}-panel`}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        hidden={open}
      >
        <IconSparkle size={17} />
        <span className="ws-dock__launcher-text">Ask</span>
        {turnCount > 0 ? (
          <span className="ws-dock__count ws-mono" aria-hidden="true">{turnCount}</span>
        ) : null}
        <span className="ws-visually-hidden">
          {turnCount > 0
            ? ` about this document — ${turnCount} earlier ${turnCount === 1 ? "turn" : "turns"}`
            : " about this document"}
        </span>
      </button>

      {/* Kept MOUNTED while closed so a draft, the restored history and the
          scroll position all survive closing and reopening; `inert` keeps it out
          of the tab order and out of the accessibility tree meanwhile. */}
      <section
        className="ws-dock__panel"
        id={`${titleId}-panel`}
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        aria-hidden={!open}
        inert={!open}
      >
        <header className="ws-dock__head">
          <h2 id={titleId} className="ws-dock__title">
            <IconSparkle size={15} /> Ask about this document
          </h2>
          <button type="button" className="ws-dock__close" onClick={close} aria-label="Close Ask">
            <IconX size={16} />
          </button>
        </header>

        {/* Which document a question will be answered about — stated, never
            assumed. Naming the version is what replaced disabling the input. */}
        <p className="ws-dock__scope">
          Answers are about <strong>Version {versionNumber}</strong>
          {isLatest ? " (latest)" : ", the version you are reading"}.
        </p>

        <div className="ws-dock__log" ref={logRef} tabIndex={-1}>
          <ol className="ws-ask__turns" aria-live="polite">
            {turns.map((turn, index) => (
              <li key={index} className="ws-ask__turn">
                <p className="ws-ask__q">
                  <span className="ws-ask__role">You</span> {turn.question}
                </p>
                {turn.error ? (
                  <div className="ws-state ws-state--error" role="alert">
                    <p>{turn.error}</p>
                  </div>
                ) : turn.result ? (
                  <>
                    {turn.versionNumber !== null && turn.versionNumber !== versionNumber ? (
                      <p className="ws-dock__turn-version">
                        Answered about Version {turn.versionNumber}, not the version open now.
                      </p>
                    ) : null}
                    <WsAnswerView
                      result={turn.result}
                      openVersionNumber={versionNumber}
                      onOpenVersion={onOpenVersion}
                    />
                  </>
                ) : null}
              </li>
            ))}
            {pending !== null ? (
              <li className="ws-ask__turn" data-pending="true">
                <p className="ws-ask__q">
                  <span className="ws-ask__role">You</span> {pending}
                </p>
                <div className="ws-ask__answer" aria-busy="true">
                  <p className="ws-pane__note" role="status" aria-live="polite">
                    Searching the document and checking citations…
                  </p>
                  <span className="ws-skel ws-skel--line" style={{ width: "88%" }} aria-hidden="true" />
                  <span className="ws-skel ws-skel--line" style={{ width: "64%" }} aria-hidden="true" />
                </div>
              </li>
            ) : null}
          </ol>
          {turns.length === 0 && pending === null ? (
            restoring ? (
              <p className="ws-ask__empty" aria-busy="true">
                Reopening your questions about this document…
              </p>
            ) : (
              <div className="ws-dock__empty">
                <p className="ws-ask__empty">
                  Ask what this document says about something. Every answer points at
                  the passage it came from — or says plainly that the document does not
                  answer it.
                </p>
                <div className="ws-dock__chips" role="group" aria-label="Ask suggestions">
                  {SUGGESTED_QUESTIONS.map((suggested) => (
                    <button
                      key={suggested}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setQuestion(suggested);
                        inputRef.current?.focus();
                      }}
                    >
                      {suggested}
                    </button>
                  ))}
                </div>
              </div>
            )
          ) : null}
        </div>

        <form
          className="ws-dock__form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <label className="ws-visually-hidden" htmlFor="ws-ask-question">
            Your question about this document
          </label>
          <input
            id="ws-ask-question"
            ref={inputRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            placeholder="Ask about this document…"
            disabled={busy}
          />
          <button
            className="ws-dock__send"
            type="submit"
            aria-label={busy ? "Searching…" : "Send question"}
            disabled={busy || !question.trim()}
          >
            <IconSend />
          </button>
        </form>
        <p className="ws-dock__note">
          AI answers cite the document, or say they cannot. Verify with the original
          document.
        </p>
      </section>
    </div>
  );
}

/** Prefill chips — editable drafts, exactly like a finding's "Ask about this":
 *  nothing sends until the user sends it. Document-factual questions only. */
const SUGGESTED_QUESTIONS = [
  "What is the termination notice period?",
  "Summarize the payment terms",
  "What are each party's confidentiality obligations?",
  "How can this agreement be renewed or ended?",
];

/** Exported for the static test suite, the `AnswerView` precedent. */
export function WsAnswerView({
  result,
  openVersionNumber,
  onOpenVersion,
}: {
  result: AskResult;
  /** The version the document pane is showing, if the caller knows it. */
  openVersionNumber?: number | undefined;
  onOpenVersion?: ((documentVersionId: string) => void) | undefined;
}) {
  const { point, target } = useHighlight();

  if (result.routed_to_evaluator) {
    return (
      <div className="ws-ask__answer ws-ask__answer--routed" data-state={result.answer_state}>
        <p className="ws-ask__routed-label">Not answered here</p>
        <p>{result.text}</p>
      </div>
    );
  }
  if (result.answer_state !== "ANSWERED") {
    // A refusal is the system working, not failing: quiet, factual, no error tint.
    return (
      <div className="ws-ask__answer ws-ask__answer--refusal" data-state={result.answer_state}>
        <p>{result.text}</p>
      </div>
    );
  }

  /* An evidence row belongs to exactly one version's reading order, so a citation
   * from another version CANNOT be highlighted on the open page. Pointing at it
   * anyway is what the highlight gesture used to do: nothing moved, and the
   * aria-live region announced that something had. Offer the honest action —
   * open the version the answer actually read — instead. */
  const elsewhere =
    openVersionNumber !== undefined &&
    result.version_number > 0 &&
    result.version_number !== openVersionNumber;

  return (
    <div className="ws-ask__answer" data-state="ANSWERED">
      <p className="ws-ask__text">{result.text}</p>
      {result.citations.length > 0 ? (
        <ol className="ws-ask__citations">
          {result.citations.map((citation, index) => (
            <li key={citation.chunk_id} className="ws-ask__citation">
              {elsewhere ? (
                <button
                  type="button"
                  className="ws-ask__cite"
                  onClick={() => onOpenVersion?.(result.document_version_id)}
                  disabled={!onOpenVersion}
                  data-evidence-id={citation.evidence_id}
                  data-other-version={result.version_number}
                >
                  <span className="ws-mono">[{index + 1}]</span>{" "}
                  {sectionRef(citation.section_ref) ?? "passage"}
                  {citation.page_number != null ? ` · p.${citation.page_number}` : ""}
                  {" — open Version "}
                  {result.version_number}
                </button>
              ) : (
                <button
                  type="button"
                  className="ws-ask__cite"
                  aria-current={target === citation.evidence_id ? "true" : undefined}
                  onClick={() => point(citation.evidence_id, `citation ${index + 1}`)}
                  data-evidence-id={citation.evidence_id}
                >
                  <span className="ws-mono">[{index + 1}]</span>{" "}
                  {sectionRef(citation.section_ref) ?? "passage"}
                  {citation.page_number != null ? ` · p.${citation.page_number}` : ""}
                </button>
              )}
              <blockquote className="ws-ask__excerpt">{citation.excerpt}</blockquote>
              {citation.retrieval_score != null ? (
                <span className="ws-ask__score ws-mono">retrieval score {citation.retrieval_score.toFixed(3)}</span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

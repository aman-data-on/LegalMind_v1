"use client";

/**
 * Ask about this document — the Inquiry register, now a sticky bar (owner
 * brief, 2026-08-31): the input is mounted and reachable at EVERY breakpoint
 * and every scroll position, below the workspace grid, never behind a tab. The
 * turn history lives in a panel that slides up over the bar on demand and
 * expands automatically when an answer is coming.
 *
 * Everything about the CONTENT is unchanged from the former AskPane:
 *
 *   ANSWERED            prose + numbered citations; each citation POINTS at its
 *                       evidence row through the slice-1 highlight gesture
 *   a refusal           the identical sentence whatever the cause (`AM-29` r4),
 *                       on the quiet surface — the system working, not failing
 *   routed_to_evaluator a compliance-shaped question is a pointer to the
 *                       Findings pane, a third type, not an answer or a refusal
 *
 * The conversation is durable: on mount the bar reopens this contract's most
 * recent conversation — the server keeps citations across reloads. A finding's
 * "Ask about this" arrives as an EDITABLE draft (askIntent): placed in the
 * always-visible input and focused, never auto-sent — no tab switching needed
 * any more, because the input cannot be hidden.
 *
 * When an OLDER version is open the bar stays visible but disabled, saying so
 * plainly (never hidden, never silently misdirecting to the wrong version).
 * One honest status line while a request is in flight (decision #180); scores
 * are retrieval scores, labelled as exactly that (`AI-03` item 16, rule 12).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { ApiError, api, describeError } from "@/lib/api";
import type { AskResult, ConversationTurn } from "@/lib/types";

import { useAskIntent } from "./askIntent";
import { useHighlight } from "./highlight";
import { IconHistory, IconSend, IconSparkle } from "./icons";

interface Turn {
  question: string;
  result: AskResult | null;
  error: string | null;
}

/** A replayed turn pair from `GET /conversations/{id}` in the live bar's shape. */
function turnsFromHistory(messages: ConversationTurn[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role === "USER") {
      turns.push({ question: message.content, result: null, error: null });
    } else {
      const last = turns[turns.length - 1];
      if (!last) continue;
      last.result = {
        conversation_id: "",
        message_id: message.id,
        answer_state: message.answer_state ?? "ANSWERED",
        text: message.content,
        routed_to_evaluator: message.routed_to_evaluator,
        citations: message.citations,
      };
    }
  }
  return turns;
}

export function AskBar({
  contractId,
  notLatestVersion,
  onOpenLatest,
}: {
  contractId: string;
  /** The open version is not the newest — Ask answers about the latest only. */
  notLatestVersion?: number | undefined;
  onOpenLatest?: (() => void) | undefined;
}) {
  const askIntent = useAskIntent();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [restoring, setRestoring] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const conversationRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const busy = pending !== null;
  const disabled = notLatestVersion !== undefined;

  // Reopen this contract's most recent conversation, citations intact.
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

  // A finding's handoff: place the draft, focus the input, send nothing. The
  // input is always mounted, so this needs no tab or panel gymnastics.
  const consumedSeq = useRef(0);
  useEffect(() => {
    const draft = askIntent?.draft;
    if (!draft || draft.seq === consumedSeq.current) return;
    consumedSeq.current = draft.seq;
    setQuestion(draft.text);
    inputRef.current?.focus();
  }, [askIntent?.draft]);

  // The newest turn should be visible when the panel is open or opening.
  useEffect(() => {
    if (!open) return;
    const node = panelRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [open, turns.length, pending]);

  const submit = useCallback(async () => {
    const asked = question.trim();
    if (!asked || busy || disabled) return;
    setPending(asked);
    setQuestion("");
    setOpen(true); // the answer must land somewhere the user can see
    try {
      if (!conversationRef.current) {
        const conversation = await api.createConversation(contractId);
        conversationRef.current = conversation.id;
      }
      const result = await api.ask(conversationRef.current, asked);
      setTurns((previous) => [...previous, { question: asked, result, error: null }]);
    } catch (error) {
      const message = error instanceof ApiError ? describeError(error) : "The question could not be sent.";
      setTurns((previous) => [...previous, { question: asked, result: null, error: message }]);
    } finally {
      setPending(null);
    }
  }, [busy, contractId, disabled, question]);

  return (
    <aside className="ws-askbar" aria-label="Ask about this document">
      <div className="ws-askbar__card">
        <div
          className="ws-askbar__panel"
          data-open={open}
          ref={panelRef}
          // Content stays in the tree (state never lost), hidden from readers
          // and tab order while collapsed.
          aria-hidden={!open}
          inert={!open}
        >
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
                  <WsAnswerView result={turn.result} />
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
              <p className="ws-ask__empty">
                Ask what this document says about something. Every answer points at the
                passage it came from — or says plainly that the document does not answer it.
              </p>
            )
          ) : null}
        </div>
        <form
          className="ws-askbar__row"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <span className="ws-askbar__spark" aria-hidden="true">
            <IconSparkle size={18} />
          </span>
          <label className="ws-visually-hidden" htmlFor="ws-ask-question">
            Question
          </label>
          <input
            id="ws-ask-question"
            ref={inputRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            placeholder={
              disabled
                ? `Ask answers about the latest version — you are reading v${notLatestVersion}`
                : "Ask LegalMind anything about this document…"
            }
            disabled={busy || disabled}
          />
          {disabled && onOpenLatest ? (
            <button type="button" className="ws-btn" onClick={onOpenLatest}>
              Open the latest version
            </button>
          ) : (
            <button
              className="ws-askbar__send"
              type="submit"
              aria-label={busy ? "Searching…" : "Ask"}
              disabled={busy || disabled || !question.trim()}
            >
              <IconSend />
            </button>
          )}
          <button
            type="button"
            className="ws-askbar__toggle"
            aria-expanded={open}
            aria-label={open ? "Hide conversation" : `Show conversation${turns.length ? ` (${turns.length} turns)` : ""}`}
            onClick={() => setOpen((wasOpen) => !wasOpen)}
          >
            <IconHistory />
            {turns.length > 0 ? <span className="ws-mono">{turns.length}</span> : null}
          </button>
        </form>
        {!disabled ? (
          <div className="ws-askbar__chips" role="group" aria-label="Ask suggestions">
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
        ) : null}
      </div>
      <p className="ws-askbar__note">
        AI answers cite the document, or say they cannot. Verify with the original document.
      </p>
    </aside>
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
export function WsAnswerView({ result }: { result: AskResult }) {
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
  return (
    <div className="ws-ask__answer" data-state="ANSWERED">
      <p className="ws-ask__text">{result.text}</p>
      {result.citations.length > 0 ? (
        <ol className="ws-ask__citations">
          {result.citations.map((citation, index) => (
            <li key={citation.chunk_id} className="ws-ask__citation">
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

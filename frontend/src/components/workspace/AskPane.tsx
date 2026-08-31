"use client";

/**
 * Ask about this document — the Inquiry register (UI_UX_MASTER_PROMPT §4.1/§5).
 * Slice 3 of PRODUCT_UX_ROADMAP §G.
 *
 * Deliberately colorless: no state-axis hue appears here, so a cited answer can
 * never be mistaken for a verdict. Three message shapes, from the server's own
 * vocabulary (`AM-29`), never re-derived:
 *
 *   ANSWERED            prose + numbered citations; each citation POINTS at its
 *                       evidence row through the slice-1 highlight gesture
 *   a refusal           the identical sentence whatever the cause (`AM-29` r4),
 *                       on the quiet surface — the system working, not failing
 *   routed_to_evaluator a compliance-shaped question is a pointer to the
 *                       Findings pane, a third type, not an answer or a refusal
 *
 * The conversation is durable (2026-08-31): on mount the pane reopens this
 * contract's most recent conversation — the server keeps citations across
 * reloads (the 2026-08-26 backend addition) — so leaving and returning to the
 * workspace no longer silently starts a fresh thread.
 *
 * A finding's "Ask about this" arrives here as an EDITABLE draft (askIntent):
 * placed in the input and focused, never auto-sent.
 *
 * While a request is in flight there is ONE honest status line — the client
 * sees a single request, so a staged "searching → verifying" theater with
 * invented timings would claim progress knowledge it does not have (decision
 * #180). Scores are retrieval scores, labelled as exactly that, never rendered
 * as a bar or colour (`AI-03` item 16, rule 12).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import type { AskResult, ConversationTurn } from "@/lib/types";

import { useAskIntent } from "./askIntent";
import { useHighlight } from "./highlight";

interface Turn {
  question: string;
  result: AskResult | null;
  error: string | null;
}

/** A replayed turn pair from `GET /conversations/{id}` in the live pane's shape. */
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

export function AskPane({ contractId }: { contractId: string }) {
  const askIntent = useAskIntent();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [restoring, setRestoring] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const conversationRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = pending !== null;

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

  // A finding's handoff: place the draft, focus the input, send nothing.
  const consumedSeq = useRef(0);
  useEffect(() => {
    const draft = askIntent?.draft;
    if (!draft || draft.seq === consumedSeq.current) return;
    consumedSeq.current = draft.seq;
    setQuestion(draft.text);
    inputRef.current?.focus();
  }, [askIntent?.draft]);

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
      const result = await api.ask(conversationRef.current, asked);
      setTurns((previous) => [...previous, { question: asked, result, error: null }]);
    } catch (error) {
      const message = error instanceof ApiError ? describeError(error) : "The question could not be sent.";
      setTurns((previous) => [...previous, { question: asked, result: null, error: message }]);
    } finally {
      setPending(null);
    }
  }, [busy, contractId, question]);

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Ask</h2>
        <span className="ws-pane__note">Answers cite the document, or say they cannot.</span>
      </div>
      <div className="ws-pane__body ws-ask">
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
        className="ws-ask__form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="ws-visually-hidden" htmlFor="ws-ask-question">
          Question
        </label>
        <input
          id="ws-ask-question"
          ref={inputRef}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={2000}
          placeholder="What does this document say about…"
          disabled={busy}
        />
        <button className="ws-btn ws-btn--primary" type="submit" disabled={busy || !question.trim()}>
          {busy ? "Searching…" : "Ask"}
        </button>
      </form>
    </>
  );
}

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
                {citation.section_ref ? `§${citation.section_ref}` : "passage"}
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

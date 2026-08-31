"use client";

/**
 * Ask about this document — the assist lane's conversational surface (AB-3/AB-4).
 *
 * Three rules from the locked records shape everything rendered here.
 *
 * **A refusal is a first-class outcome, not an error state** (`AM-29`). The system
 * saying "not found" is it working correctly, so the refusal renders calmly in the
 * conversation flow — never as a red failure banner.
 *
 * **Scores are retrieval scores, labeled as exactly that** (`AI-03` item 16, rule 12).
 * There is no "confidence" figure anywhere on this surface, and no percentage sits
 * next to a legal statement.
 *
 * **This panel never judges** (`AM-25` r1/r4). It renders answers about what the
 * document says; whether the document is acceptable belongs to the Review screen, and
 * a question of that shape comes back routed there by the server.
 */

import { useCallback, useRef, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { SkeletonAnswer } from "@/components/Skeleton";
import { api, describeError } from "@/lib/api";
import type { AskResult } from "@/lib/types";

interface Turn {
  question: string;
  result: AskResult | null;
  error: string | null;
}

export function AskPanel({ contractId }: { contractId: string }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  /* The in-flight question, rendered as a pending turn with an answer-shaped
     skeleton. One honest status line — the client sees a single request, so a
     staged "searching → verifying" theater with invented timings would claim
     knowledge of pipeline progress it does not have. */
  const [pending, setPending] = useState<string | null>(null);
  const busy = pending !== null;
  const conversationRef = useRef<string | null>(null);

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
      setTurns((previous) => [
        ...previous,
        { question: asked, result: null, error: describeError(error) },
      ]);
    } finally {
      setPending(null);
    }
  }, [busy, contractId, question]);

  return (
    <section aria-labelledby="ask-heading">
      <h2 id="ask-heading">Ask about this document</h2>
      <p className="hint">
        Answers come only from the uploaded document and always cite their source.
        Whether the document meets company standards is decided by a Review, not here.
      </p>

      <ol className="ask-turns" aria-live="polite">
        {turns.map((turn, index) => (
          <li key={index} className="ask-turn">
            <p className="ask-question">
              <span className="ask-role">You</span> {turn.question}
            </p>
            {turn.error ? (
              <ErrorBanner error={turn.error} />
            ) : turn.result ? (
              <AnswerView result={turn.result} />
            ) : null}
          </li>
        ))}
        {pending !== null ? (
          <li className="ask-turn" data-pending="true">
            <p className="ask-question">
              <span className="ask-role">You</span> {pending}
            </p>
            <SkeletonAnswer />
          </li>
        ) : null}
      </ol>

      <form
        className="ask-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="field">
          <span className="field-label">Question</span>
          <input
            className="field-input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            placeholder="What does this document say about…"
            disabled={busy}
          />
        </label>
        <button className="btn btn--primary" type="submit" disabled={busy || !question.trim()}>
          {busy ? "Searching…" : "Ask"}
        </button>
      </form>
    </section>
  );
}

export function AnswerView({ result }: { result: AskResult }) {
  if (result.routed_to_evaluator) {
    return (
      <div className="ask-answer ask-answer--routed" data-state={result.answer_state}>
        <p>{result.text}</p>
      </div>
    );
  }
  if (result.answer_state !== "ANSWERED") {
    // A refusal is the system working, not failing: quiet, factual, no error tint.
    return (
      <div className="ask-answer ask-answer--refusal" data-state={result.answer_state}>
        <p>{result.text}</p>
      </div>
    );
  }
  return (
    <div className="ask-answer" data-state="ANSWERED">
      <p className="ask-text">{result.text}</p>
      {result.citations.length > 0 ? (
        <ul className="ask-citations">
          {result.citations.map((citation) => (
            <li key={citation.chunk_id} className="ask-citation">
              <span className="ask-citation-ref">
                {citation.section_ref ? `§${citation.section_ref}` : "—"}
                {citation.page_number != null ? ` · p.${citation.page_number}` : ""}
              </span>
              <blockquote className="ask-citation-excerpt">{citation.excerpt}</blockquote>
              {citation.retrieval_score != null ? (
                <span className="ask-citation-score">
                  retrieval score {citation.retrieval_score.toFixed(3)}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

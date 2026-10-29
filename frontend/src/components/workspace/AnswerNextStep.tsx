"use client";

/**
 * One way forward under the last answer when it is not an answer (Ask audit, 2026-10-29:
 * 5 of 44 production replies were dead ends, and the reader retyped the question each
 * time). Nothing here decides anything: it resends the reader's own question, or sends
 * the brand they tap.
 */
import type { ConversationTurn } from "@/lib/types";

/** The server's fixed brand question (`agent.BRAND_QUESTION`) opens with these words; a
 *  backend test pins the same opening, as the server's own reply detection does. */
export const BRAND_QUESTION_START = "Before I answer: is this for CloudPe or Leapswitch?";

/** A reply the model never wrote — timed out, unreachable or paused — after a real wait:
 *  the meta line reads "No AI-written answer · N s". A fixed "not found" has no wait,
 *  and a reviewed file or the assistant's questions carry a payload. */
export function isDeadEnd(turn: ConversationTurn): boolean {
  return turn.role === "ASSISTANT" && turn.answer_state !== "ANSWERED"
    && !turn.routed_to_evaluator && !turn.answered_by && turn.latency_ms != null
    && !(turn.payload && "kind" in turn.payload);
}

/** A fixed "not found" reply: nothing was timed and no model wrote it. */
export function isNotFound(turn: ConversationTurn): boolean {
  return turn.role === "ASSISTANT" && turn.answer_state === "NO_EVIDENCE_RETRIEVED"
    && !turn.routed_to_evaluator && turn.latency_ms == null;
}

export function AnswerNextStep({ turn, question, switchTo, onAsk, onSwitchAndAsk, onAttach, onEdit }: {
  turn: ConversationTurn;
  /** The reader's question this reply answered, resent as it was. */
  question: string | undefined;
  /** A model that can answer, when the chosen one is paused. */
  switchTo: { id: string; label: string } | null;
  onAsk: (text: string) => void;
  onSwitchAndAsk: (modelId: string, text: string) => void;
  /** Open the file picker, so the document the question is about can be attached. */
  onAttach?: (() => void) | undefined;
  /** Put the question back in the box to be reworded. */
  onEdit?: ((text: string) => void) | undefined;
}) {
  if (turn.content.startsWith(BRAND_QUESTION_START)) {
    return (
      <div className="ws-next" role="group" aria-label="Which brand?">
        {["Leapswitch", "CloudPe"].map((brand) => (
          <button key={brand} type="button" className="ws-btn ws-btn--sm" onClick={() => onAsk(brand)}>
            {brand}
          </button>
        ))}
      </div>
    );
  }
  if (question && isNotFound(turn) && (onAttach || onEdit)) {
    // Ask audit M4: two ways forward that need no model — the document, or other words
    return (
      <div className="ws-next">
        {onAttach ? <button type="button" className="ws-btn ws-btn--sm" onClick={onAttach}>Attach the document</button> : null}
        {onEdit ? <button type="button" className="ws-btn ws-btn--sm" onClick={() => onEdit(question)}>Reword the question</button> : null}
      </div>
    );
  }
  if (!question || !isDeadEnd(turn)) return null;
  return (
    <div className="ws-next">
      {switchTo ? (
        <button type="button" className="ws-btn ws-btn--sm ws-btn--primary"
                onClick={() => onSwitchAndAsk(switchTo.id, question)}>
          Ask with {switchTo.label}
        </button>
      ) : (
        <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => onAsk(question)}>
          Ask again
        </button>
      )}
    </div>
  );
}

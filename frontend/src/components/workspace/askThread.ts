/**
 * The conversation logic both chat surfaces share — the Ask page and the document page's
 * Ask — over the one assistant-ui thread (`components/ui/thread.tsx`). Each surface keeps
 * only what is its own: where a question is sent and what happens around it.
 */
import {
  type AppendMessage,
  type AssistantRuntime,
  type ThreadMessageLike,
  useExternalStoreRuntime,
} from "@assistant-ui/react";
import { type KeyboardEvent as ReactKeyboardEvent, type RefObject, useEffect, useRef } from "react";

import type { AskResult, ConversationSummary, ConversationTurn } from "@/lib/types";

/** A chat's name: the reader's own for it, else the first thing they actually asked. */
export function chatTitle(conversation: ConversationSummary): string {
  return conversation.title?.trim() || conversation.first_question?.trim() || "New chat";
}

/** Stopping is the reader's choice, a timeout is not; the two are said differently. */
export const STOPPED = "stopped";

/** Why the wait ended, for an aborted ask. A stop ends the wait here only: the server
 *  may still finish the answer and keep it in the chat. */
export function waitEnded(reason: unknown): string {
  return reason === STOPPED ? "Stopped. Your question is kept — try again."
    : "The answer took too long to arrive. Your question is kept — try again.";
}

/** Enter that commits an IME composition (Devanagari, Japanese, Chinese input) chooses
 *  the composed word; it is not a send. Safari reports it only as keyCode 229. */
export function isImeEnter(event: { nativeEvent: KeyboardEvent; keyCode: number }): boolean {
  return event.nativeEvent.isComposing || event.keyCode === 229;
}

/** Enter sends, Shift+Enter breaks the line — the composer convention. A textarea is what
 *  lets a long question be read back before it is sent. Enter inside an IME composition
 *  picks the composed word and sends nothing. */
export function enterSends(runtime: AssistantRuntime) {
  return (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !isImeEnter(event)) {
      event.preventDefault();
      runtime.thread.composer.send();
    }
  };
}

/** The reader's question in the recorded turn's shape — shown while it is answered,
 *  and kept beside the answer once it arrives. */
export function askedTurn(id: string, question: string): ConversationTurn {
  return {
    id,
    ordinal: -1,
    role: "USER",
    content: question,
    answer_state: null,
    routed_to_evaluator: false,
    document_version_id: null,
    version_number: null,
    citations: [],
  };
}

/** A live answer in the recorded turn's shape, so ONE renderer draws both — the
 *  replayed transcript and the answer that has just arrived. */
export function liveTurns(question: string, result: AskResult): ConversationTurn[] {
  return [
    // The question's own id when the server names it, so it can be edited (`AM-134`).
    askedTurn(result.question_message_id ?? `${result.message_id}-q`, question),
    {
      id: result.message_id,
      ordinal: 0,
      role: "ASSISTANT",
      content: result.text,
      answer_state: result.answer_state,
      routed_to_evaluator: result.routed_to_evaluator,
      document_version_id: result.document_version_id,
      version_number: result.version_number,
      citations: result.citations,
      positions: result.positions ?? [],
      statutes: result.statutes ?? null,
      exact_text_requested: result.exact_text_requested ?? false,
      quote_is_the_answer: result.quote_is_the_answer ?? false,
      comparison: result.comparison ?? null,
      sources: result.sources ?? [],
      answered_by: result.answered_by ?? null,
      latency_ms: result.latency_ms ?? null,
    },
  ];
}

/** An answer turn as the answer it was — for a renderer that takes the live shape. */
export function answerOf(turn: ConversationTurn): AskResult {
  return {
    conversation_id: "",
    message_id: turn.id,
    answer_state: turn.answer_state ?? "ANSWERED",
    text: turn.content,
    routed_to_evaluator: turn.routed_to_evaluator,
    document_version_id: turn.document_version_id ?? null,
    version_number: turn.version_number ?? null,
    citations: turn.citations,
    positions: turn.positions ?? [],
    statutes: turn.statutes ?? null,
    exact_text_requested: turn.exact_text_requested ?? false,
    quote_is_the_answer: turn.quote_is_the_answer ?? false,
    comparison: turn.comparison ?? null,
    sources: turn.sources ?? [],
    answered_by: turn.answered_by ?? null,
    latency_ms: turn.latency_ms ?? null,
  };
}

/** The turns shown before an edited question: the edit replaces it and all after it. */
export function before(turns: ConversationTurn[], editOf: string | undefined): ConversationTurn[] {
  const at = editOf ? turns.findIndex((turn) => turn.id === editOf) : -1;
  return at < 0 ? turns : turns.slice(0, at);
}

/** The turn travels whole in `metadata.custom`: the thread renders it with the surface's
 *  own renderer, so citations, sources and routed Findings are drawn by the code that
 *  already enforces their rules — assistant-ui only places and scrolls. */
function toThreadMessage(turn: ConversationTurn): ThreadMessageLike {
  return {
    id: turn.id,
    role: turn.role === "USER" ? "user" : "assistant",
    content: turn.content,
    metadata: { custom: { turn } },
  };
}

function messageText(message: AppendMessage): string {
  return message.content.map((part) => (part.type === "text" ? part.text : "")).join("");
}

/** What a screen reader hears when an answer arrives. */
export function arrived(result: AskResult): string {
  return result.answer_state === "ANSWERED"
    ? "LegalMind answered."
    : "LegalMind could not answer this from the approved material.";
}

/** Sending is disabled while an answer is found, which drops focus to the page; once
 *  it is enabled again (after that render — a disabled control cannot take focus) the
 *  box gets it back, unless the reader moved on. */
export function useFocusAfterAnswer(busy: boolean, inputRef: RefObject<HTMLTextAreaElement | null>) {
  const wasBusy = useRef(false);
  useEffect(() => {
    if (wasBusy.current && !busy && (document.activeElement === document.body
                                     || document.activeElement === null)) {
      inputRef.current?.focus();
    }
    wasBusy.current = busy;
  }, [busy, inputRef]);
}

/** A question being answered, as the thread shows it. */
export interface Pending {
  text: string;
  /** An edit (`AM-134`): the turns from this question on are replaced. */
  editOf?: string | undefined;
}

/** assistant-ui over the state a surface already keeps: its turns are the messages, and
 *  the question being answered is the reader's turn until its answer replaces it — after
 *  the turns an edit keeps. No answer is streamed: nothing reaches the reader before it is
 *  verified (`AM-25` r5, `AM-69`), so a run is one request and the thread shows progress,
 *  not tokens. */
export function useAskRuntime({ turns, pending, busy, send, stop }: {
  turns: ConversationTurn[];
  /** The question answered in THIS view, or null. */
  pending: Pending | null;
  /** One answer at a time, from any view: the box stays editable, only sending waits. */
  busy: boolean;
  send: (text: string, editOf?: string) => Promise<void>;
  stop: () => void;
}): AssistantRuntime {
  return useExternalStoreRuntime({
    messages: pending === null ? turns
      : [...before(turns, pending.editOf), askedTurn("pending", pending.text)],
    convertMessage: toThreadMessage,
    isRunning: pending !== null,
    isSendDisabled: busy,
    onNew: (message: AppendMessage) => send(messageText(message)),
    onEdit: (message: AppendMessage) => send(messageText(message), message.sourceId ?? undefined),
    onCancel: async () => stop(),
  });
}

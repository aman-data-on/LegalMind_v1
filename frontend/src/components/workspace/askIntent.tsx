"use client";

/**
 * Finding → Ask handoff (owner directive 2026-08-31 §17): "Ask about this"
 * on a finding pre-fills the Ask input with an editable, document-shaped
 * question — nothing is sent until the user sends it, so the user always sees
 * exactly what is asked.
 *
 * The draft carries a sequence number so the same text can be requested twice,
 * and so the collapsed-layout tabs can switch to the Ask region when a draft
 * arrives (a prefill into an invisible pane would be a silent no-op).
 *
 * `findingId` (2026-09-11) — WHAT IT IS AND WHAT IT IS NOT. It is a RETRIEVAL
 * hint: the server seeds its search with that Finding's requirement and the
 * clause its Evaluation already cited, so "why is this a deviation?" — a
 * question with almost no retrievable content of its own — finds the provision
 * the reader is looking at instead of nothing.
 *
 * It is NOT hidden context in the old sense this file used to warn about. No
 * classification, Rule Outcome or Company Standard value travels, and none may:
 * `AM-30` t3 and `AM-32` r4 are unchanged, and a backend test asserts the seed
 * carries none of them. The user still sees exactly the question that is asked;
 * the id only tells the index where to look.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";

export interface AskDraft {
  text: string;
  seq: number;
  /** The Finding this draft came from, when it came from one. */
  findingId?: string;
}

interface AskIntentState {
  draft: AskDraft | null;
  ask: (text: string, findingId?: string) => void;
}

const Ctx = createContext<AskIntentState | null>(null);

/** The draft, as a pure function of the previous one — extracted so the rule that
 *  matters can be asserted without a render pass: a draft with no Finding behind it
 *  OMITS `findingId` rather than carrying an empty slot to the API. */
export function nextDraft(previous: AskDraft | null, text: string,
                          findingId?: string): AskDraft {
  return { text, seq: (previous?.seq ?? 0) + 1,
           ...(findingId ? { findingId } : {}) };
}

export function AskIntentProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<AskDraft | null>(null);
  const ask = useCallback((text: string, findingId?: string) => {
    setDraft((previous) => nextDraft(previous, text, findingId));
  }, []);
  const value = useMemo(() => ({ draft, ask }), [draft, ask]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Null outside the provider — surfaces that can live without it (the Ask
 *  history replay) simply render no handoff control. */
export function useAskIntent(): AskIntentState | null {
  return useContext(Ctx);
}

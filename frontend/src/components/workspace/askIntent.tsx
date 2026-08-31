"use client";

/**
 * Finding → Ask handoff (owner directive 2026-08-31 §17): "Ask about this"
 * on a finding pre-fills the Ask input with an editable, document-shaped
 * question — nothing is sent until the user sends it, so the user always sees
 * exactly what is asked (no hidden context is injected into the assist lane,
 * whose scope stays the document text — AM-25).
 *
 * The draft carries a sequence number so the same text can be requested twice,
 * and so the collapsed-layout tabs can switch to the Ask region when a draft
 * arrives (a prefill into an invisible pane would be a silent no-op).
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";

export interface AskDraft {
  text: string;
  seq: number;
}

interface AskIntentState {
  draft: AskDraft | null;
  ask: (text: string) => void;
}

const Ctx = createContext<AskIntentState | null>(null);

export function AskIntentProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<AskDraft | null>(null);
  const ask = useCallback((text: string) => {
    setDraft((previous) => ({ text, seq: (previous?.seq ?? 0) + 1 }));
  }, []);
  const value = useMemo(() => ({ draft, ask }), [draft, ask]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Null outside the provider — surfaces that can live without it (the Ask
 *  history replay) simply render no handoff control. */
export function useAskIntent(): AskIntentState | null {
  return useContext(Ctx);
}

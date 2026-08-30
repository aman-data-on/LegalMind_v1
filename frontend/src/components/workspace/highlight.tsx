"use client";

/**
 * The cross-pane highlight — the workspace's signature gesture (WORKSPACE_UI_PLAN,
 * PRODUCT_UX_ROADMAP §A): a verdict, a citation, an outline entry or a shared link
 * all say the same thing — "point at this evidence row" — and the document pane
 * answers by scrolling to it, lighting it, and moving focus so a keyboard or
 * screen-reader user arrives there too.
 *
 * The target is an evidence row id: the unit every source in the system already
 * shares (a Finding's `evidence_refs`, a citation's chunk → evidence row, the
 * `/evidence` endpoint's rows). Deep-linkable as `?evidence=<id>` so a citation can
 * be handed to a colleague as a URL and land on the exact clause.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export const EVIDENCE_PARAM = "evidence";

interface HighlightState {
  target: string | null;
  /** Point at an evidence row. `source` is for the aria-live announcement only. */
  point: (evidenceId: string | null, source?: string) => void;
  announcement: string;
}

const Ctx = createContext<HighlightState | null>(null);

export function HighlightProvider({ children }: { children: React.ReactNode }) {
  const [target, setTarget] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  // The URL is the durable form of "what am I pointing at".
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get(EVIDENCE_PARAM);
    if (fromUrl) setTarget(fromUrl);
  }, []);

  const point = useCallback((evidenceId: string | null, source?: string) => {
    setTarget(evidenceId);
    const url = new URL(window.location.href);
    if (evidenceId) url.searchParams.set(EVIDENCE_PARAM, evidenceId);
    else url.searchParams.delete(EVIDENCE_PARAM);
    window.history.replaceState(null, "", url);
    setAnnouncement(evidenceId ? `Showing ${source ?? "the selected"} evidence in the document` : "");
  }, []);

  const value = useMemo(() => ({ target, point, announcement }), [target, point, announcement]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useHighlight(): HighlightState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useHighlight must be used inside HighlightProvider");
  return value;
}

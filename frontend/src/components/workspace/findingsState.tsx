"use client";

/**
 * One findings state machine for the whole workspace (2026-08-31 3-column
 * redesign). The findings pane, the document outline's status dots and the
 * Analysis panel all read THIS state — one fetch, one poll loop, so three
 * views can never disagree about what the analysis found.
 *
 * Extracted verbatim from FindingsPane's former internal state: progress is
 * the Review lifecycle and nothing else (52.7), polling is bounded and silent,
 * and every state is an honest shape the consumers render in their own words.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { DocumentVersion, Finding, Review } from "@/lib/types";

export type FindingsLoad =
  | { kind: "loading" }
  | { kind: "no-review" }
  | { kind: "in-flight"; review: Review }
  | { kind: "failed"; review: Review }
  | { kind: "ready"; review: Review; findings: Finding[] }
  | { kind: "error"; error: unknown };

/** Review lifecycle states that mean "a result is still coming" (Step 30). */
const IN_FLIGHT_STATUSES = new Set(["DRAFT", "UPLOADED", "PROCESSING"]);
const POLL_MS = 2500;
const POLL_LIMIT = 120; // five minutes of patience, then the state stands as is

interface FindingsState {
  state: FindingsLoad;
  reload: () => void;
}

const Ctx = createContext<FindingsState | null>(null);

export function FindingsProvider({
  contractId,
  version,
  children,
}: {
  contractId: string;
  version: DocumentVersion;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<FindingsLoad>({ kind: "loading" });
  const polls = useRef(0);

  const load = useCallback(async (silent = false) => {
    if (!silent) setState({ kind: "loading" });
    try {
      const { items: reviews } = await api.reviews({ contract_id: contractId, page_size: 100 });
      const review = reviews.find((r) => r.document_version_id === version.id);
      if (!review) {
        setState({ kind: "no-review" });
        return;
      }
      if (IN_FLIGHT_STATUSES.has(review.status)) {
        setState({ kind: "in-flight", review });
        return;
      }
      if (review.status === "ANALYSIS_FAILED") {
        setState({ kind: "failed", review });
        return;
      }
      const { items: findings } = await api.findings(review.id, { page_size: 100 });
      setState({ kind: "ready", review, findings });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [contractId, version.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Progress is the Review lifecycle and nothing else (52.7): while it says a
  // result is coming, ask again quietly. Bounded, and silent so no consumer's
  // shape flickers mid-read.
  useEffect(() => {
    if (state.kind !== "in-flight") {
      polls.current = 0;
      return;
    }
    if (polls.current >= POLL_LIMIT) return;
    const timer = window.setTimeout(() => {
      polls.current += 1;
      void load(true);
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [state, load]);

  const reload = useCallback(() => {
    void load();
  }, [load]);

  const value = useMemo(() => ({ state, reload }), [state, reload]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFindingsState(): FindingsState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useFindingsState must be used inside FindingsProvider");
  return value;
}

/** Null outside the provider — for surfaces that can render without findings
 *  (the document pane opens on contracts with no analysis at all). */
export function useFindingsStateOptional(): FindingsState | null {
  return useContext(Ctx);
}

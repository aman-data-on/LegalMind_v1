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
import { mergeEquivalentFindings } from "./findingLanguage";

export type FindingsLoad =
  | { kind: "loading" }
  | { kind: "no-review" }
  /** A Review exists and analysis has NOT been submitted (Step 30 DRAFT/UPLOADED).
   *  Distinct from `in-flight` on purpose — see the note on the status sets. */
  | { kind: "not-started"; review: Review }
  | { kind: "in-flight"; review: Review }
  | { kind: "failed"; review: Review }
  | { kind: "ready"; review: Review; findings: Finding[] }
  | { kind: "error"; error: unknown };

/*
 * Step 30's pre-result states, split into the two things they actually mean —
 * 2026-09-04, found by porting the legacy analysis browser test.
 *
 * They used to be one set, all rendered as "Analysing against configuration
 * snapshot…" with a poll behind it. But DRAFT and UPLOADED mean nothing has been
 * submitted: the screen claimed work was running that was not, and offered no way
 * to start it — so a Review that stopped at DRAFT could never be analysed from
 * the new UI at all, while the legacy screen it replaced carried exactly that
 * control. Two states, two honest renderings: one offers the action, the other
 * reports real progress.
 */
const NOT_STARTED_STATUSES = new Set(["DRAFT", "UPLOADED"]);
const IN_FLIGHT_STATUSES = new Set(["PROCESSING"]);
const POLL_MS = 2500;
const POLL_LIMIT = 120; // five minutes of patience, then the state stands as is
/* A Review just submitted keeps its pre-analysis state until a worker picks the job
   up (`worker/dispatch.py`: the queue writes nothing first, and Step 30 has no QUEUED
   state). The page read the Review in that instant, saw "not started" and never asked
   again — the Summary appeared only on a manual refresh (owner, 2026-10-09: submitted
   11:51:04, worker done ~11:51:35, nothing fetched until the click at 11:51:40). So a
   "not started" Review is asked again too, for two minutes: long enough to see a
   queued job begin behind two running analyses (the worker runs two at a time, ~35 s each), short enough that a Review nobody submitted settles quietly. */
const NOT_STARTED_POLL_LIMIT = 48;

/** How many quiet re-reads a findings state earns: a result in flight, or one that
 *  may have just been queued, is asked again; a settled state is not. */
export function pollBudget(kind: FindingsLoad["kind"]): number {
  return kind === "in-flight" ? POLL_LIMIT : kind === "not-started" ? NOT_STARTED_POLL_LIMIT : 0;
}

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
      if (NOT_STARTED_STATUSES.has(review.status)) {
        setState({ kind: "not-started", review });
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
      /* Folded HERE, at the one load, rather than inside the pane: the pane, the
         Summary counts and the outline's status dots all read this state, and a
         list deduplicated for one of them but not the others is exactly how a
         count and a filter come to disagree. Nothing is discarded — a folded
         finding is carried on the one that survives. */
      setState({ kind: "ready", review, findings: mergeEquivalentFindings(findings) });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [contractId, version.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Progress is the Review lifecycle and nothing else (52.7): while it says a
  // result is coming — or may be about to (a just-queued job, above) — ask again
  // quietly. Bounded, and silent so no consumer's shape flickers mid-read.
  const polledKind = useRef<FindingsLoad["kind"] | null>(null);
  useEffect(() => {
    const limit = pollBudget(state.kind);
    if (polledKind.current !== state.kind) {
      polledKind.current = state.kind;
      polls.current = 0;
    }
    if (polls.current >= limit) return;
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

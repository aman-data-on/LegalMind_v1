"use client";

/**
 * One-click analysis for a version with no Review yet — the 2026-08-31 UX
 * correction's second half. "Analyze against the current standards" resolves
 * to the LATEST PUBLISHED configuration snapshot, which is named on screen
 * before and after the act: reproducibility stays visible (AUD-04), and the
 * engine still refuses an undeclared type or missing configuration exactly as
 * locked — this control adds reachability, never semantics.
 *
 * Honest blocked states instead of a dead end: no `review.create` → says so;
 * no published snapshot → names who unblocks it (Legal publishes
 * configuration); document still processing → says to wait.
 */

import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, SnapshotSummary } from "@/lib/types";
import { useFindingsStateOptional } from "./findingsState";

type State =
  | { kind: "loading" }
  | { kind: "no-snapshot" }
  | { kind: "ready"; snapshot: SnapshotSummary }
  | { kind: "running"; snapshot: SnapshotSummary }
  | { kind: "not-contract"; snapshot: SnapshotSummary; reviewId: string | null; busy: boolean }
  | { kind: "error"; error: unknown };

export function AnalyzeControl({
  version,
  onAnalysed,
}: {
  version: DocumentVersion;
  onAnalysed: () => void;
}) {
  const { can } = useSession();
  const [state, setState] = useState<State>({ kind: "loading" });
  const owner = useFindingsStateOptional()?.isOwner ?? true;
  const allowed = can(P.REVIEW_CREATE) && owner;
  const processed = version.processing_status === "COMPLETED";

  const load = useCallback(async () => {
    try {
      const snapshots = await api.snapshots({ page_size: 1 });
      const snapshot = snapshots.items[0];
      // AM-245: a refused paper says so on every load, before any Review is created
      const refused = version.paper_kind?.kind === "NOT_A_CONTRACT"
        && !version.paper_kind.reviewed_anyway;
      setState(!snapshot ? { kind: "no-snapshot" }
        : refused ? { kind: "not-contract", snapshot, reviewId: null, busy: false }
          : { kind: "ready", snapshot });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [version.paper_kind]);

  useEffect(() => {
    if (allowed && processed) void load();
  }, [allowed, processed, load]);

  if (!allowed) {
    return (
      <p className="ws-pane__note">
        {owner
          ? <>This version hasn&rsquo;t been analysed. Your account cannot start an analysis.</>
          : <>This version hasn&rsquo;t been analysed yet. Its owner starts the analysis.</>}
      </p>
    );
  }

  if (!processed) {
    return (
      <p className="ws-pane__note">
        The document is still being processed — analysis can start once it completes.
      </p>
    );
  }

  async function analyze(snapshot: SnapshotSummary) {
    setState({ kind: "running", snapshot });
    try {
      const review = await api.createReview(version.id, snapshot.id);
      const done = await api.analyzeReview(review.id);
      // AM-245: refused before anything ran — say so, never "analysing"
      if (done.not_a_contract) {
        setState({ kind: "not-contract", snapshot, reviewId: review.id, busy: false });
        return;
      }
      onAnalysed();
    } catch (error) {
      setState({ kind: "error", error });
    }
  }

  async function reviewAnyway(snapshot: SnapshotSummary, reviewId: string | null) {
    setState({ kind: "not-contract", snapshot, reviewId, busy: true });
    try {
      const id = reviewId ?? (await api.createReview(version.id, snapshot.id)).id;
      const done = await api.analyzeReview(id, undefined, true);
      if (done.not_a_contract) {    // refused again: never report an analysis that did not run
        setState({ kind: "not-contract", snapshot, reviewId, busy: false });
        return;
      }
      onAnalysed();
    } catch (error) {
      setState({ kind: "error", error });
    }
  }

  return (
    <div className="ws-analyze">
      {state.kind === "loading" ? (
        <p className="ws-pane__note" aria-busy="true">
          Checking the published standards…
        </p>
      ) : null}
      {state.kind === "no-snapshot" ? (
        <p className="ws-pane__note">
          This version hasn&rsquo;t been analysed. It runs once Legal publishes our standards.
        </p>
      ) : null}
      {state.kind === "ready" || state.kind === "running" ? (
        <>
          <p>This version hasn&rsquo;t been analysed yet.</p>
          <button
            type="button"
            className="ws-btn ws-btn--primary"
            disabled={state.kind === "running"}
            onClick={() => void analyze(state.snapshot)}
          >
            {state.kind === "running" ? "Analysing…" : "Analyze against current standards"}
          </button>
          <p className="ws-pane__note">Our standards, version <span className="ws-mono">{state.snapshot.id.slice(0, 8)}</span></p>
        </>
      ) : null}
      {state.kind === "not-contract" ? (
        <div className="ws-pane__note" role="status">
          <p>This doesn&rsquo;t look like a contract or one of our policies, so it was not
            reviewed against our positions.</p>
          <button
            type="button"
            className="ws-btn"
            disabled={state.busy}
            onClick={() => void reviewAnyway(state.snapshot, state.reviewId)}
          >
            {state.busy ? "Analysing…" : "Review anyway"}
          </button>
          <p>Choosing &ldquo;Review anyway&rdquo; is recorded with your name.</p>
        </div>
      ) : null}
      {state.kind === "error" ? (
        <div className="ws-state ws-state--error" role="alert">
          <p>{describeError(state.error)}</p>
        </div>
      ) : null}
    </div>
  );
}

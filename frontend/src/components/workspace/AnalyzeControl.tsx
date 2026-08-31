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

type State =
  | { kind: "loading" }
  | { kind: "no-snapshot" }
  | { kind: "ready"; snapshot: SnapshotSummary }
  | { kind: "running"; snapshot: SnapshotSummary }
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
  const allowed = can(P.REVIEW_CREATE);
  const processed = version.processing_status === "COMPLETED";

  const load = useCallback(async () => {
    try {
      const snapshots = await api.snapshots({ page_size: 1 });
      const snapshot = snapshots.items[0];
      setState(snapshot ? { kind: "ready", snapshot } : { kind: "no-snapshot" });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, []);

  useEffect(() => {
    if (allowed && processed) void load();
  }, [allowed, processed, load]);

  if (!allowed) {
    return (
      <p className="ws-pane__note">
        This version hasn&rsquo;t been analysed. Starting an analysis needs Review
        creation, which your account does not include.
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
      await api.analyzeReview(review.id);
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
          This version hasn&rsquo;t been analysed, and no configuration has been
          published yet. Analysis needs published standards — that is Legal&rsquo;s
          act, not something this screen can invent.
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
          <p className="ws-pane__note ws-mono">snapshot {state.snapshot.id.slice(0, 8)}</p>
        </>
      ) : null}
      {state.kind === "error" ? (
        <div className="ws-state ws-state--error" role="alert">
          <p>{describeError(state.error)}</p>
        </div>
      ) : null}
    </div>
  );
}
